from django.db import models

from helpers.models import TrackingModel


class Appointment(TrackingModel):
    '''A booked slot with a doctor. Checking in turns it into a visit in the queue.'''

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        CHECKED_IN = 'checked_in', 'Checked in'
        CANCELLED = 'cancelled', 'Cancelled'
        NO_SHOW = 'no_show', 'No-show'

    # Appointments that occupy their time slot
    ACTIVE_STATUSES = (Status.SCHEDULED, Status.CHECKED_IN)

    patient = models.ForeignKey('profiles.PatientProfile', on_delete=models.PROTECT, related_name='appointments')
    doctor = models.ForeignKey('profiles.DoctorProfile', on_delete=models.PROTECT, related_name='appointments')
    department = models.ForeignKey(
        'profiles.Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments'
    )
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    cancellation_reason = models.TextField(blank=True)
    booked_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    visit = models.OneToOneField(
        'clinical.Visit', on_delete=models.SET_NULL, null=True, blank=True, related_name='appointment'
    )

    class Meta:
        ordering = ['starts_at']
        indexes = [models.Index(fields=['doctor', 'starts_at'])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F('starts_at')), name='appointment_ends_after_start'
            )
        ]

    def __str__(self):
        return f'{self.patient} with {self.doctor} at {self.starts_at:%Y-%m-%d %H:%M}'

    @property
    def duration_minutes(self):
        return int((self.ends_at - self.starts_at).total_seconds() // 60)
