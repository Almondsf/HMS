from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Create your models here.

class UserManager(BaseUserManager):
    def create_user(self, first_name, last_name, email, password=None,  **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        if not last_name:
            raise ValueError("Users must have a last name")
        if not first_name:
            raise ValueError("Users must have a first name")
        email = self.normalize_email(email)
        user = self.model(
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            **extra_fields
        )
        
    def get_patients(self):
        """Get all active patients"""
        return self.filter(user_type='patient', is_active=True)
    
    def get_doctors(self):
        """Get all active doctors"""
        return self.filter(user_type='doctor', is_active=True)
    
    def get_staff(self):
        """Get all staff members (excluding patients)"""
        return self.exclude(user_type='patient').filter(is_active=True)
    
    
class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for Hospital Management System
    Uses email as the primary authentication field
    """
    
    class UserType(models.TextChoices):
        PATIENT = 'patient', _('Patient')
        DOCTOR = 'doctor', _('Doctor')
        NURSE = 'nurse', _('Nurse')
        ADMIN = 'admin', _('Admin')
        RECEPTIONIST = 'receptionist', _('Receptionist')
        PHARMACIST = 'pharmacist', _('Pharmacist')
        LAB_TECHNICIAN = 'lab_tech', _('Lab Technician')
    
    # Phone number validator
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    # Basic Information
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(max_length=100, unique=True, db_index=True)
    
    # Hospital-specific fields
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.PATIENT,
        db_index=True,
        help_text="Type of user in the hospital system"
    )
    
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        help_text="Contact phone number"
    )
    
    # Status flags
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this user should be treated as active."
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into admin site."
    )
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Manager
    objects = UserManager()
    
    # Authentication settings
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type', 'is_active']),
            models.Index(fields=['phone_number']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Return the short name for the user"""
        return self.first_name
    
    # Property methods for user type checks
    @property
    def is_patient(self):
        """Check if user is a patient"""
        return self.user_type == self.UserType.PATIENT
    
    @property
    def is_doctor(self):
        """Check if user is a doctor"""
        return self.user_type == self.UserType.DOCTOR
    
    @property
    def is_nurse(self):
        """Check if user is a nurse"""
        return self.user_type == self.UserType.NURSE
    
    @property
    def is_receptionist(self):
        """Check if user is a receptionist"""
        return self.user_type == self.UserType.RECEPTIONIST
    
    @property
    def is_pharmacist(self):
        """Check if user is a pharmacist"""
        return self.user_type == self.UserType.PHARMACIST
    
    @property
    def is_lab_technician(self):
        """Check if user is a lab technician"""
        return self.user_type == self.UserType.LAB_TECHNICIAN
    
    @property
    def is_staff_member(self):
        """Check if user is any type of staff (not patient)"""
        return self.user_type != self.UserType.PATIENT
    
    def has_perm(self, perm, obj=None):
        """Does the user have a specific permission?"""
        return self.is_admin or self.is_superuser
    
    def has_module_perms(self, app_label):
        """Does the user have permissions to view the app `app_label`?"""
        return self.is_admin or self.is_superuser