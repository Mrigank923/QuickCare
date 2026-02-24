from rest_framework import serializers
from django.utils import timezone
from users.serializers import UserSerializer
from .models import Clinic, ClinicMember


class ClinicSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            'id', 'name', 'slug', 'clinic_type', 'owner',
            'phone', 'email', 'address', 'city', 'state', 'pincode',
            'registration_number', 'logo', 'description',
            'is_active', 'member_count', 'created_at',
        ]
        read_only_fields = ['id', 'slug', 'owner', 'created_at']

    def get_member_count(self, obj):
        return obj.members.filter(status='active').count()


class ClinicWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        exclude = ['owner', 'slug', 'created_at', 'updated_at']


class ClinicMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    added_by_name = serializers.CharField(source='added_by.name', read_only=True)

    class Meta:
        model = ClinicMember
        fields = [
            'id', 'clinic', 'clinic_name', 'user', 'member_role', 'status',
            'department', 'joined_at', 'left_at', 'notes',
            'added_by_name', 'invite_accepted_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'clinic', 'user', 'added_by_name',
            'invite_token', 'invite_accepted_at', 'created_at',
        ]


class AddMemberSerializer(serializers.Serializer):
    """
    Used by clinic owner to add a doctor/lab member/receptionist.
    The user must already be registered in the system.
    """
    contact = serializers.IntegerField(
        help_text="Phone number of the user to add")
    member_role = serializers.ChoiceField(
        choices=ClinicMember.MEMBER_ROLE_CHOICES)
    department = serializers.CharField(required=False, allow_blank=True)
    joined_at = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class UpdateMemberSerializer(serializers.ModelSerializer):
    """Clinic owner updates a member's role, status, or department."""

    class Meta:
        model = ClinicMember
        fields = ['member_role', 'status', 'department', 'joined_at', 'left_at', 'notes']
