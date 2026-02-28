from rest_framework import serializers
from users.serializers import UserSerializer
from .models import Document, DocumentConsent, DocumentAccessLog


class DocumentSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['id', 'owner', 'uploaded_by', 'uploaded_by_role', 'created_at', 'updated_at']


class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['title', 'document_type', 'file', 'description', 'appointment']

    def validate_file(self, value):
        # ── PDF only ──────────────────────────────────────────────────────────
        content_type = getattr(value, 'content_type', None)
        name = value.name.lower() if value.name else ''

        if content_type != 'application/pdf' or not name.endswith('.pdf'):
            raise serializers.ValidationError('Only PDF files are accepted.')

        # ── 5 MB max ──────────────────────────────────────────────────────────
        max_size = 5 * 1024 * 1024  # 5 MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError(
                f'File size must not exceed 5 MB. Uploaded file is {value.size / (1024*1024):.1f} MB.'
            )

        return value


class DocumentConsentSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.name', read_only=True)
    patient_name = serializers.CharField(source='patient.name', read_only=True)

    class Meta:
        model = DocumentConsent
        fields = [
            'id', 'document', 'document_title', 'doctor', 'doctor_name',
            'patient', 'patient_name', 'status', 'purpose',
            'expires_at', 'actioned_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'patient', 'document_title', 'doctor_name',
            'patient_name', 'actioned_at', 'created_at',
        ]


class ConsentActionSerializer(serializers.Serializer):
    """Patient uses this to grant or reject a consent request."""
    action = serializers.ChoiceField(choices=['granted', 'rejected', 'revoked'])
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class DocumentMetaSerializer(serializers.ModelSerializer):
    """
    Safe document listing for doctors — exposes only metadata, never the file URL.
    Doctor uses this to know which document IDs to request consent for.
    """
    consent_status = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'document_type', 'description',
            'uploaded_by_role', 'created_at', 'consent_status',
        ]

    def get_consent_status(self, obj):
        """
        Returns the current consent status this doctor has for the document,
        or None if no request has been made yet.
        """
        doctor = self.context.get('doctor')
        if not doctor:
            return None
        consent = DocumentConsent.objects.filter(
            document=obj, doctor=doctor
        ).order_by('-created_at').first()
        return consent.status if consent else None


class DocumentAccessLogSerializer(serializers.ModelSerializer):
    accessed_by_name = serializers.CharField(source='accessed_by.name', read_only=True)

    class Meta:
        model = DocumentAccessLog
        fields = ['id', 'document', 'accessed_by_name', 'ip_address', 'accessed_at']
