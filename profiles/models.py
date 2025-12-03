from django.db import models

# Create your models here.

''' Model representing a Doctor with personal and professional details.'''
class DoctorProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    specialty = models.CharField(max_length=50)
    license_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name} - {self.specialty}"
   
''' Model representing a Patient linked to a User account.''' 
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
    blood_group = models.CharField(choices=bloodGroup.choices, max_length=3, blank=True, null=True)
    genotype = models.CharField(choices=genotype.choices, max_length=2, blank=True, null=True)
    allergies = models.TextField(blank=True, null=True)
    medical_history = models.TextField(blank=True, null=True)
    assigned_doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, blank=True, null=True)
    
    def __str__(self):
        
        return self.user.get_full_name() or self.user.username #
    
    
class LabTechProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    qualifications = models.TextField(blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"Lab Technician: {self.user.first_name} {self.user.last_name}"

class PharmacistProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)
    qualifications = models.TextField(blank=True, null=True)
    years_of_experience = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"Pharmacist: {self.user.first_name} {self.user.last_name}"
    
class ReceptionistProfile(models.Model):
    user = models.OneToOneField('authentication.User', on_delete=models.CASCADE)

    def __str__(self):
        return f"Receptionist: {self.user.first_name} {self.user.last_name}"