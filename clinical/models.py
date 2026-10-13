from django.db import models
from django.db.models import Sum
from helpers.models import TrackingModel

# Medical history must survive staff/patient changes, so records PROTECT
# their parents instead of cascading deletes. Deactivate accounts instead.


class Visit(TrackingModel):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    patient = models.ForeignKey(
        'profiles.PatientProfile',
        on_delete=models.PROTECT,
        related_name='visits'
    )
    assigned_doctor = models.ForeignKey(
        'profiles.DoctorProfile',
        on_delete=models.PROTECT,
        related_name='assigned_visits'
    )
    visit_date = models.DateTimeField(auto_now_add=True)
    reason_for_visit = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )

    def __str__(self):
        return f"Visit of {self.patient} on {self.visit_date:%Y-%m-%d}"


class Consultation(TrackingModel):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        related_name='consultations'
    )
    subjective = models.TextField(blank=True, null=True, help_text="Patient complaints, symptoms, history.")
    objective = models.TextField(blank=True, null=True, help_text="Physical exam findings, vitals, test results.")
    assessment = models.TextField(blank=True, null=True, help_text="Diagnosis or clinical impression.")
    plan = models.TextField(blank=True, null=True, help_text="Treatment plan + medications + procedures.")
    follow_up_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Consultation ({self.visit.patient})"


class Prescription(TrackingModel):
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.PROTECT,
        related_name='prescriptions'
    )
    drug = models.ForeignKey(
        'pharmacy.Drug',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='prescriptions',
        help_text="Formulary drug. Optional so items not stocked can still be prescribed."
    )
    medication_name = models.CharField(max_length=100, blank=True)
    dosage = models.CharField(max_length=50)
    frequency = models.CharField(max_length=50)
    duration = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total units to dispense; caps what pharmacy can dispense."
    )
    instructions = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Prescription: {self.medication_name} for {self.consultation.visit.patient}"

    @property
    def patient(self):
        return self.consultation.visit.patient

    @property
    def quantity_dispensed(self):
        return self.dispensed_items.aggregate(total=Sum('quantity_dispensed'))['total'] or 0
