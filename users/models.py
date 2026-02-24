import string
import random
from django.db import models
import uuid
from django.db import models, transaction
from django.contrib.auth.models import (AbstractBaseUser, PermissionsMixin, BaseUserManager)
from django.utils import timezone

gender_choice = (
    ("male", "male"),
    ("female", "female"),
    ("others", "others")
)

blood_group_choices = (
    ("A+", "A+"),
    ("A-", "A-"),
    ("B+", "B+"),
    ("B-", "B-"),
    ("AB+", "AB+"),
    ("AB-", "AB-"),
    ("O+", "O+"),
    ("O-", "O-"),
)


class Role(models.Model):

    IS_SUPERADMIN = 1
    IS_ADMIN = 2
    IS_PATIENT = 3
    IS_DOCTOR = 4
    IS_RECEPTIONIST = 5
    IS_LAB_MEMBER = 6
    IS_CLINIC_OWNER = 7

    ROLE_CHOICES = (
        (IS_SUPERADMIN, 'is_superadmin'),
        (IS_ADMIN, 'is_admin'),
        (IS_PATIENT, 'is_patient'),
        (IS_DOCTOR, 'is_doctor'),
        (IS_RECEPTIONIST, 'is_receptionist'),
        (IS_LAB_MEMBER, 'is_lab_member'),
        (IS_CLINIC_OWNER, 'is_clinic_owner'),
    )
    ROLES_CHOICES = (
        ('IS_SUPERADMIN', 'is_superadmin'),
        ('IS_ADMIN', 'is_admin'),
        ('IS_PATIENT', 'is_patient'),
        ('IS_DOCTOR', 'is_doctor'),
        ('IS_RECEPTIONIST', 'is_receptionist'),
        ('IS_LAB_MEMBER', 'is_lab_member'),
        ('IS_CLINIC_OWNER', 'is_clinic_owner'),
    )

    id = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, primary_key=True)
    name = models.CharField(max_length=100, choices=ROLES_CHOICES, blank=True, null=True)

    def __str__(self):
        return str(self.name)


class UserManager(BaseUserManager):

    def _create_user(self, contact, password, **extra_fields):
        if not contact:
            raise ValueError('The given contact must be set')
        try:
            with transaction.atomic():
                user = self.model(contact=contact, **extra_fields)
                user.set_password(password)
                user.save(using=self._db)
                return user
        except:
            raise

    def create_user(self, contact, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(contact, password, **extra_fields)

    def create_superuser(self, contact, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('roles_id', 1)
        return self._create_user(contact, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    age = models.PositiveIntegerField(default=18)
    gender = models.CharField(max_length=100, choices=gender_choice, default=None, null=True)
    blood_group = models.CharField(max_length=5, choices=blood_group_choices, blank=True, null=True)
    roles = models.ForeignKey(Role, on_delete=models.CASCADE, default=3)
    contact = models.BigIntegerField(default=0, unique=True, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatar/', blank=True, null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_partial_onboarding = models.BooleanField(default=False)
    is_complete_onboarding = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'contact'

    def save(self, *args, **kwargs):
        super(User, self).save(*args, **kwargs)
        return self

    def __str__(self):
        return str(self.contact)

    class Meta:
        ordering = ['-date_joined']


class UserAddress(models.Model):
    address_type_choices = (
        ('home', 'home'),
        ('work', 'work'),
    )
    area = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=100, default='India')
    state = models.CharField(max_length=100, blank=True, null=True)
    house_no = models.CharField(max_length=100, blank=True, null=True)
    town = models.CharField(max_length=100, blank=True, null=True)
    landmark = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=100, blank=True, null=True)
    address_type = models.CharField(max_length=100, choices=address_type_choices, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='address_user')
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.area}"

    class Meta:
        db_table = "user_address"


# ─────────────────────────────────────────────────────────────
# Patient Medical Profile (filled during Step 2 onboarding)
# ─────────────────────────────────────────────────────────────

class PatientMedicalProfile(models.Model):
    """
    Extended medical details for patients.
    Created/updated during Step 2 of patient onboarding.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='medical_profile')
    allergies = models.TextField(
        blank=True, null=True,
        help_text="Known allergies (food, drug, environmental)")
    chronic_conditions = models.TextField(
        blank=True, null=True,
        help_text="Chronic conditions e.g. Diabetes, Hypertension")
    current_medications = models.TextField(
        blank=True, null=True,
        help_text="Medications currently being taken")
    past_surgeries = models.TextField(
        blank=True, null=True,
        help_text="History of surgeries")
    family_history = models.TextField(
        blank=True, null=True,
        help_text="Family medical history")
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_number = models.BigIntegerField(blank=True, null=True)
    height_cm = models.PositiveIntegerField(blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Medical profile: {self.user.name or self.user.contact}"

    class Meta:
        db_table = "patient_medical_profile"


# ─────────────────────────────────────────────────────────────
# OTP Log — visible to superadmin in the admin panel
# ─────────────────────────────────────────────────────────────

class OTPLog(models.Model):
    """
    Stores every generated OTP for superadmin visibility.
    Automatically deleted after 10 minutes via admin or a cleanup task.
    """
    contact = models.BigIntegerField()
    otp = models.CharField(max_length=10)
    purpose = models.CharField(
        max_length=50,
        choices=[('patient_register', 'Patient Register'), ('clinic_register', 'Clinic Register')],
        default='patient_register'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP {self.otp} → {self.contact} ({self.purpose})"

    class Meta:
        db_table = "otp_log"
        ordering = ['-created_at']
        verbose_name = "OTP Log"
        verbose_name_plural = "OTP Logs"
