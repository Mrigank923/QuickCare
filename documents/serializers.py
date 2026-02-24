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


class DocumentAccessLogSerializer(serializers.ModelSerializer):
    accessed_by_name = serializers.CharField(source='accessed_by.name', read_only=True)

    class Meta:
        model = DocumentAccessLog
        fields = ['id', 'document', 'accessed_by_name', 'ip_address', 'accessed_at']
