from django.db import models
from profiles.models import PatientProfile, DoctorProfile, LabTechProfile
from clinical.models import Consultation

# Create your models here.
class Tests(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    normal_range = models.CharField(max_length=100, blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class TestOrder(models.Model):
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name='test_orders'
    )
    patient = models.ForeignKey(
        'profiles.PatientProfile',
        on_delete=models.CASCADE,
        related_name='test_orders'
    )
    ordered_by = models.ForeignKey(
        'profiles.DoctorProfile',
        on_delete=models.SET_NULL,
        null=True,
        related_name='test_orders'
    )
    ordered_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Lab Test Order for {self.patient.get_full_name()} ({self.ordered_at})"
    
class TestResult(models.Model):
    order = models.ForeignKey(
        TestOrder,
        on_delete=models.CASCADE,
        related_name='test_results'
    )
    test = models.ForeignKey(
        Tests,
        on_delete=models.CASCADE,
        related_name='test_results'
    )
    
    notes = models.TextField(blank=True, null=True)
    # sample_collected_at = models.DateTimeField(null=True, blank=True)
    
    result_value = models.CharField(max_length=100)
    result_date = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(
    max_length=20,
    choices=[
        ('pending', 'Pending'),
        ('collected', 'Sample Collected'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ],
    default='pending'
    )
    
    labtech = models.ForeignKey(
        'profiles.LabTechProfile',
        on_delete=models.SET_NULL,
        null=True,
        related_name='test_results'
    )

    def __str__(self):
        return f"Result for {self.test.name} - {self.result_value}"

