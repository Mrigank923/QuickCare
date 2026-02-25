from datetime import date, timedelta, datetime, time

from django.db.models import Q
from rest_framework import status, permissions, filters
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters
from drf_spectacular.utils import extend_schema

from .models import DoctorProfile, DoctorAvailability, DoctorLeave
from .serializers import (
    DoctorProfileSerializer, DoctorProfileWriteSerializer,
    DoctorAvailabilitySerializer, DoctorLeaveSerializer,
)
from appointments.models import Appointment


# ─────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────

class DoctorFilter(df_filters.FilterSet):
    city = df_filters.CharFilter(field_name='clinic_members__clinic__city', lookup_expr='icontains')
    specialty = df_filters.CharFilter(field_name='specialty', lookup_expr='icontains')
    clinic = df_filters.UUIDFilter(field_name='clinic_members__clinic__id')
    min_fee = df_filters.NumberFilter(field_name='first_visit_fee', lookup_expr='gte')
    max_fee = df_filters.NumberFilter(field_name='first_visit_fee', lookup_expr='lte')
    video = df_filters.BooleanFilter(field_name='offers_video_consultation')

    class Meta:
        model = DoctorProfile
        fields = ['specialty', 'min_fee', 'max_fee', 'video']


# ─────────────────────────────────────────────
# Doctor Profile
# ─────────────────────────────────────────────

