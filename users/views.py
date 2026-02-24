import pyotp
import base64
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model, authenticate
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from decouple import config

from .models import User, UserAddress, Role, PatientMedicalProfile, OTPLog
from .serializers import (
    UserSerializer, UserCreateSerializer, UserAddressSerializer,
    PatientStep1Serializer, PatientStep2Serializer,
    PatientMedicalProfileSerializer, ClinicOwnerStep1Serializer,
)

User = get_user_model()

MASTER_OTP = config('MASTER_OTP', default='')

# OTP cache timeout — 10 minutes (matches TOTP interval)
OTP_CACHE_TIMEOUT = 600


def generate_base32(contact):
    s = str(contact)
    b = s.encode("UTF-8")
    return base64.b32encode(b)


def send_otp(contact, purpose='patient_register'):
    """Generate and 'send' OTP. Saves to OTPLog for superadmin visibility."""
    totp = pyotp.TOTP(generate_base32(contact), digits=6, interval=OTP_CACHE_TIMEOUT)
    otp = totp.now()
    # TODO: integrate SMS/WhatsApp (e.g. Twilio, MSG91) before production
    print(f"[OTP] Contact: {contact}  OTP: {otp}")
    # Save to DB for superadmin visibility
    OTPLog.objects.create(
        contact=contact,
        otp=otp,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(seconds=OTP_CACHE_TIMEOUT),
    )
    return otp


def verify_otp(contact, otp):
    """Returns True if OTP is valid for the given contact. Marks it as used in the log."""
    totp = pyotp.TOTP(generate_base32(contact), digits=6, interval=OTP_CACHE_TIMEOUT)
    is_valid = (
        totp.verify(otp, valid_window=3, for_time=datetime.now() - timedelta(minutes=1))
        or (MASTER_OTP and otp == MASTER_OTP)
    )
    if is_valid:
        # Mark the most recent unused OTP for this contact as used
        OTPLog.objects.filter(contact=contact, is_used=False).order_by('-created_at').first() and \
            OTPLog.objects.filter(contact=contact, is_used=False).order_by('-created_at').update(is_used=True)
    return is_valid


# ═══════════════════════════════════════════════════════════════
# LOGIN — contact + password (no OTP needed)
# ═══════════════════════════════════════════════════════════════

