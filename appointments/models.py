from django.db import models
from users.models import User
from doctors.models import DoctorProfile


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    )

    TYPE_CHOICES = (
        ('first_visit', 'First Visit'),
        ('follow_up', 'Follow Up'),
    )

    MODE_CHOICES = (
        ('in_clinic', 'In Clinic'),
        ('video', 'Video Consultation'),
    )

    # Parties
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='patient_appointments')
    doctor = models.ForeignKey(
        DoctorProfile, on_delete=models.CASCADE, related_name='doctor_appointments')

    # Scheduling
    appointment_date = models.DateField(db_index=True)
    appointment_time = models.TimeField()
    appointment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='first_visit')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='in_clinic')

    # Details
    reason = models.TextField(blank=True, null=True,
                              help_text="Patient's reason for visit / chief complaint")
    notes = models.TextField(blank=True, null=True,
                             help_text="Doctor's notes after the appointment")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    # Payment
    fee_charged = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)

    # Cancellation
    cancelled_by = models.CharField(max_length=50, blank=True, null=True)  # 'patient' | 'doctor'
    cancellation_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointment'
        ordering = ['-appointment_date', '-appointment_time']
        indexes = [
            models.Index(fields=['appointment_date', 'doctor'], name='appt_date_doctor_idx'),
            models.Index(fields=['patient', 'status'], name='appt_patient_status_idx'),
        ]

    def __str__(self):
        return f"{self.patient} → Dr.{self.doctor} | {self.appointment_date} {self.appointment_time}"
