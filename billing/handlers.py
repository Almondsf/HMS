'''
Automatic charges. These run inside the clinical action's transaction
(in_transaction=True): a service is never recorded without its charge.
'''

from audit import events
from tenants.features import Feature, has_feature

from . import services
from .models import ServiceItem


def _billing_enabled():
    return has_feature(Feature.BILLING)


@events.subscribe('clinical.visit_opened', in_transaction=True)
def charge_visit_fees(event):
    if not _billing_enabled():
        return
    visit = event.resource
    services.charge_service_items(
        charge_on=ServiceItem.ChargeOn.VISIT_OPENED,
        patient=visit.patient,
        visit=visit,
        source_type='clinical.visit',
        source_id=visit.pk,
    )


@events.subscribe('clinical.consultation_recorded', in_transaction=True)
def charge_consultation_fees(event):
    if not _billing_enabled():
        return
    consultation = event.resource
    services.charge_service_items(
        charge_on=ServiceItem.ChargeOn.CONSULTATION_RECORDED,
        patient=consultation.visit.patient,
        visit=consultation.visit,
        source_type='clinical.consultation',
        source_id=consultation.pk,
    )


@events.subscribe('lab.order_placed', in_transaction=True)
def charge_lab_tests(event):
    if not _billing_enabled():
        return
    order = event.resource
    visit = order.consultation.visit if order.consultation_id else None
    for result in order.results.select_related('test'):
        services.add_charge(
            patient=order.patient,
            visit=visit,
            category=ServiceItem.Category.LAB,
            description=f'Lab: {result.test.name}',
            unit_price=result.test.cost,
            source=('lab.testresult', result.pk),
        )


@events.subscribe('pharmacy.dispensed', in_transaction=True)
def charge_dispensed_drugs(event):
    if not _billing_enabled():
        return
    for item in event.resource.items.select_related('drug', 'prescription__consultation__visit__patient'):
        visit = item.prescription.consultation.visit
        services.add_charge(
            patient=visit.patient,
            visit=visit,
            category=ServiceItem.Category.PHARMACY,
            description=f'{item.drug.name} ({item.drug.unit})',
            unit_price=item.drug.unit_price,
            quantity=item.quantity_dispensed,
            source=('pharmacy.dispenseditem', item.pk),
        )
