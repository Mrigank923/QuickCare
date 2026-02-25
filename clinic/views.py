from django.utils import timezone
from rest_framework import status, permissions, filters
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User, Role
from users.views import generate_temp_password, send_temp_password
from doctors.models import DoctorProfile
from .models import Clinic, ClinicMember, ClinicTimeSlot
from .serializers import (
    ClinicSerializer, ClinicWriteSerializer,
    ClinicMemberSerializer, AddMemberSerializer, UpdateMemberSerializer,
    ClinicTimeSlotSerializer, ClinicTimeSlotWriteSerializer,
    ClinicOnboardingStep2Serializer,
)
from .permissions import IsClinicOwner


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _get_clinic_or_403(clinic_id, user):
    """
    Returns (clinic, error_response).
    Ensures the requesting user is the owner of the clinic.
    """
    try:
        clinic = Clinic.objects.get(pk=clinic_id)
    except Clinic.DoesNotExist:
        return None, Response({'message': 'Clinic not found.'}, status=status.HTTP_404_NOT_FOUND)
    if clinic.owner != user:
        return None, Response(
            {'message': 'You are not the owner of this clinic.'},
            status=status.HTTP_403_FORBIDDEN
        )
    return clinic, None


# ─────────────────────────────────────────────
# Clinic CRUD (Owner)
# ─────────────────────────────────────────────

