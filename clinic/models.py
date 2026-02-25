import uuid
from django.db import models
from django.utils.text import slugify
from users.models import User


# ─────────────────────────────────────────────────────────────
# Clinic
# ─────────────────────────────────────────────────────────────

class Clinic(models.Model):
    """
    Represents a hospital or clinic.
    A clinic is owned/managed by a user with IS_CLINIC_OWNER role.
    Doctors and lab members can only operate under a clinic.
    """
    TYPE_CHOICES = (
        ('clinic', 'Clinic'),
        ('hospital', 'Hospital'),
        ('diagnostic_center', 'Diagnostic Center'),
        ('polyclinic', 'Polyclinic'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    clinic_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='clinic')
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='owned_clinics',
        help_text="The clinic owner/admin user (role = IS_CLINIC_OWNER)"
    )

    # Contact & Location
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    # Registration
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    logo = models.ImageField(upload_to='clinic/logos/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinic'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Clinic.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────
# Clinic Member  (Doctor / Lab Member / Receptionist)
# ─────────────────────────────────────────────────────────────

class ClinicMember(models.Model):
    """
    Links a user (doctor, lab member, receptionist) to a clinic.

    Key rules enforced:
      - A doctor/lab member MUST belong to at least one clinic via this table.
      - The clinic owner adds or removes members.
      - A member can belong to multiple clinics (e.g. visiting doctor).
      - Removing a member sets is_active=False (soft-remove), preserving history.
    """
    MEMBER_ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('lab_member', 'Lab Member'),
        ('receptionist', 'Receptionist'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),      # Invite sent, not yet accepted
        ('active', 'Active'),        # Currently working at the clinic
        ('inactive', 'Inactive'),    # Removed / deactivated by clinic
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='clinic_memberships')
    member_role = models.CharField(
        max_length=20, choices=MEMBER_ROLE_CHOICES, default='doctor')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')

    # Who added this member (must be the clinic owner or admin)
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='added_clinic_members')

    # Optional: doctor's department within the clinic
    department = models.CharField(max_length=100, blank=True, null=True)

    # Invite token for email/SMS-based onboarding
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False)
    invite_accepted_at = models.DateTimeField(null=True, blank=True)

    joined_at = models.DateField(null=True, blank=True)
    left_at = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True, null=True,
                             help_text="Internal notes about this member (e.g. visiting doctor)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinic_member'
        # A user can only have ONE active entry per clinic
        unique_together = ('clinic', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.name} @ {self.clinic.name} [{self.member_role}]"

    @property
    def is_active(self):
        return self.status == 'active'


# ─────────────────────────────────────────────────────────────
# Clinic Time Slot  (appointment schedule setup during onboarding)
# ─────────────────────────────────────────────────────────────

class ClinicTimeSlot(models.Model):
    """
    Weekly recurring time slots for a clinic.
    Set up by the clinic owner during onboarding (Step 2).
    Doctors inherit these slots or override with DoctorAvailability.
    """
    DAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name='time_slots')
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField(
        default=15, help_text="Duration of each appointment slot in minutes")
    max_appointments = models.PositiveSmallIntegerField(
        default=20, help_text="Max appointments in this time window")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clinic_time_slot'
        ordering = ['day_of_week', 'start_time']
        unique_together = ('clinic', 'day_of_week', 'start_time')

    def __str__(self):
        day_name = dict(self.DAY_CHOICES).get(self.day_of_week, '')
        return f"{self.clinic.name} — {day_name} {self.start_time}–{self.end_time}"


# ─────────────────────────────────────────────────────────────
# Clinic Admission Document Requirements
# ─────────────────────────────────────────────────────────────

class ClinicAdmissionDocument(models.Model):
    """
    Checklist of documents a clinic requires from a patient at the time of admission.
    Defined by the clinic owner. Publicly visible so patients can prepare in advance.
    """
    DOC_TYPE_CHOICES = (
        ('id_proof',       'ID Proof (Aadhar, PAN, Passport)'),
        ('insurance',      'Insurance / TPA Card'),
        ('prescription',   'Prescription / Referral Letter'),
        ('lab_report',     'Lab / Blood Report'),
        ('imaging',        'Imaging / X-Ray / MRI / CT Scan'),
        ('vaccination',    'Vaccination Record'),
        ('discharge_summary', 'Previous Discharge Summary'),
        ('other',          'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name='admission_documents')
    document_name = models.CharField(
        max_length=200,
        help_text="Human-readable name, e.g. 'Aadhar Card', 'CBC Blood Report'")
    document_type = models.CharField(
        max_length=50, choices=DOC_TYPE_CHOICES, default='other')
    is_mandatory = models.BooleanField(
        default=True,
        help_text="True = patient must bring this; False = recommended but optional")
    notes = models.TextField(
        blank=True, null=True,
        help_text="Additional instructions for the patient, e.g. 'original + 2 photocopies'")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinic_admission_document'
        ordering = ['-is_mandatory', 'document_type', 'document_name']

    def __str__(self):
        mandatory = 'Mandatory' if self.is_mandatory else 'Optional'
        return f"{self.clinic.name} — {self.document_name} [{mandatory}]"
