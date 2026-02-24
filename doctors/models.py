from django.db import models
from django.core.exceptions import ValidationError
from users.models import User


SPECIALTY_CHOICES = (
    ('general_medicine', 'General Medicine'),
    ('cardiology', 'Cardiology'),
    ('dermatology', 'Dermatology'),
    ('neurology', 'Neurology'),
    ('orthopedics', 'Orthopedics'),
    ('pediatrics', 'Pediatrics'),
    ('gynecology', 'Gynecology'),
    ('ophthalmology', 'Ophthalmology'),
    ('ent', 'ENT'),
    ('psychiatry', 'Psychiatry'),
    ('dentistry', 'Dentistry'),
    ('radiology', 'Radiology'),
    ('pathology', 'Pathology'),
    ('oncology', 'Oncology'),
    ('urology', 'Urology'),
    ('other', 'Other'),
)

DAY_CHOICES = (
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
)


class DoctorProfile(models.Model):
    """
    Detailed professional profile for a doctor.
    One-to-one with the User model (role = IS_DOCTOR).
    A doctor MUST be linked to a clinic via ClinicMember — this profile
    stores the professional details that are clinic-agnostic.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='doctor_profile')

    # Professional info
    specialty = models.CharField(max_length=100, choices=SPECIALTY_CHOICES, default='general_medicine')
    qualification = models.CharField(max_length=200, blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)
    biography = models.TextField(blank=True, null=True)
    languages = models.CharField(max_length=200, blank=True, null=True,
                                 help_text="Comma-separated, e.g. English, Hindi")

    # Consultation fees (default; clinic can override per membership)
    first_visit_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    follow_up_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Online consultation
    offers_video_consultation = models.BooleanField(default=False)

    # Status — is_verified set by superadmin; is_active managed by clinic
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'doctor_profile'

    def __str__(self):
        return f"Dr. {self.user.name} ({self.specialty})"

    def get_clinics(self):
        """Returns all active clinics this doctor belongs to."""
        from clinic.models import ClinicMember
        return ClinicMember.objects.filter(
            user=self.user, member_role='doctor', status='active'
        ).select_related('clinic')


class DoctorAvailability(models.Model):
    """
    Weekly recurring schedule slot for a doctor at a specific clinic.
    """
    doctor = models.ForeignKey(
        DoctorProfile, on_delete=models.CASCADE, related_name='availability')
    # Availability is per-clinic so a visiting doctor can have different hours at each clinic
    clinic = models.ForeignKey(
        'clinic.Clinic', on_delete=models.CASCADE, related_name='doctor_slots',
        null=True, blank=True)
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveIntegerField(
        default=15, help_text="Duration of each appointment slot in minutes")
    max_patients = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'doctor_availability'
        unique_together = ('doctor', 'clinic', 'day', 'start_time')
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.doctor} | {self.clinic} | {self.day} {self.start_time}–{self.end_time}"


class DoctorLeave(models.Model):
    """
    Marks a doctor as unavailable for a date range (holiday / leave).
    """
    doctor = models.ForeignKey(
        DoctorProfile, on_delete=models.CASCADE, related_name='leaves')
    clinic = models.ForeignKey(
        'clinic.Clinic', on_delete=models.CASCADE, related_name='doctor_leaves',
        null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'doctor_leave'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.doctor} | {self.start_date} – {self.end_date}"
