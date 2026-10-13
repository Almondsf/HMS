from django.db import models

from helpers.models import TrackingModel


class Drug(TrackingModel):
    '''Formulary item and its stock level.'''

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=20, default="unit")  # tablets, ml, capsules, etc.
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.quantity_in_stock <= self.reorder_level


class DispenseTransaction(TrackingModel):
    '''One pharmacy hand-over to a patient; stock moves via its items.'''

    pharmacist = models.ForeignKey(
        'profiles.PharmacistProfile', on_delete=models.SET_NULL, null=True, related_name='dispense_transactions'
    )
    dispensed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dispense #{self.pk} for {self.patient or 'unknown patient'} ({self.dispensed_at:%Y-%m-%d})"

    # All items in a transaction belong to the same patient (enforced by pharmacy.services)
    @property
    def patient(self):
        first_item = self.items.first()
        return first_item.patient if first_item else None

    @property
    def doctor(self):
        first_item = self.items.first()
        return first_item.doctor if first_item else None


class DispensedItem(TrackingModel):
    '''A drug line within a dispense transaction.'''

    transaction = models.ForeignKey(DispenseTransaction, on_delete=models.CASCADE, related_name='items')
    prescription = models.ForeignKey('clinical.Prescription', on_delete=models.PROTECT, related_name='dispensed_items')
    drug = models.ForeignKey(
        Drug,
        on_delete=models.PROTECT,
        null=True,  # legacy rows; new items always have a drug
        related_name='dispensed_items',
    )
    quantity_dispensed = models.PositiveIntegerField()
    notes = models.TextField(blank=True, null=True)  # Optional for pharmacist remarks

    def __str__(self):
        return f"{self.quantity_dispensed} x {self.drug} for {self.patient}"

    @property
    def patient(self):
        return self.prescription.consultation.visit.patient

    @property
    def doctor(self):
        return self.prescription.consultation.visit.assigned_doctor