class ClinicListCreateView(APIView):
    """
    GET  – list all clinics owned by the current user
    POST – create a new clinic (logged-in user becomes owner)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        clinics = Clinic.objects.filter(owner=request.user, is_active=True)
        return Response(ClinicSerializer(clinics, many=True).data)

    def post(self, request):
        serializer = ClinicWriteSerializer(data=request.data)
        if serializer.is_valid():
            clinic = serializer.save(owner=request.user)
            return Response(ClinicSerializer(clinic).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClinicDetailView(APIView):
    """
    GET    – public clinic profile
    PUT    – owner updates clinic details
    DELETE – owner deactivates clinic (soft delete)
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(pk=clinic_id, is_active=True)
        except Clinic.DoesNotExist:
            return Response({'message': 'Clinic not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ClinicSerializer(clinic).data)

    def put(self, request, clinic_id):
        clinic, err = _get_clinic_or_403(clinic_id, request.user)
        if err:
            return err
        serializer = ClinicWriteSerializer(clinic, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ClinicSerializer(clinic).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, clinic_id):
        clinic, err = _get_clinic_or_403(clinic_id, request.user)
        if err:
            return err
        clinic.is_active = False
        clinic.save(update_fields=['is_active'])
        return Response({'message': 'Clinic deactivated.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# Member Management (Add / List / Update / Remove)
# ─────────────────────────────────────────────

class ClinicMemberListView(APIView):
    """
    GET  – list all members of the clinic (owner only)
    POST – add a new doctor / lab member / receptionist by contact number
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, clinic_id):
        clinic, err = _get_clinic_or_403(clinic_id, request.user)
        if err:
            return err

        role_filter = request.query_params.get('role')   # doctor | lab_member | receptionist
        status_filter = request.query_params.get('status', 'active')

        qs = ClinicMember.objects.filter(clinic=clinic).select_related('user')
        if role_filter:
            qs = qs.filter(member_role=role_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response(ClinicMemberSerializer(qs, many=True).data)

    def post(self, request, clinic_id):
        """
        Add a member by their contact number.
        - If the user does NOT exist → auto-create account with 8-digit temp password,
          send password to their contact, set is_partial_onboarding=True.
        - If the user already exists → add to clinic directly (status=active).
        - Doctors are enforced to belong to only ONE clinic at a time.
        - Auto-creates DoctorProfile for doctors.
        """
        clinic, err = _get_clinic_or_403(clinic_id, request.user)
        if err:
            return err

        serializer = AddMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        contact = data['contact']
        member_role = data['member_role']

        # Map member_role → system Role
        role_map = {
            'doctor': Role.IS_DOCTOR,
            'lab_member': Role.IS_LAB_MEMBER,
            'receptionist': Role.IS_RECEPTIONIST,
        }
        system_role_id = role_map[member_role]

        # ── Enforce: a doctor can only belong to one clinic ──────────
        if member_role == 'doctor':
            existing_user = User.objects.filter(contact=contact).first()
            if existing_user:
                active_elsewhere = ClinicMember.objects.filter(
                    user=existing_user,
                    member_role='doctor',
                    status='active',
                ).exclude(clinic=clinic).first()
                if active_elsewhere:
                    return Response(
                        {
                            'message': (
                                f'This doctor is already an active member of '
                                f'"{active_elsewhere.clinic.name}". '
                                f'A doctor can only belong to one clinic at a time.'
                            )
                        },
                        status=status.HTTP_409_CONFLICT
                    )

        # ── Get or auto-create the user ───────────────────────────────
        user = User.objects.filter(contact=contact).first()
        is_new_user = False

        if not user:
            # Auto-create with temp password
            temp_password = generate_temp_password()
            role_obj = Role.objects.get(id=system_role_id)
            user = User.objects.create_user(
                contact=contact,
                password=temp_password,
                name=data.get('name', ''),
                roles=role_obj,
                is_partial_onboarding=True,
                is_complete_onboarding=False,
            )
            send_temp_password(contact, temp_password, added_by=request.user)
            is_new_user = True
        else:
            # Existing user — update their role if they were previously a patient
            if user.roles_id not in (Role.IS_DOCTOR, Role.IS_LAB_MEMBER, Role.IS_RECEPTIONIST):
                role_obj = Role.objects.get(id=system_role_id)
                user.roles = role_obj
                user.is_partial_onboarding = True
                user.is_complete_onboarding = False
                user.save(update_fields=['roles', 'is_partial_onboarding', 'is_complete_onboarding'])

        # Prevent adding the clinic owner as a member
        if user == request.user:
            return Response(
                {'message': 'Clinic owner cannot be added as a member.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Check for existing (even inactive) membership ─────────────
        existing = ClinicMember.objects.filter(clinic=clinic, user=user).first()
        if existing:
            if existing.status == 'active':
                return Response(
                    {'message': f'{user.name or contact} is already an active member of this clinic.'},
                    status=status.HTTP_409_CONFLICT
                )
            # Re-activate previously removed member
            existing.status = 'active'
            existing.member_role = member_role
            existing.department = data.get('department', existing.department)
            existing.joined_at = data.get('joined_at', existing.joined_at)
            existing.notes = data.get('notes', existing.notes)
            existing.added_by = request.user
            existing.left_at = None
            existing.save()
            if member_role == 'doctor':
                DoctorProfile.objects.get_or_create(user=user)
            return Response(ClinicMemberSerializer(existing).data, status=status.HTTP_200_OK)

        # ── Create new membership ─────────────────────────────────────
        member = ClinicMember.objects.create(
            clinic=clinic,
            user=user,
            member_role=member_role,
            status='active',
            department=data.get('department', ''),
            joined_at=data.get('joined_at', None),
            notes=data.get('notes', ''),
            added_by=request.user,
        )

        # Auto-create DoctorProfile for doctors
        if member_role == 'doctor':
            DoctorProfile.objects.get_or_create(user=user)

        response_data = ClinicMemberSerializer(member).data
        if is_new_user:
            response_data['_info'] = (
                f'New account created. A temporary password has been sent to {contact}. '
                f'They must log in and complete their profile at '
                f'/api/users/onboarding/member/complete/'
            )

        return Response(response_data, status=status.HTTP_201_CREATED)


class ClinicMemberDetailView(APIView):
    """
    GET    – get a single member's details (owner only)
    PUT    – update member role / department / notes (owner only)
    DELETE – remove (deactivate) a member from the clinic
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_member(self, clinic_id, member_id, owner):
        clinic, err = _get_clinic_or_403(clinic_id, owner)
        if err:
            return None, None, err
        try:
            member = ClinicMember.objects.select_related('user', 'clinic').get(
                pk=member_id, clinic=clinic)
        except ClinicMember.DoesNotExist:
            return None, None, Response(
                {'message': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)
        return clinic, member, None

    def get(self, request, clinic_id, member_id):
        _, member, err = self._get_member(clinic_id, member_id, request.user)
        if err:
            return err
        return Response(ClinicMemberSerializer(member).data)

    def put(self, request, clinic_id, member_id):
        _, member, err = self._get_member(clinic_id, member_id, request.user)
        if err:
            return err
        serializer = UpdateMemberSerializer(member, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ClinicMemberSerializer(member).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, clinic_id, member_id):
        """
        Soft-remove: sets status to 'inactive' and records left_at date.
        Does NOT delete the user account.
        """
        _, member, err = self._get_member(clinic_id, member_id, request.user)
        if err:
            return err

        if member.status == 'inactive':
            return Response(
                {'message': 'Member is already inactive.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        import datetime
        member.status = 'inactive'
        member.left_at = datetime.date.today()
        member.save(update_fields=['status', 'left_at', 'updated_at'])

        return Response(
            {'message': f'{member.user.name} has been removed from {member.clinic.name}.'},
            status=status.HTTP_200_OK
        )


# ─────────────────────────────────────────────
# My Clinics (for a doctor / lab member)
# ─────────────────────────────────────────────

class MyClinicMembershipsView(APIView):
    """
    A doctor / lab member views all clinics they belong to.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = ClinicMember.objects.filter(
            user=request.user, status='active'
        ).select_related('clinic')
        return Response(ClinicMemberSerializer(memberships, many=True).data)


# ─────────────────────────────────────────────
# Public: list all active clinics (for patients)
# ─────────────────────────────────────────────

class PublicClinicListView(ListAPIView):
    """
    Public endpoint: patients can browse clinics.
    Supports ?city= and ?name= search.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = ClinicSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'city', 'clinic_type']

    def get_queryset(self):
        qs = Clinic.objects.filter(is_active=True).select_related('owner')
        city = self.request.query_params.get('city')
        clinic_type = self.request.query_params.get('type')
        if city:
            qs = qs.filter(city__icontains=city)
        if clinic_type:
            qs = qs.filter(clinic_type=clinic_type)
        return qs


# ═══════════════════════════════════════════════════════════════
# CLINIC OWNER ONBOARDING — Step 2
# ═══════════════════════════════════════════════════════════════

class ClinicOnboardingStep2(APIView):
    """
    CLINIC OWNER — Step 2 (requires JWT from user onboarding Step 1).

    Creates the clinic and initial time slots in one request.
    Sets the owner's is_complete_onboarding = True.

    POST /api/clinics/onboarding/step2/
    {
        "name": "City Care Clinic",
        "clinic_type": "clinic",
        "phone": "9876543210",
        "email": "citycare@example.com",
        "address": "12, MG Road",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302001",
        "description": "Multi-specialty clinic",
        "time_slots": [
            {"day_of_week": 0, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15},
            {"day_of_week": 0, "start_time": "17:00", "end_time": "20:00", "slot_duration_minutes": 15},
            {"day_of_week": 1, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15}
        ]
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ClinicOnboardingStep2Serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        slots_data = data.pop('time_slots', [])

        # Create the clinic
        clinic = Clinic.objects.create(owner=request.user, **data)

        # Create time slots
        created_slots = []
        for slot in slots_data:
            ts = ClinicTimeSlot.objects.create(clinic=clinic, **slot)
            created_slots.append(ts)

        # Mark owner as fully onboarded
        user = request.user
        user.is_partial_onboarding = False
        user.is_complete_onboarding = True
        user.save(update_fields=['is_partial_onboarding', 'is_complete_onboarding'])

        return Response({
            'message': 'Clinic registration complete! You can now add doctors from your dashboard.',
            'clinic': ClinicSerializer(clinic).data,
            'time_slots': ClinicTimeSlotSerializer(created_slots, many=True).data,
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════
# Clinic Time Slots CRUD (post-onboarding management)
# ═══════════════════════════════════════════════════════════════

class ClinicTimeSlotListView(APIView):
    """
    GET  – list all time slots for a clinic (public)
    POST – add a new time slot (owner only)
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request, clinic_id):
        try:
            clinic = Clinic.objects.get(pk=clinic_id, is_active=True)
        except Clinic.DoesNotExist:
            return Response({'message': 'Clinic not found.'}, status=status.HTTP_404_NOT_FOUND)
        slots = ClinicTimeSlot.objects.filter(clinic=clinic, is_active=True)
        return Response(ClinicTimeSlotSerializer(slots, many=True).data)

    def post(self, request, clinic_id):
        clinic, err = _get_clinic_or_403(clinic_id, request.user)
        if err:
            return err
        serializer = ClinicTimeSlotWriteSerializer(data=request.data)
        if serializer.is_valid():
            slot = serializer.save(clinic=clinic)
            return Response(ClinicTimeSlotSerializer(slot).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClinicTimeSlotDetailView(APIView):
    """
    PUT    – update a time slot (owner only)
    DELETE – deactivate a time slot (owner only)
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_slot(self, clinic_id, slot_id, user):
        clinic, err = _get_clinic_or_403(clinic_id, user)
        if err:
            return None, err
        try:
            slot = ClinicTimeSlot.objects.get(pk=slot_id, clinic=clinic)
        except ClinicTimeSlot.DoesNotExist:
            return None, Response({'message': 'Time slot not found.'}, status=status.HTTP_404_NOT_FOUND)
        return slot, None

    def put(self, request, clinic_id, slot_id):
        slot, err = self._get_slot(clinic_id, slot_id, request.user)
        if err:
            return err
        serializer = ClinicTimeSlotWriteSerializer(slot, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ClinicTimeSlotSerializer(slot).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, clinic_id, slot_id):
        slot, err = self._get_slot(clinic_id, slot_id, request.user)
        if err:
            return err
        slot.is_active = False
        slot.save(update_fields=['is_active'])
        return Response({'message': 'Time slot deactivated.'}, status=status.HTTP_200_OK)
