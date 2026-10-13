from django.db import models


class LabTest(models.Model):
    '''Catalogue of tests the lab offers.'''
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    normal_range = models.CharField(max_length=100, blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True, help_text="Retire tests instead of deleting them.")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TestOrder(models.Model):
    '''
    A request for one or more tests. Usually raised from a consultation;
    consultation is optional so walk-in lab patients can be served too.
    '''
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    patient = models.ForeignKey(
        'profiles.PatientProfile',
        on_delete=models.PROTECT,
        related_name='lab_orders'
    )
    consultation = models.ForeignKey(
        'clinical.Consultation',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='lab_orders'
    )
    ordered_by = models.ForeignKey(
        'profiles.DoctorProfile',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lab_orders'
    )
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    ordered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ordered_at']

    def __str__(self):
        return f"Lab order #{self.pk} for {self.patient} ({self.ordered_at:%Y-%m-%d})"


class TestResult(models.Model):
    '''One test within an order; created pending, filled in by the lab.'''
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COLLECTED = 'collected', 'Sample Collected'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    FINAL_STATUSES = (Status.COMPLETED, Status.CANCELLED)

    order = models.ForeignKey(
        TestOrder,
        on_delete=models.CASCADE,
        related_name='results'
    )
    test = models.ForeignKey(
        LabTest,
        on_delete=models.PROTECT,
        related_name='results'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    result_value = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, null=True)
    labtech = models.ForeignKey(
        'profiles.LabTechProfile',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='test_results'
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.test.name}: {self.result_value or self.get_status_display()}"
