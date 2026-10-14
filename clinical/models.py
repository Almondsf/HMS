from django.db import models
from django.db.models import Sum

from helpers.models import TrackingModel

# Medical history must survive staff/patient changes, so records PROTECT
# their parents instead of cascading deletes. Deactivate accounts instead.


class Visit(TrackingModel):
    class Status(models.TextChoices):
        WAITING = 'waiting', 'Waiting'  # in the doctor's queue
        IN_PROGRESS = 'in_progress', 'In consultation'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    QUEUE_STATUSES = (Status.WAITING, Status.IN_PROGRESS)

    class Triage(models.TextChoices):
        EMERGENCY = 'emergency', 'Emergency'
        URGENT = 'urgent', 'Urgent'
        STANDARD = 'standard', 'Standard'
        NON_URGENT = 'non_urgent', 'Non-urgent'

    # Queue order: lower is seen first; untriaged patients count as standard
    TRIAGE_RANK = {Triage.EMERGENCY: 0, Triage.URGENT: 1, Triage.STANDARD: 2, Triage.NON_URGENT: 3}

    patient = models.ForeignKey('profiles.PatientProfile', on_delete=models.PROTECT, related_name='visits')
    assigned_doctor = models.ForeignKey(
        'profiles.DoctorProfile', on_delete=models.PROTECT, related_name='assigned_visits'
    )
    visit_date = models.DateTimeField(auto_now_add=True)
    reason_for_visit = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING, db_index=True)

    triage_level = models.CharField(max_length=20, choices=Triage.choices, blank=True)
    triage_notes = models.TextField(blank=True)
    triaged_at = models.DateTimeField(null=True, blank=True)
    triaged_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    def __str__(self):
        return f"Visit of {self.patient} on {self.visit_date:%Y-%m-%d}"


class VitalSigns(models.Model):
    '''One set of observations taken during a visit. Every measurement is optional.'''

    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name='vitals')
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulse_bpm = models.PositiveSmallIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Breaths per minute')
    systolic_bp = models.PositiveSmallIntegerField(null=True, blank=True, help_text='mmHg')
    diastolic_bp = models.PositiveSmallIntegerField(null=True, blank=True, help_text='mmHg')
    spo2_percent = models.PositiveSmallIntegerField('SpO2 (%)', null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    blood_glucose_mmol = models.DecimalField(
        'blood glucose (mmol/L)', max_digits=4, decimal_places=1, null=True, blank=True
    )
    pain_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='0 (none) to 10 (worst)')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name_plural = 'vital signs'

    def __str__(self):
        return f'Vitals for {self.visit} at {self.recorded_at:%H:%M}'

    @property
    def bmi(self):
        if self.weight_kg and self.height_cm:
            metres = float(self.height_cm) / 100
            return round(float(self.weight_kg) / (metres * metres), 1)
        return None


class Consultation(TrackingModel):
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name='consultations')
    subjective = models.TextField(blank=True, null=True, help_text="Patient complaints, symptoms, history.")
    objective = models.TextField(blank=True, null=True, help_text="Physical exam findings, vitals, test results.")
    assessment = models.TextField(blank=True, null=True, help_text="Diagnosis or clinical impression.")
    plan = models.TextField(blank=True, null=True, help_text="Treatment plan + medications + procedures.")
    follow_up_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Consultation ({self.visit.patient})"


class Diagnosis(TrackingModel):
    """An ICD-10 coded (or free-text) diagnosis made in a consultation."""

    class Kind(models.TextChoices):
        PRIMARY = 'primary', 'Primary'
        SECONDARY = 'secondary', 'Secondary'

    class Certainty(models.TextChoices):
        PROVISIONAL = 'provisional', 'Provisional'
        CONFIRMED = 'confirmed', 'Confirmed'
        RULED_OUT = 'ruled_out', 'Ruled out'

    consultation = models.ForeignKey(Consultation, on_delete=models.PROTECT, related_name='diagnoses')
    # Codes are shared reference data in the public schema: no cross-schema
    # constraint; codes are never deleted and are validated on save
    code = models.ForeignKey(
        'terminology.Icd10Code',
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name='+',
    )
    description = models.CharField(max_length=255, help_text='Defaults to the ICD-10 title')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PRIMARY)
    certainty = models.CharField(max_length=20, choices=Certainty.choices, default=Certainty.PROVISIONAL)

    class Meta:
        ordering = ['consultation', 'kind', 'id']
        verbose_name_plural = 'diagnoses'
        constraints = [
            models.UniqueConstraint(
                fields=['consultation'],
                condition=models.Q(kind='primary') & ~models.Q(certainty='ruled_out'),
                name='one_primary_diagnosis_per_consultation',
            )
        ]

    def __str__(self):
        return f"{self.code_id or 'uncoded'} {self.description}"


class Prescription(TrackingModel):
    consultation = models.ForeignKey(Consultation, on_delete=models.PROTECT, related_name='prescriptions')
    drug = models.ForeignKey(
        'pharmacy.Drug',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='prescriptions',
        help_text="Formulary drug. Optional so items not stocked can still be prescribed.",
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
