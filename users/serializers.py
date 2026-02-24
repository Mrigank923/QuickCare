from rest_framework import serializers
from .models import User, UserAddress, Role, PatientMedicalProfile


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'age', 'gender', 'blood_group',
            'roles', 'contact', 'avatar',
            'is_partial_onboarding', 'is_complete_onboarding', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']


class UserCreateSerializer(serializers.ModelSerializer):
    """Used for registration and profile update."""
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'age', 'gender', 'blood_group',
            'roles', 'contact', 'avatar', 'password',
            'is_partial_onboarding', 'is_complete_onboarding',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = '__all__'
        read_only_fields = ['user']


# ─────────────────────────────────────────────────────────────
# Onboarding Serializers
# ─────────────────────────────────────────────────────────────

class PatientStep1Serializer(serializers.Serializer):
    """
    Patient Step 1: collect contact, name, password (after OTP verify).
    Creates the User account with is_partial_onboarding=True.
    """
    contact = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_contact(self, value):
        if User.objects.filter(contact=value).exists():
            raise serializers.ValidationError('A user with this contact already exists.')
        return value


class PatientStep2Serializer(serializers.Serializer):
    """
    Patient Step 2: basic + medical details — completes onboarding.
    """
    # Basic details
    gender = serializers.ChoiceField(choices=['male', 'female', 'others'])
    age = serializers.IntegerField(min_value=0, max_value=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    blood_group = serializers.ChoiceField(
        choices=['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
        required=False, allow_blank=True)

    # Address (optional but encouraged)
    address_area = serializers.CharField(required=False, allow_blank=True)
    house_no = serializers.CharField(required=False, allow_blank=True)
    town = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    pincode = serializers.CharField(required=False, allow_blank=True)
    landmark = serializers.CharField(required=False, allow_blank=True)

    # Medical details
    allergies = serializers.CharField(required=False, allow_blank=True)
    chronic_conditions = serializers.CharField(required=False, allow_blank=True)
    current_medications = serializers.CharField(required=False, allow_blank=True)
    past_surgeries = serializers.CharField(required=False, allow_blank=True)
    family_history = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_number = serializers.IntegerField(required=False, allow_null=True)
    height_cm = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    weight_kg = serializers.DecimalField(
        required=False, allow_null=True, max_digits=5, decimal_places=2)


class PatientMedicalProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientMedicalProfile
        exclude = ['user']


class ClinicOwnerStep1Serializer(serializers.Serializer):
    """
    Clinic Owner Step 1: contact, name, password.
    Creates User with role=IS_CLINIC_OWNER and is_partial_onboarding=True.
    """
    contact = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_contact(self, value):
        if User.objects.filter(contact=value).exists():
            raise serializers.ValidationError('A user with this contact already exists.')
        return value
