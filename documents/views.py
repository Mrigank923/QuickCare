from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Document, DocumentConsent, DocumentAccessLog
from .serializers import (
    DocumentSerializer, DocumentUploadSerializer,
    DocumentConsentSerializer, ConsentActionSerializer,
    DocumentAccessLogSerializer, DocumentMetaSerializer,
)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ─────────────────────────────────────────────
# Documents: Upload & List
# ─────────────────────────────────────────────

@extend_schema(
    tags=['Documents'],
    responses={200: DocumentSerializer},
    parameters=[
        OpenApiParameter('document_type', str, OpenApiParameter.QUERY,
            description='Filter by type: prescription, lab_report, scan, discharge_summary, vaccination, insurance, other',
            required=False),
        OpenApiParameter('uploaded_by_role', str, OpenApiParameter.QUERY,
            description='Filter by uploader role: doctor, patient, lab_member',
            required=False),
    ]
)
class DocumentListView(APIView):
    """
    GET  – patient: own documents | doctor: documents they have consent to
    POST – patient or doctor uploads a document for a patient

    Query params (patient only):
      ?document_type=prescription   → prescriptions only
      ?uploaded_by_role=doctor      → docs uploaded by a doctor
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        from users.models import Role
        role_id = user.roles_id

        if role_id == Role.IS_DOCTOR:
            # Doctor sees docs where they have an active granted consent
            from doctors.models import DoctorProfile
            try:
                doctor = DoctorProfile.objects.get(user=user)
            except DoctorProfile.DoesNotExist:
                return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)

            consented_doc_ids = DocumentConsent.objects.filter(
                doctor=doctor, status='granted'
            ).values_list('document_id', flat=True)
            docs = Document.objects.filter(id__in=consented_doc_ids, is_deleted=False)

        elif role_id == Role.IS_LAB_MEMBER:
            # Lab member sees only documents they personally uploaded
            docs = Document.objects.filter(uploaded_by=user, is_deleted=False)

        else:
            # Patient sees their own documents
            docs = Document.objects.filter(owner=user, is_deleted=False)

            # Optional filters
            doc_type = request.query_params.get('document_type')
            uploader_role = request.query_params.get('uploaded_by_role')

            valid_doc_types = [c[0] for c in Document.DOC_TYPE_CHOICES]
            valid_uploader_roles = [c[0] for c in Document.UPLOADED_BY_CHOICES]

            if doc_type:
                if doc_type not in valid_doc_types:
                    return Response(
                        {'message': f'Invalid document_type. Choices: {valid_doc_types}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                docs = docs.filter(document_type=doc_type)

            if uploader_role:
                if uploader_role not in valid_uploader_roles:
                    return Response(
                        {'message': f'Invalid uploaded_by_role. Choices: {valid_uploader_roles}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                docs = docs.filter(uploaded_by_role=uploader_role)

        return Response(DocumentSerializer(docs, many=True).data)

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        from users.models import Role
        role_id = user.roles_id

        # Only doctors, lab members, and patients can upload documents
        allowed_roles = (Role.IS_DOCTOR, Role.IS_LAB_MEMBER, Role.IS_PATIENT)
        if role_id not in allowed_roles:
            return Response(
                {'message': 'You do not have permission to upload documents.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Doctor or Lab Member uploading → patient_id required
        if role_id in (Role.IS_DOCTOR, Role.IS_LAB_MEMBER):
            patient_id = request.data.get('patient_id')
            if not patient_id:
                return Response(
                    {'message': 'patient_id is required when a doctor or lab member uploads a document.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from users.models import User as UserModel
            try:
                owner = UserModel.objects.get(pk=patient_id)
            except UserModel.DoesNotExist:
                return Response({'message': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)
            uploaded_by_role = 'doctor' if role_id == Role.IS_DOCTOR else 'lab_member'
        else:
            # Patient uploads their own document
            owner = user
            uploaded_by_role = 'patient'

        doc = serializer.save(
            owner=owner,
            uploaded_by=user,
            uploaded_by_role=uploaded_by_role,
        )
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Documents'], responses={200: DocumentSerializer})
class DocumentDetailView(APIView):
    """
    GET    – download/view a document (owner or consented doctor)
    DELETE – soft-delete (owner only)
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_document_with_access(self, pk, user):
        """
        Returns (document, consent_or_None, error_response).
        Checks that the user is either the owner or has a granted consent.
        """
        try:
            doc = Document.objects.get(pk=pk, is_deleted=False)
        except Document.DoesNotExist:
            return None, None, Response({'message': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

        if doc.owner == user:
            return doc, None, None  # Owner always has access

        # Check doctor consent
        from doctors.models import DoctorProfile
        try:
            doctor = DoctorProfile.objects.get(user=user)
        except DoctorProfile.DoesNotExist:
            return None, None, Response({'message': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)

        consent = DocumentConsent.objects.filter(
            document=doc, doctor=doctor, status='granted'
        ).first()

        if not consent:
            return None, None, Response(
                {'message': 'Access denied. Request consent from the patient.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check consent expiry
        if consent.expires_at and consent.expires_at < timezone.now():
            consent.status = 'expired'
            consent.save(update_fields=['status'])
            return None, None, Response(
                {'message': 'Your consent for this document has expired.'},
                status=status.HTTP_403_FORBIDDEN
            )

        return doc, consent, None

    def get(self, request, pk):
        doc, consent, err = self._get_document_with_access(pk, request.user)
        if err:
            return err

        # Log access
        DocumentAccessLog.objects.create(
            document=doc,
            accessed_by=request.user,
            consent=consent,
            ip_address=_get_client_ip(request),
        )

        return Response(DocumentSerializer(doc).data)

    def delete(self, request, pk):
        try:
            doc = Document.objects.get(pk=pk, owner=request.user, is_deleted=False)
        except Document.DoesNotExist:
            return Response({'message': 'Document not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)
        doc.is_deleted = True
        doc.save(update_fields=['is_deleted'])
        return Response({'message': 'Document deleted.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# Consent Management
# ─────────────────────────────────────────────

@extend_schema(tags=['Document Consent'], responses={200: DocumentConsentSerializer})
class ConsentRequestView(APIView):
    """
    Doctor requests access to a patient's document.
    POST: { document: <uuid>, purpose: "..." }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from doctors.models import DoctorProfile
        try:
            doctor = DoctorProfile.objects.get(user=request.user)
        except DoctorProfile.DoesNotExist:
            return Response({'message': 'Only doctors can request document access.'}, status=status.HTTP_403_FORBIDDEN)

        doc_id = request.data.get('document')
        purpose = request.data.get('purpose', '')

        try:
            doc = Document.objects.get(pk=doc_id, is_deleted=False)
        except Document.DoesNotExist:
            return Response({'message': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Can't request access to your own patient's already-accessible doc
        existing = DocumentConsent.objects.filter(document=doc, doctor=doctor).first()
        if existing:
            if existing.status == 'granted':
                return Response({'message': 'You already have access to this document.'}, status=status.HTTP_409_CONFLICT)
            # Re-request
            existing.status = 'pending'
            existing.purpose = purpose
            existing.save(update_fields=['status', 'purpose', 'updated_at'])
            return Response(DocumentConsentSerializer(existing).data, status=status.HTTP_200_OK)

        consent = DocumentConsent.objects.create(
            document=doc,
            doctor=doctor,
            patient=doc.owner,
            status='pending',
            purpose=purpose,
        )
        return Response(DocumentConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Document Consent'], responses={200: DocumentConsentSerializer})
class PatientConsentListView(APIView):
    """
    Patient: view all consent requests made for their documents.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        consents = DocumentConsent.objects.filter(
            patient=request.user
        ).select_related('doctor__user', 'document')
        status_filter = request.query_params.get('status')
        if status_filter:
            consents = consents.filter(status=status_filter)
        return Response(DocumentConsentSerializer(consents, many=True).data)


@extend_schema(tags=['Document Consent'], responses={200: DocumentConsentSerializer})
class PatientConsentActionView(APIView):
    """
    Patient: grant, reject, or revoke a consent request.
    PATCH: { action: "granted" | "rejected" | "revoked", expires_at: "..." }
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, consent_id):
        try:
            consent = DocumentConsent.objects.get(pk=consent_id, patient=request.user)
        except DocumentConsent.DoesNotExist:
            return Response({'message': 'Consent not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ConsentActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']
        expires_at = serializer.validated_data.get('expires_at')

        allowed_transitions = {
            'pending':  ['granted', 'rejected'],
            'granted':  ['revoked'],
            'rejected': ['granted'],
            'revoked':  ['granted'],
        }
        if action not in allowed_transitions.get(consent.status, []):
            return Response(
                {'message': f'Cannot change status from "{consent.status}" to "{action}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        consent.status = action
        consent.actioned_at = timezone.now()
        if expires_at:
            consent.expires_at = expires_at
        consent.save(update_fields=['status', 'actioned_at', 'expires_at', 'updated_at'])

        return Response(DocumentConsentSerializer(consent).data)


@extend_schema(tags=['Document Consent'], responses={200: DocumentConsentSerializer})
class DoctorConsentListView(APIView):
    """
    Doctor: view all consent requests they have made.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from doctors.models import DoctorProfile
        try:
            doctor = DoctorProfile.objects.get(user=request.user)
        except DoctorProfile.DoesNotExist:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        consents = DocumentConsent.objects.filter(doctor=doctor).select_related('document', 'patient')
        return Response(DocumentConsentSerializer(consents, many=True).data)


# ─────────────────────────────────────────────
# Doctor browses patient document metadata (no file, no content)
# ─────────────────────────────────────────────

@extend_schema(
    tags=['Document Consent'],
    responses={200: DocumentMetaSerializer},
    parameters=[
        OpenApiParameter('patient_id', str, OpenApiParameter.QUERY,
            description='UUID of the patient whose document list to browse',
            required=True),
    ]
)
class PatientDocumentListForDoctorView(APIView):
    """
    Doctor: browse a patient's document metadata (title, type, id — NO file URL).

    Step 1 of the consent flow:
      1. Doctor calls GET /api/documents/patient-docs/?patient_id=<uuid>
         → sees document titles + types + their current consent_status for each
      2. Doctor picks the doc IDs they need and calls POST /api/documents/consent/request/

    Rules:
      - Only doctors can call this.
      - Returns document title, type, description, upload date, and current consent status.
      - Never returns the file URL — patient privacy is preserved.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from doctors.models import DoctorProfile
        from users.models import Role

        if request.user.roles_id != Role.IS_DOCTOR:
            return Response(
                {'message': 'Only doctors can browse patient documents.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            doctor = DoctorProfile.objects.get(user=request.user)
        except DoctorProfile.DoesNotExist:
            return Response({'message': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        patient_id = request.query_params.get('patient_id', '').strip()
        if not patient_id:
            return Response(
                {'message': 'patient_id query param is required. '
                            'Use GET /api/users/patient/lookup/?contact=<number> first to get the patient UUID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from users.models import User as UserModel
        try:
            patient = UserModel.objects.get(pk=patient_id, roles_id=Role.IS_PATIENT)
        except UserModel.DoesNotExist:
            return Response({'message': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND)

        docs = Document.objects.filter(owner=patient, is_deleted=False).order_by('-created_at')
        serializer = DocumentMetaSerializer(docs, many=True, context={'doctor': doctor})
        return Response({
            'patient': {
                'id': str(patient.id),
                'name': patient.name,
                'contact': patient.contact,
            },
            'documents': serializer.data,
            'total': docs.count(),
        })


@extend_schema(tags=['Documents'], responses={200: DocumentAccessLogSerializer})
class DocumentAccessLogView(APIView):
    """
    Patient: view the full audit trail of who accessed their documents.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, doc_id=None):
        if doc_id:
            try:
                doc = Document.objects.get(pk=doc_id, owner=request.user)
            except Document.DoesNotExist:
                return Response({'message': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)
            logs = DocumentAccessLog.objects.filter(document=doc)
        else:
            # All logs for all patient's documents
            logs = DocumentAccessLog.objects.filter(document__owner=request.user)
        return Response(DocumentAccessLogSerializer(logs, many=True).data)
