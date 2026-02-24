import pyotp
import base64
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status, permissions, filters
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from decouple import config

from .models import User, UserAddress, Role
from .serializers import UserSerializer, UserCreateSerializer, UserAddressSerializer

User = get_user_model()

MASTER_OTP = config('MASTER_OTP', default='')


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
