from rest_framework import serializers
from django.utils import timezone
from users.serializers import UserSerializer
from .models import Clinic, ClinicMember, ClinicTimeSlot


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


# ─────────────────────────────────────────────────────────────
# Time Slot Serializers
# ─────────────────────────────────────────────────────────────

class ClinicTimeSlotSerializer(serializers.ModelSerializer):
    day_name = serializers.SerializerMethodField()

    class Meta:
        model = ClinicTimeSlot
        fields = [
            'id', 'day_of_week', 'day_name', 'start_time', 'end_time',
            'slot_duration_minutes', 'max_appointments', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_day_name(self, obj):
        return dict(ClinicTimeSlot.DAY_CHOICES).get(obj.day_of_week, '')


class ClinicTimeSlotWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicTimeSlot
        exclude = ['clinic', 'created_at']

    def validate(self, data):
        if data.get('start_time') and data.get('end_time'):
            if data['start_time'] >= data['end_time']:
                raise serializers.ValidationError('start_time must be before end_time.')
        return data


# ─────────────────────────────────────────────────────────────
# Clinic Onboarding Step 2 Serializer
# ─────────────────────────────────────────────────────────────

class ClinicOnboardingStep2Serializer(serializers.Serializer):
    """
    Clinic owner Step 2: create clinic + initial time slots together.
    """
    # Clinic fields
    name = serializers.CharField(max_length=200)
    clinic_type = serializers.ChoiceField(
        choices=['clinic', 'hospital', 'diagnostic_center', 'polyclinic'],
        default='clinic')
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    pincode = serializers.CharField(max_length=10, required=False, allow_blank=True)
    registration_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)

    # Time slots (list of slot objects)
    time_slots = ClinicTimeSlotWriteSerializer(many=True, required=False)
