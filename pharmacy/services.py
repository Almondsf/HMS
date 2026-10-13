'''Pharmacy workflow: dispensing against prescriptions and moving stock.'''

from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F

from clinical.models import Prescription

from .models import DispensedItem, DispenseTransaction, Drug


@transaction.atomic
def dispense(*, pharmacist_user, items):
    '''
    Dispense drugs for one patient's prescriptions and deduct stock.

    `items`: [{'prescription': Prescription, 'drug': Drug, 'quantity_dispensed': int, 'notes': str}]

    Drug and prescription rows are locked for the whole transaction, so two
    pharmacists dispensing at once can't oversell stock or a prescription.
    '''
    pharmacist = getattr(pharmacist_user, 'pharmacist', None)
    if pharmacist is None:
        raise PermissionDenied('Only pharmacists can dispense.')
    if not items:
        raise ValidationError('At least one dispensed item is required.')

    # Lock in a stable order (by id) to avoid deadlocks between concurrent dispenses
    drugs = Drug.objects.select_for_update().in_bulk(sorted({item['drug'].pk for item in items}))
    prescriptions = (
        Prescription.objects.select_for_update(of=('self',))
        .select_related('consultation__visit')
        .in_bulk(sorted({item['prescription'].pk for item in items}))
    )

    errors = []
    if len({p.consultation.visit.patient_id for p in prescriptions.values()}) > 1:
        errors.append('All items in a dispense must be for the same patient.')

    requested_per_drug = defaultdict(int)
    requested_per_prescription = defaultdict(int)
    for item in items:
        drug, prescription = drugs[item['drug'].pk], prescriptions[item['prescription'].pk]
        if prescription.drug_id and prescription.drug_id != drug.pk:
            errors.append(f'Prescription #{prescription.pk} is for {prescription.drug}, not {drug}.')
        requested_per_drug[drug.pk] += item['quantity_dispensed']
        requested_per_prescription[prescription.pk] += item['quantity_dispensed']

    for drug_id, requested in requested_per_drug.items():
        drug = drugs[drug_id]
        if requested > drug.quantity_in_stock:
            errors.append(f'Insufficient stock for {drug}. Available: {drug.quantity_in_stock}, requested: {requested}.')

    for prescription_id, requested in requested_per_prescription.items():
        prescription = prescriptions[prescription_id]
        if prescription.quantity is not None:
            remaining = prescription.quantity - prescription.quantity_dispensed
            if requested > remaining:
                errors.append(
                    f'Prescription #{prescription.pk} has {remaining} unit(s) left to dispense, requested {requested}.'
                )

    if errors:
        raise ValidationError(errors)

    dispense_transaction = DispenseTransaction.objects.create(pharmacist=pharmacist)
    for item in items:
        DispensedItem.objects.create(
            transaction=dispense_transaction,
            prescription=prescriptions[item['prescription'].pk],
            drug=drugs[item['drug'].pk],
            quantity_dispensed=item['quantity_dispensed'],
            notes=item.get('notes'),
        )
    for drug_id, requested in requested_per_drug.items():
        Drug.objects.filter(pk=drug_id).update(quantity_in_stock=F('quantity_in_stock') - requested)

    return dispense_transaction