class LoginView(APIView):
    """
    Standard login with contact number + password.
    No OTP required — credentials are verified against the DB.

    POST /api/users/login/
    {
        "contact": 9876543210,
        "password": "secret123"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        password = request.data.get('password')

        if not contact or not password:
            return Response(
                {'message': 'Contact and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, contact=contact, password=password)
        if not user:
            return Response(
                {'message': 'Invalid contact number or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'message': 'Your account has been deactivated.'},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
# PATIENT ONBOARDING — 3-step registration
# ═══════════════════════════════════════════════════════════════

class PatientRegisterStep1(APIView):
    """
    PATIENT — Step 1.

    Accepts contact + name + password.
    Validates contact is not already registered.
    Stores data in cache and sends OTP to the contact number.

    POST /api/users/onboarding/patient/step1/
    {
        "contact": 9876543210,
        "name": "Rahul Sharma",
        "password": "secret123"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PatientStep1Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        contact = data['contact']

        # Store registration data in cache keyed by contact
        cache.set(f'patient_reg_{contact}', {
            'contact': contact,
            'name': data['name'],
            'password': data['password'],
        }, timeout=OTP_CACHE_TIMEOUT)

        send_otp(contact, purpose='patient_register')

        return Response({
            'message': 'OTP sent to your contact number. Please verify to complete registration.',
            'contact': contact,
            'next_step': '/api/users/onboarding/patient/step2/',
        }, status=status.HTTP_200_OK)


class PatientRegisterStep2(APIView):
    """
    PATIENT — Step 2.

    Verifies OTP. On success, creates the user account and returns JWT.

    POST /api/users/onboarding/patient/step2/
    {
        "contact": 9876543210,
        "otp": "482910"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        otp = request.data.get('otp')

        if not contact or not otp:
            return Response(
                {'message': 'Contact and OTP are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not verify_otp(contact, otp):
            return Response({'message': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve cached registration data
        reg_data = cache.get(f'patient_reg_{contact}')
        if not reg_data:
            return Response(
                {'message': 'Registration session expired. Please start again from Step 1.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Double-check contact not registered during OTP window
        if User.objects.filter(contact=contact).exists():
            return Response(
                {'message': 'This contact is already registered. Please login.'},
                status=status.HTTP_409_CONFLICT
            )

        patient_role = Role.objects.get(id=Role.IS_PATIENT)
        user = User.objects.create_user(
            contact=reg_data['contact'],
            password=reg_data['password'],
            name=reg_data['name'],
            roles=patient_role,
            is_partial_onboarding=True,
            is_complete_onboarding=False,
        )

        # Clear cache
        cache.delete(f'patient_reg_{contact}')

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'OTP verified. Account created! Please complete your profile.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'next_step': '/api/users/onboarding/patient/step3/',
        }, status=status.HTTP_201_CREATED)


class PatientRegisterStep3(APIView):
    """
    PATIENT — Step 3 (requires JWT from Step 2).

    Saves basic details (gender, age, email, blood_group, address)
    and medical details. Sets is_complete_onboarding = True.

    PUT /api/users/onboarding/patient/step3/
    """
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        serializer = PatientStep2Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user

        # 1. Update basic user fields
        user.gender = data.get('gender', user.gender)
        user.age = data.get('age', user.age)
        user.email = data.get('email', user.email)
        user.blood_group = data.get('blood_group', user.blood_group)
        user.is_partial_onboarding = False
        user.is_complete_onboarding = True
        user.save()

        # 2. Create/update home address if any field provided
        address_fields = ['address_area', 'house_no', 'town', 'state', 'pincode', 'landmark']
        if any(data.get(f) for f in address_fields):
            UserAddress.objects.update_or_create(
                user=user,
                address_type='home',
                defaults={
                    'area': data.get('address_area', ''),
                    'house_no': data.get('house_no', ''),
                    'town': data.get('town', ''),
                    'state': data.get('state', ''),
                    'pincode': data.get('pincode', ''),
                    'landmark': data.get('landmark', ''),
                    'is_current': True,
                }
            )

        # 3. Create/update medical profile
        medical_fields = [
            'allergies', 'chronic_conditions', 'current_medications',
            'past_surgeries', 'family_history', 'emergency_contact_name',
            'emergency_contact_number', 'height_cm', 'weight_kg',
        ]
        medical_data = {k: data[k] for k in medical_fields if k in data and data[k] is not None}
        if medical_data:
            PatientMedicalProfile.objects.update_or_create(user=user, defaults=medical_data)

        medical_profile = PatientMedicalProfile.objects.filter(user=user).first()
        return Response({
            'message': 'Registration complete! Welcome to QuickCare.',
            'user': UserSerializer(user).data,
            'medical_profile': PatientMedicalProfileSerializer(medical_profile).data if medical_profile else None,
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════
# CLINIC OWNER ONBOARDING — 3-step registration
# ═══════════════════════════════════════════════════════════════

class ClinicOwnerRegisterStep1(APIView):
    """
    CLINIC OWNER — Step 1.

    Accepts contact + name + password.
    Stores data in cache and sends OTP to the contact number.

    POST /api/users/onboarding/clinic/step1/
    {
        "contact": 9876543210,
        "name": "Dr. Anil Gupta",
        "password": "secret123"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ClinicOwnerStep1Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        contact = data['contact']

        cache.set(f'clinic_reg_{contact}', {
            'contact': contact,
            'name': data['name'],
            'password': data['password'],
        }, timeout=OTP_CACHE_TIMEOUT)

        send_otp(contact, purpose='clinic_register')

        return Response({
            'message': 'OTP sent to your contact number. Please verify to complete registration.',
            'contact': contact,
            'next_step': '/api/users/onboarding/clinic/step2/',
        }, status=status.HTTP_200_OK)


class ClinicOwnerRegisterStep2(APIView):
    """
    CLINIC OWNER — Step 2.

    Verifies OTP. On success, creates the user account and returns JWT.

    POST /api/users/onboarding/clinic/step2/
    {
        "contact": 9876543210,
        "otp": "482910"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        otp = request.data.get('otp')

        if not contact or not otp:
            return Response(
                {'message': 'Contact and OTP are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not verify_otp(contact, otp):
            return Response({'message': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        reg_data = cache.get(f'clinic_reg_{contact}')
        if not reg_data:
            return Response(
                {'message': 'Registration session expired. Please start again from Step 1.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(contact=contact).exists():
            return Response(
                {'message': 'This contact is already registered. Please login.'},
                status=status.HTTP_409_CONFLICT
            )

        owner_role = Role.objects.get(id=Role.IS_CLINIC_OWNER)
        user = User.objects.create_user(
            contact=reg_data['contact'],
            password=reg_data['password'],
            name=reg_data['name'],
            roles=owner_role,
            is_partial_onboarding=True,
            is_complete_onboarding=False,
        )

        cache.delete(f'clinic_reg_{contact}')

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'OTP verified. Account created! Please complete clinic registration.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'next_step': '/api/clinics/onboarding/step3/',
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════
# General User Endpoints
# ═══════════════════════════════════════════════════════════════

class CurrentUser(APIView):
    """Get / update the currently authenticated user's profile."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        serializer = UserCreateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckUserByContact(APIView):
    """Check whether a contact number is already registered."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        contact = request.query_params.get('contact')
        if not contact:
            return Response({'message': 'Contact is required.'}, status=status.HTTP_400_BAD_REQUEST)
        exists = User.objects.filter(contact=contact).exists()
        return Response({'exists': exists}, status=status.HTTP_200_OK)


class ChangePassword(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        password = request.data.get('password')
        if not password:
            return Response({'message': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(password)
        request.user.save()
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """Refresh access token using refresh token."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken as RT
        from rest_framework_simplejwt.exceptions import TokenError
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'message': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RT(refresh_token)
            return Response({'access': str(token.access_token)}, status=status.HTTP_200_OK)
        except TokenError as e:
            return Response({'message': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


# ═══════════════════════════════════════════════════════════════
# User Address
# ═══════════════════════════════════════════════════════════════

class UserAddressList(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        addresses = UserAddress.objects.filter(user=request.user)
        return Response(UserAddressSerializer(addresses, many=True).data)

    def post(self, request):
        serializer = UserAddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserAddressDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return UserAddress.objects.get(pk=pk, user=user)
        except UserAddress.DoesNotExist:
            return None

    def get(self, request, pk):
        addr = self.get_object(pk, request.user)
        if not addr:
            return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserAddressSerializer(addr).data)

    def put(self, request, pk):
        addr = self.get_object(pk, request.user)
        if not addr:
            return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserAddressSerializer(addr, data=request.data, partial=True)
        if serializer.is_valid():
            if request.data.get('is_current'):
                UserAddress.objects.filter(user=request.user).update(is_current=False)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        addr = self.get_object(pk, request.user)
        if not addr:
            return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        addr.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════
# Patient Medical Profile
# ═══════════════════════════════════════════════════════════════

class PatientMedicalProfileView(APIView):
    """GET / PUT the logged-in patient's medical profile."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = PatientMedicalProfile.objects.filter(user=request.user).first()
        if not profile:
            return Response({'message': 'No medical profile found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientMedicalProfileSerializer(profile).data)

    def put(self, request):
        profile, _ = PatientMedicalProfile.objects.get_or_create(user=request.user)
        serializer = PatientMedicalProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



def generate_base32(contact):
    s = str(contact)
    b = s.encode("UTF-8")
    return base64.b32encode(b)


# ─────────────────────────────────────────────
# Auth: OTP Generation & Verification
# ─────────────────────────────────────────────

class GenerateOTP(APIView):
    """Send OTP to an existing user's contact."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        if not contact:
            return Response({'message': 'Contact is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            User.objects.get(contact=contact)
        except User.DoesNotExist:
            return Response({'message': 'No user with this contact.'}, status=status.HTTP_404_NOT_FOUND)

        totp = pyotp.TOTP(generate_base32(contact), digits=6, interval=600)
        otp = totp.now()
        # TODO: integrate SMS/WhatsApp — for MVP print to console
        print(f"[OTP] Contact: {contact}  OTP: {otp}")
        return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)


class GenerateSignupOTP(APIView):
    """Send OTP to any contact (for new registration)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        if not contact:
            return Response({'message': 'Contact is required.'}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(generate_base32(contact), digits=6, interval=600)
        otp = totp.now()
        print(f"[SIGNUP OTP] Contact: {contact}  OTP: {otp}")
        return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)


class VerifyOTP(APIView):
    """Verify OTP and return JWT tokens (login)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        otp = request.data.get('otp')

        if not contact or not otp:
            return Response({'message': 'Contact and OTP are required.'}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(generate_base32(contact), digits=6, interval=600)
        is_valid = (
            totp.verify(otp, valid_window=3, for_time=datetime.now() - timedelta(minutes=1))
            or (MASTER_OTP and otp == MASTER_OTP)  # master OTP for dev
        )

        if not is_valid:
            return Response({'message': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(contact=contact)
        except User.DoesNotExist:
            return Response({'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


class VerifySignupOTP(APIView):
    """Verify OTP for signup flow — does NOT create user, just validates OTP."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        contact = request.data.get('contact')
        otp = request.data.get('otp')

        if not contact or not otp:
            return Response({'message': 'Contact and OTP are required.'}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(generate_base32(contact), digits=6, interval=600)
        is_valid = (
            totp.verify(otp, valid_window=3, for_time=datetime.now() - timedelta(minutes=1))
            or (MASTER_OTP and otp == MASTER_OTP)
        )
        if not is_valid:
            return Response({'message': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'OTP verified. Proceed to registration.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# User CRUD
# ─────────────────────────────────────────────

class RegisterUser(APIView):
    """Create a new user account (after OTP verification)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUser(APIView):
    """Get / update the currently authenticated user's profile."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def put(self, request):
        serializer = UserCreateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckUserByContact(APIView):
    """Check whether a user exists (used before OTP flow)."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        contact = request.query_params.get('contact')
        if not contact:
            return Response({'message': 'Contact is required.'}, status=status.HTTP_400_BAD_REQUEST)
        exists = User.objects.filter(contact=contact).exists()
        return Response({'exists': exists}, status=status.HTTP_200_OK)


class ChangePassword(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        password = request.data.get('password')
        if not password:
            return Response({'message': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(password)
        request.user.save()
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# User Address
# ─────────────────────────────────────────────

class UserAddressList(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        addresses = UserAddress.objects.filter(user=request.user)
        return Response(UserAddressSerializer(addresses, many=True).data)

    def post(self, request):
        serializer = UserAddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserAddressDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return UserAddress.objects.get(pk=pk, user=user)
        except UserAddress.DoesNotExist:
            return None

    def get(self, request, pk):
        addr = self.get_object(pk, request.user)
        if not addr:
            return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserAddressSerializer(addr).data)

    def put(self, request, pk):
        addr = self.get_object(pk, request.user)
        if not addr:
            return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserAddressSerializer(addr, data=request.data, partial=True)
        if serializer.is_valid():
            if request.data.get('is_current'):
                UserAddress.objects.filter(user=request.user).update(is_current=False)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        addr = self.get_object(pk, request.user)
        if not addr:
            return Response({'message': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        addr.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════
# PATIENT ONBOARDING — Two-step registration
# ═══════════════════════════════════════════════════════════════

class PatientRegisterStep1(APIView):
    """
    PATIENT — Step 1 (after OTP is verified).

    Creates the user account with contact + name + password.
    Sets role = IS_PATIENT (3) and is_partial_onboarding = True.

    POST /api/users/onboarding/patient/step1/
    {
        "contact": 9876543210,
        "name": "Rahul Sharma",
        "password": "secret123"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PatientStep1Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        patient_role = Role.objects.get(id=Role.IS_PATIENT)
        user = User.objects.create_user(
            contact=data['contact'],
            password=data['password'],
            name=data['name'],
            roles=patient_role,
            is_partial_onboarding=True,
            is_complete_onboarding=False,
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Step 1 complete. Please fill in your profile details.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'next_step': '/api/users/onboarding/patient/step2/',
        }, status=status.HTTP_201_CREATED)


class PatientRegisterStep2(APIView):
    """
    PATIENT — Step 2 (requires JWT from Step 1).

    Saves basic details (gender, age, address, email, blood_group)
    and medical details. Sets is_complete_onboarding = True.

    PUT /api/users/onboarding/patient/step2/
    {
        "gender": "male",
        "age": 28,
        "email": "rahul@example.com",
        "blood_group": "B+",
        "address_area": "Near City Hospital",
        "house_no": "12A",
        "town": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302001",
        "allergies": "Penicillin",
        "chronic_conditions": "None",
        "current_medications": "None",
        "height_cm": 175,
        "weight_kg": 70.5,
        "emergency_contact_name": "Priya Sharma",
        "emergency_contact_number": 9123456789
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        serializer = PatientStep2Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user

        # 1. Update user basic fields
        user.gender = data.get('gender', user.gender)
        user.age = data.get('age', user.age)
        user.email = data.get('email', user.email)
        user.blood_group = data.get('blood_group', user.blood_group)
        user.is_partial_onboarding = False
        user.is_complete_onboarding = True
        user.save()

        # 2. Create/update address if any address field provided
        address_fields = ['address_area', 'house_no', 'town', 'state', 'pincode', 'landmark']
        has_address = any(data.get(f) for f in address_fields)
        if has_address:
            UserAddress.objects.update_or_create(
                user=user,
                address_type='home',
                defaults={
                    'area': data.get('address_area', ''),
                    'house_no': data.get('house_no', ''),
                    'town': data.get('town', ''),
                    'state': data.get('state', ''),
                    'pincode': data.get('pincode', ''),
                    'landmark': data.get('landmark', ''),
                    'is_current': True,
                }
            )

        # 3. Create/update medical profile
        medical_fields = [
            'allergies', 'chronic_conditions', 'current_medications',
            'past_surgeries', 'family_history', 'emergency_contact_name',
            'emergency_contact_number', 'height_cm', 'weight_kg',
        ]
        medical_data = {k: data[k] for k in medical_fields if k in data and data[k] is not None}
        if medical_data:
            PatientMedicalProfile.objects.update_or_create(
                user=user, defaults=medical_data)

        medical_profile = PatientMedicalProfile.objects.filter(user=user).first()
        return Response({
            'message': 'Registration complete! Welcome to QuickCare.',
            'user': UserSerializer(user).data,
            'medical_profile': PatientMedicalProfileSerializer(medical_profile).data if medical_profile else None,
        }, status=status.HTTP_200_OK)


class PatientMedicalProfileView(APIView):
    """
    GET/PUT the logged-in patient's medical profile.
    GET  /api/users/me/medical-profile/
    PUT  /api/users/me/medical-profile/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = PatientMedicalProfile.objects.filter(user=request.user).first()
        if not profile:
            return Response({'message': 'No medical profile found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientMedicalProfileSerializer(profile).data)

    def put(self, request):
        profile, _ = PatientMedicalProfile.objects.get_or_create(user=request.user)
        serializer = PatientMedicalProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════
# CLINIC OWNER ONBOARDING — Two-step registration
# ═══════════════════════════════════════════════════════════════

class ClinicOwnerRegisterStep1(APIView):
    """
    CLINIC OWNER — Step 1 (after OTP is verified).

    Creates the user account with contact + name + password.
    Sets role = IS_CLINIC_OWNER (7) and is_partial_onboarding = True.

    POST /api/users/onboarding/clinic/step1/
    {
        "contact": 9876543210,
        "name": "Dr. Anil Gupta",
        "password": "secret123"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ClinicOwnerStep1Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        owner_role = Role.objects.get(id=Role.IS_CLINIC_OWNER)
        user = User.objects.create_user(
            contact=data['contact'],
            password=data['password'],
            name=data['name'],
            roles=owner_role,
            is_partial_onboarding=True,
            is_complete_onboarding=False,
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Step 1 complete. Please fill in clinic details and time slots.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'next_step': '/api/clinics/onboarding/step2/',
        }, status=status.HTTP_201_CREATED)
