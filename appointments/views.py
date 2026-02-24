from rest_framework import status, permissions, filters
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters

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
