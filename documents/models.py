import uuid
from django.db import models
from users.models import User
from doctors.models import DoctorProfile
from appointments.models import Appointment


class Document(models.Model):
    """
    A medical document uploaded by a doctor or patient.
    Can be a lab report, prescription, discharge summary, scan, etc.
    """
    DOC_TYPE_CHOICES = (
        ('prescription', 'Prescription'),
        ('lab_report', 'Lab Report'),
        ('scan', 'Scan / Imaging'),
        ('discharge_summary', 'Discharge Summary'),
        ('vaccination', 'Vaccination Record'),
        ('insurance', 'Insurance Document'),
        ('other', 'Other'),
    )

    UPLOADED_BY_CHOICES = (
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
        ('lab_member', 'Lab Member'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=50, choices=DOC_TYPE_CHOICES, default='other')
    file = models.FileField(upload_to='documents/%Y/%m/')
    description = models.TextField(blank=True, null=True)

    # Ownership
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='owned_documents',
        help_text="The patient this document belongs to")
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_documents')
    uploaded_by_role = models.CharField(max_length=20, choices=UPLOADED_BY_CHOICES, default='patient')

    # Optional link to appointment
    appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')

    # Soft delete
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.document_type}) — {self.owner}"


class DocumentConsent(models.Model):
    """
    Patient grants explicit consent for a specific doctor to view a document.
    Consent has an optional expiry. Doctors cannot access documents without consent.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),    # Doctor requested access
        ('granted', 'Granted'),    # Patient approved
        ('revoked', 'Revoked'),    # Patient revoked after granting
        ('expired', 'Expired'),    # Past expiry date
        ('rejected', 'Rejected'),  # Patient rejected the request
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='consents')
    doctor = models.ForeignKey(
        DoctorProfile, on_delete=models.CASCADE, related_name='document_consents')
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='given_consents')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    purpose = models.TextField(blank=True, null=True,
                               help_text="Why the doctor is requesting access")
    expires_at = models.DateTimeField(blank=True, null=True,
                                      help_text="Leave blank for indefinite access")

    # Who actioned last
    actioned_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_consent'
        unique_together = ('document', 'doctor')
        ordering = ['-created_at']

    def __str__(self):
        return f"Consent: {self.document.title} → Dr.{self.doctor} [{self.status}]"


class DocumentAccessLog(models.Model):
    """
    Audit trail: records every time a document is accessed.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_logs')
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    consent = models.ForeignKey(DocumentConsent, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'document_access_log'
        ordering = ['-accessed_at']

    def __str__(self):
        return f"{self.accessed_by} accessed '{self.document.title}' at {self.accessed_at}"
