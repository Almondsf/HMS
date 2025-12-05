from django.db import models
from helpers.models import TrackingModel
from clinical.models import Prescription
from profiles.models import PharmacistProfile


# Drug / Inventory
class Drug(TrackingModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=20, default="unit")  # tablets, ml, capsules, etc.
    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name


# Dispense Transaction
class DispenseTransaction(TrackingModel):
    pharmacist = models.ForeignKey(
        PharmacistProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='dispense_transactions'
    )
    dispensed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dispense Transaction for {self.patient.get_full_name()} ({self.dispensed_at})"
    @property 
    def patient(self):
        # Assuming all items in the transaction belong to the same patient
        first_item = self.items.first()
        if first_item:
            return first_item.patient
        return None
    def doctor(self):
        first_item = self.items.first()
        if first_item:
            return first_item.doctor
        return None




# Dispensed Items (per drug line)
class DispensedItem(TrackingModel):
    transaction = models.ForeignKey(
        DispenseTransaction,
        on_delete=models.CASCADE,
        related_name='items'
    )
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='dispensed_items'
    )
    drug = models.ForeignKey(
        Drug,
        on_delete=models.SET_NULL,
        null=True,
        related_name='dispensed_items'
    )
    quantity_dispensed = models.PositiveIntegerField()
    notes = models.TextField(blank=True, null=True)  # Optional for pharmacist remarks

    def __str__(self):
        return f"{self.prescription.medication_name} dispensed to {self.patient.get_full_name()}"

    @property
    def patient(self):
        return self.prescription.consultation.visit.patient

    @property
    def doctor(self):
        return self.prescription.consultation.visit.assigned_doctor