@extend_schema(tags=['Doctors'], responses={200: DoctorProfileSerializer})
class DoctorListView(ListAPIView):
    """
    Public: list all active, verified doctors that belong to at least one clinic.
    Filter by ?clinic=<uuid>, ?specialty=, ?city=, ?min_fee=, ?max_fee=, ?video=
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = DoctorProfileSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DoctorFilter
    search_fields = ['user__name', 'specialty']
    ordering_fields = ['first_visit_fee', 'experience_years']

    def get_queryset(self):
        # Only list doctors who are active members of at least one clinic
        from clinic.models import ClinicMember
        active_doctor_user_ids = ClinicMember.objects.filter(
            member_role='doctor', status='active'
        ).values_list('user_id', flat=True)

        return DoctorProfile.objects.filter(
            is_active=True,
            is_verified=True,
            user_id__in=active_doctor_user_ids,
        ).select_related('user').prefetch_related('availability').distinct()


@extend_schema(tags=['Doctors'], responses={200: DoctorProfileSerializer})
class DoctorDetailView(APIView):
    """Public: get a single doctor's full profile."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            doctor = DoctorProfile.objects.select_related('user').prefetch_related(
                'availability').get(pk=pk, is_active=True)
        except DoctorProfile.DoesNotExist:
            return Response({'message': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(DoctorProfileSerializer(doctor).data)


@extend_schema(tags=['Doctors'], responses={200: DoctorProfileSerializer})
class MyDoctorProfile(APIView):
    """
    Authenticated doctor: get or create/update own professional profile.
    Note: A DoctorProfile is auto-created when a clinic adds the doctor as a member.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            profile = DoctorProfile.objects.get(user=request.user)
        except DoctorProfile.DoesNotExist:
            return Response(
                {'message': 'No doctor profile found. You must be added to a clinic first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(DoctorProfileSerializer(profile).data)

    def put(self, request):
        """Doctor updates their own professional details."""
        try:
            profile = DoctorProfile.objects.get(user=request.user)
        except DoctorProfile.DoesNotExist:
            return Response({'message': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DoctorProfileWriteSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(DoctorProfileSerializer(profile).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Doctor Availability (Schedule) — per clinic
# ─────────────────────────────────────────────

@extend_schema(tags=['Doctor Availability'], responses={200: DoctorAvailabilitySerializer})
class DoctorAvailabilityView(APIView):
    """
    GET  – public: get a doctor's availability at a specific clinic
           ?clinic_id=<uuid> to filter by clinic (optional)
    POST – doctor adds an availability slot for a clinic they belong to
    PUT  – doctor updates a slot (pass slot_id in request body)
    DELETE – doctor removes a slot (?slot_id=)
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def _get_doctor(self, user=None, pk=None):
        if pk:
            try:
                return DoctorProfile.objects.get(pk=pk)
            except DoctorProfile.DoesNotExist:
                return None
        try:
            return DoctorProfile.objects.get(user=user)
        except DoctorProfile.DoesNotExist:
            return None

    def _verify_clinic_membership(self, doctor, clinic_id):
        """Ensure the doctor is an active member of the given clinic."""
        from clinic.models import ClinicMember
        return ClinicMember.objects.filter(
            user=doctor.user, clinic_id=clinic_id,
            member_role='doctor', status='active'
        ).exists()

    def get(self, request, doctor_id):
        doctor = self._get_doctor(pk=doctor_id)
        if not doctor:
            return Response({'message': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)
        qs = DoctorAvailability.objects.filter(doctor=doctor, is_active=True)
        clinic_id = request.query_params.get('clinic_id')
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)
        return Response(DoctorAvailabilitySerializer(qs, many=True).data)

    def post(self, request, doctor_id=None):
        doctor = self._get_doctor(user=request.user)
        if not doctor:
            return Response(
                {'message': 'Doctor profile not found. Ask your clinic to add you first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        clinic_id = request.data.get('clinic')
        if clinic_id and not self._verify_clinic_membership(doctor, clinic_id):
            return Response(
                {'message': 'You are not an active member of this clinic.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = DoctorAvailabilitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(doctor=doctor)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, doctor_id=None):
        doctor = self._get_doctor(user=request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        slot_id = request.data.get('slot_id')
        try:
            slot = DoctorAvailability.objects.get(pk=slot_id, doctor=doctor)
        except DoctorAvailability.DoesNotExist:
            return Response({'message': 'Slot not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DoctorAvailabilitySerializer(slot, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, doctor_id=None):
        doctor = self._get_doctor(user=request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        slot_id = request.query_params.get('slot_id')
        try:
            slot = DoctorAvailability.objects.get(pk=slot_id, doctor=doctor)
        except DoctorAvailability.DoesNotExist:
            return Response({'message': 'Slot not found.'}, status=status.HTTP_404_NOT_FOUND)
        slot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────
# Available Appointment Slots for a Date
# ─────────────────────────────────────────────

@extend_schema(tags=['Doctor Availability'])
class DoctorAvailableSlotsView(APIView):
    """
    Public: Returns free time slots for a doctor on a given date.
    Query params: ?date=YYYY-MM-DD  &clinic_id=<uuid> (optional)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, doctor_id):
        try:
            doctor = DoctorProfile.objects.get(pk=doctor_id, is_active=True)
        except DoctorProfile.DoesNotExist:
            return Response({'message': 'Doctor not found.'}, status=status.HTTP_404_NOT_FOUND)

        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {'message': 'date query param required (YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            query_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({'message': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check leave
        on_leave = DoctorLeave.objects.filter(
            doctor=doctor, start_date__lte=query_date, end_date__gte=query_date
        ).exists()
        if on_leave:
            return Response({'available_slots': [], 'message': 'Doctor is on leave on this date.'})

        day_name = query_date.strftime('%A').lower()
        qs = DoctorAvailability.objects.filter(doctor=doctor, day=day_name, is_active=True)
        clinic_id = request.query_params.get('clinic_id')
        if clinic_id:
            qs = qs.filter(clinic_id=clinic_id)

        if not qs.exists():
            return Response({'available_slots': [], 'message': 'Doctor is not available on this day.'})

        booked_times = set(
            Appointment.objects.filter(
                doctor=doctor, appointment_date=query_date,
                status__in=['pending', 'confirmed']
            ).values_list('appointment_time', flat=True)
        )

        available_slots = []
        for avail in qs:
            current = datetime.combine(query_date, avail.start_time)
            end = datetime.combine(query_date, avail.end_time)
            delta = timedelta(minutes=avail.slot_duration_minutes)
            while current + delta <= end:
                slot_time = current.time()
                if slot_time not in booked_times:
                    available_slots.append(str(slot_time)[:5])
                current += delta

        return Response({'date': date_str, 'available_slots': available_slots})


# ─────────────────────────────────────────────
# Doctor Leave Management
# ─────────────────────────────────────────────

@extend_schema(tags=['Doctor Availability'], responses={200: DoctorLeaveSerializer})
class DoctorLeaveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_doctor(self, user):
        try:
            return DoctorProfile.objects.get(user=user)
        except DoctorProfile.DoesNotExist:
            return None

    def get(self, request):
        doctor = self._get_doctor(request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        leaves = DoctorLeave.objects.filter(doctor=doctor)
        return Response(DoctorLeaveSerializer(leaves, many=True).data)

    def post(self, request):
        doctor = self._get_doctor(request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = DoctorLeaveSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(doctor=doctor)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, leave_id):
        doctor = self._get_doctor(request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            leave = DoctorLeave.objects.get(pk=leave_id, doctor=doctor)
        except DoctorLeave.DoesNotExist:
            return Response({'message': 'Leave not found.'}, status=status.HTTP_404_NOT_FOUND)
        leave.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
