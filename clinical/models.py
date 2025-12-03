from django.db import models
from helpers.models import TrackingModel

class Visit(TrackingModel):
    class visit_status(models.TextChoices):
        IN_PROGRESS = 'In Progress'
        COMPLETED = 'Completed'
        CANCELLED = 'Cancelled'
    
    patient = models.ForeignKey(
        'profiles.PatientProfile',
        on_delete=models.CASCADE,
        related_name='visits'
    )
    assigned_doctor = models.ForeignKey(
        'profiles.DoctorProfile',
        on_delete=models.CASCADE,
        related_name='assigned_visits'
    )
    visit_date = models.DateTimeField(auto_now_add=True)
    reason_for_visit = models.TextField()

    def __str__(self):
        return f"Visit of {self.patient} on {self.visit_date}"

class Consultation(TrackingModel):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='consultations'
    )
    subjective = models.TextField(blank=True, null=True, help_text="Patient complaints, symptoms, history.")
    objective = models.TextField(blank=True, null=True, help_text="Physical exam findings, vitals, test results.")
    assessment = models.TextField(blank=True, null=True, help_text="Diagnosis or clinical impression.")
    plan = models.TextField(blank=True, null=True, help_text="Treatment plan + medications + procedures.")
    follow_up_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Consultation ({self.visit.patient.user.get_full_name()})"
    

class Prescription(TrackingModel):
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name='prescriptions'
    )
    medication_name = models.CharField(max_length=100)
    dosage = models.CharField(max_length=50)
    frequency = models.CharField(max_length=50)
    duration = models.CharField(max_length=50)
    instructions = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Prescription: {self.medication_name} for {self.consultation.visit.patient.user.get_full_name()}"
    
class LabTestOrder(models.Model):
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name="lab_orders"
    )
    test_name = models.CharField(max_length=150)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending','Pending'), ('completed','Completed')],
        default='pending'
    )
