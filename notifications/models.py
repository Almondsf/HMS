from django.db import models

from helpers.models import TrackingModel


class SmsMessage(TrackingModel):
    '''Every SMS sent (or deliberately not sent) to a patient, and why.'''

    class Kind(models.TextChoices):
        BOOKING = 'appointment_booked', 'Booking confirmation'
        REMINDER = 'appointment_reminder', 'Appointment reminder'

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Not sent'

    kind = models.CharField(max_length=30, choices=Kind.choices)
    patient = models.ForeignKey('profiles.PatientProfile', on_delete=models.PROTECT, related_name='sms_messages')
    appointment = models.ForeignKey(
        'scheduling.Appointment', on_delete=models.PROTECT, null=True, blank=True, related_name='sms_messages'
    )
    # The slot the message was about: a rescheduled appointment gets its own messages
    appointment_starts_at = models.DateTimeField(null=True, blank=True)
    to = models.CharField(max_length=20, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    error = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=30, blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['appointment', 'kind', 'appointment_starts_at'], name='one_message_per_appointment_slot'
            )
        ]

    def __str__(self):
        return f'{self.get_kind_display()} to {self.to or "?"}: {self.get_status_display()}'


class Notification(models.Model):
    '''A message in a staff member's notification centre (the bell in the web app).'''

    class Level(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Needs attention'
        URGENT = 'urgent', 'Urgent'

    recipient = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=50)  # the event, e.g. lab.result_completed
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    title = models.CharField(max_length=150)
    body = models.CharField(max_length=300, blank=True)
    link = models.CharField(max_length=200, blank=True, help_text='Screen in the web app, e.g. /visits/12')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)  # on its own or in a daily summary

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'read_at'])]

    def __str__(self):
        return f'{self.recipient}: {self.title}'
