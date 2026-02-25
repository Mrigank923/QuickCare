from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from users.serializers import UserSerializer
from .models import DoctorProfile, DoctorAvailability, DoctorLeave


class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorAvailability
        fields = '__all__'
        read_only_fields = ['doctor']


class DoctorLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorLeave
        fields = '__all__'
        read_only_fields = ['doctor']


class DoctorClinicInfoSerializer(serializers.Serializer):
    """Inline clinic info shown inside DoctorProfile response."""
    clinic_id = serializers.UUIDField(source='clinic.id')
    clinic_name = serializers.CharField(source='clinic.name')
    city = serializers.CharField(source='clinic.city')
    department = serializers.CharField()
    joined_at = serializers.DateField()


class DoctorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    availability = DoctorAvailabilitySerializer(many=True, read_only=True)
    clinics = serializers.SerializerMethodField()

    class Meta:
        model = DoctorProfile
        fields = '__all__'
        read_only_fields = ['user', 'is_verified', 'created_at', 'updated_at']

    @extend_schema_field(DoctorClinicInfoSerializer(many=True))
    def get_clinics(self, obj):
        """Return a summary of all active clinics this doctor belongs to."""
        from clinic.models import ClinicMember
        memberships = ClinicMember.objects.filter(
            user=obj.user, member_role='doctor', status='active'
        ).select_related('clinic')
        return [
            {
                'clinic_id': str(m.clinic.id),
                'clinic_name': m.clinic.name,
                'city': m.clinic.city,
                'department': m.department,
                'joined_at': str(m.joined_at) if m.joined_at else None,
            }
            for m in memberships
        ]


class DoctorProfileWriteSerializer(serializers.ModelSerializer):
    """Used by a doctor to update their own professional details."""
    class Meta:
        model = DoctorProfile
        exclude = ['user', 'is_verified', 'created_at', 'updated_at']
