from django.utils import timezone
from rest_framework import status, permissions, filters
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters
from drf_spectacular.utils import extend_schema, OpenApiParameter

from users.models import Role
from doctors.models import DoctorProfile
from .models import Appointment
from .serializers import (
    AppointmentSerializer, AppointmentCreateSerializer, AppointmentUpdateSerializer
)


# ─────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────

class AppointmentFilter(df_filters.FilterSet):
    date = df_filters.DateFilter(field_name='appointment_date')
    from_date = df_filters.DateFilter(field_name='appointment_date', lookup_expr='gte')
    to_date = df_filters.DateFilter(field_name='appointment_date', lookup_expr='lte')
    status = df_filters.CharFilter(field_name='status')
    doctor = df_filters.NumberFilter(field_name='doctor__id')

    class Meta:
        model = Appointment
        fields = ['date', 'from_date', 'to_date', 'status', 'doctor']


# ─────────────────────────────────────────────
# Patient: Book & Manage Their Appointments
# ─────────────────────────────────────────────

class PatientAppointmentListView(APIView):
    """
    GET  – list all appointments for the logged-in patient
    POST – book a new appointment
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Appointment.objects.filter(patient=request.user).select_related('doctor__user')
        # Optional filters
        status_f = request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        serializer = AppointmentSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Determine fee
            doctor = serializer.validated_data['doctor']
            appt_type = serializer.validated_data.get('appointment_type', 'first_visit')
            fee = doctor.first_visit_fee if appt_type == 'first_visit' else doctor.follow_up_fee

            appointment = serializer.save(patient=request.user, fee_charged=fee)
            return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatientAppointmentDetailView(APIView):
    """Patient: get or cancel a specific appointment."""
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, patient):
        try:
            return Appointment.objects.get(pk=pk, patient=patient)
        except Appointment.DoesNotExist:
            return None

    def get(self, request, pk):
        appt = self.get_object(pk, request.user)
        if not appt:
            return Response({'message': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentSerializer(appt).data)

    def put(self, request, pk):
        """Patient can only cancel their appointment."""
        appt = self.get_object(pk, request.user)
        if not appt:
            return Response({'message': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status and new_status != 'cancelled':
            return Response({'message': 'Patients can only cancel appointments.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = AppointmentUpdateSerializer(appt, data={
            'status': 'cancelled',
            'cancelled_by': 'patient',
            'cancellation_reason': request.data.get('cancellation_reason', ''),
        }, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AppointmentSerializer(appt).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Doctor: View & Manage Their Appointments
# ─────────────────────────────────────────────

class DoctorAppointmentListView(APIView):
    """
    Doctor: view all appointments on their schedule.
    Supports ?date=YYYY-MM-DD and ?status= filters.
    """
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

        qs = Appointment.objects.filter(doctor=doctor).select_related('patient')
        date_f = request.query_params.get('date')
        status_f = request.query_params.get('status')
        if date_f:
            qs = qs.filter(appointment_date=date_f)
        if status_f:
            qs = qs.filter(status=status_f)
        return Response(AppointmentSerializer(qs, many=True).data)


class DoctorAppointmentDetailView(APIView):
    """Doctor: confirm, complete, add notes, or cancel an appointment."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_doctor(self, user):
        try:
            return DoctorProfile.objects.get(user=user)
        except DoctorProfile.DoesNotExist:
            return None

    def get_object(self, pk, doctor):
        try:
            return Appointment.objects.get(pk=pk, doctor=doctor)
        except Appointment.DoesNotExist:
            return None

    def get(self, request, pk):
        doctor = self._get_doctor(request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        appt = self.get_object(pk, doctor)
        if not appt:
            return Response({'message': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentSerializer(appt).data)

    def put(self, request, pk):
        doctor = self._get_doctor(request.user)
        if not doctor:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        appt = self.get_object(pk, doctor)
        if not appt:
            return Response({'message': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        # If doctor is cancelling, record cancelled_by
        if data.get('status') == 'cancelled':
            data['cancelled_by'] = 'doctor'

        serializer = AppointmentUpdateSerializer(appt, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AppointmentSerializer(appt).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# Clinic Owner: Dashboard — today's appointments
# ─────────────────────────────────────────────

@extend_schema(
    tags=['Appointments'],
    parameters=[
        OpenApiParameter('date', str, OpenApiParameter.QUERY,
            description='Date in YYYY-MM-DD format. Defaults to today.', required=False),
        OpenApiParameter('status', str, OpenApiParameter.QUERY,
            description='Filter by status: pending, confirmed, completed, cancelled, no_show',
            required=False),
        OpenApiParameter('doctor_id', int, OpenApiParameter.QUERY,
            description='Filter by a specific doctor (DoctorProfile id)', required=False),
    ]
)
class ClinicAppointmentDashboardView(APIView):
    """
    Clinic Owner 🔒 — see all appointments for their clinic.

    ?date=YYYY-MM-DD  (default: today)
    ?status=confirmed
    ?doctor_id=5

    Response includes:
      - summary counts per status
      - full appointment list ordered by time
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, clinic_id):
        from clinic.models import Clinic, ClinicMember

        # ── Auth: must be the clinic owner ───────────────────────────
        try:
            clinic = Clinic.objects.get(pk=clinic_id, is_active=True)
        except Clinic.DoesNotExist:
            return Response({'message': 'Clinic not found.'}, status=status.HTTP_404_NOT_FOUND)

        if clinic.owner != request.user:
            return Response({'message': 'Only the clinic owner can access this dashboard.'},
                            status=status.HTTP_403_FORBIDDEN)

        # ── Get all active doctors in this clinic ─────────────────────
        from django.db.models import Q
        active_doctor_user_ids = ClinicMember.objects.filter(
            Q(member_role='doctor') | Q(member_role=''),
            clinic=clinic, status='active',
        ).values_list('user_id', flat=True)

        clinic_doctors = DoctorProfile.objects.filter(
            user_id__in=active_doctor_user_ids
        )

        # ── Date filter (default today) ───────────────────────────────
        date_param = request.query_params.get('date')
        if date_param:
            try:
                from datetime import date
                target_date = date.fromisoformat(date_param)
            except ValueError:
                return Response({'message': 'Invalid date format. Use YYYY-MM-DD.'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = timezone.localdate()

        # ── Build queryset ────────────────────────────────────────────
        qs = Appointment.objects.filter(
            doctor__in=clinic_doctors,
            appointment_date=target_date,
        ).select_related('patient', 'doctor__user').order_by('appointment_time')

        # Optional filters
        status_f = request.query_params.get('status')
        doctor_id_f = request.query_params.get('doctor_id')

        if status_f:
            qs = qs.filter(status=status_f)
        if doctor_id_f:
            qs = qs.filter(doctor_id=doctor_id_f)

        # ── Summary counts ────────────────────────────────────────────
        all_today = Appointment.objects.filter(
            doctor__in=clinic_doctors,
            appointment_date=target_date,
        )
        summary = {s: all_today.filter(status=s).count() for s, _ in Appointment.STATUS_CHOICES}
        summary['total'] = all_today.count()

        return Response({
            'clinic': clinic.name,
            'date': str(target_date),
            'summary': summary,
            'appointments': AppointmentSerializer(qs, many=True).data,
        })
