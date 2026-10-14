from django.db import models


class Department(models.Model):
    '''A clinical or administrative unit, e.g. Paediatrics, Emergency, Ward B.'''

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class RecordSequence(models.Model):
    '''Per-hospital counters for human-readable numbers (MRNs, later invoices).'''

    name = models.CharField(max_length=50, unique=True)
    last_value = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return f'{self.name}: {self.last_value}'


class DoctorProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    specialty = models.CharField(max_length=50)
    license_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctors')

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name} - {self.specialty}"


class NurseProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    license_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='nurses')

    def __str__(self):
        return f"Nurse {self.user.get_full_name()}"


class PatientProfile(models.Model):
    class bloodGroup(models.TextChoices):
        A_POSITIVE = 'A+', 'A+'
        A_NEGATIVE = 'A-', 'A-'
        B_POSITIVE = 'B+', 'B+'
        B_NEGATIVE = 'B-', 'B-'
        AB_POSITIVE = 'AB+', 'AB+'
        AB_NEGATIVE = 'AB-', 'AB-'
        O_POSITIVE = 'O+', 'O+'
        O_NEGATIVE = 'O-', 'O-'

    class genotype(models.TextChoices):
        AA = 'AA', 'AA'
        AS = 'AS', 'AS'
        SS = 'SS', 'SS'
        AC = 'AC', 'AC'
        SC = 'SC', 'SC'

    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    mrn = models.CharField(
        'medical record number', max_length=20, unique=True, help_text='Assigned at registration; never changes'
    )
    blood_group = models.CharField(choices=bloodGroup.choices, max_length=3, blank=True, null=True)
    genotype = models.CharField(choices=genotype.choices, max_length=2, blank=True, null=True)
    allergies = models.TextField(blank=True, null=True)
    medical_history = models.TextField(blank=True, null=True)
    assigned_doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.email


class LabTechProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    qualifications = models.TextField(blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"Lab Technician: {self.user.first_name} {self.user.last_name}"


class PharmacistProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE, related_name='pharmacist')
    qualifications = models.TextField(blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"Pharmacist: {self.user.first_name} {self.user.last_name}"


class CashierProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)

    def __str__(self):
        return f"Cashier: {self.user.get_full_name()}"


class ReceptionistProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)

    def __str__(self):
        return f"Receptionist: {self.user.first_name} {self.user.last_name}"
