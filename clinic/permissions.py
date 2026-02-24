from rest_framework.permissions import BasePermission
from .models import Clinic, ClinicMember


class IsClinicOwner(BasePermission):
    """
    Allows access only to the owner of the clinic being accessed.
    Expects the view to set `self.clinic` or the URL to have `clinic_id`.
    """
    message = "You must be the clinic owner to perform this action."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # obj can be a Clinic or a ClinicMember
        if isinstance(obj, Clinic):
            return obj.owner == request.user
        if isinstance(obj, ClinicMember):
            return obj.clinic.owner == request.user
        return False


class IsClinicOwnerOrReadOnly(BasePermission):
    """
    Read-only for any authenticated user; write only for clinic owner.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True
        clinic = obj if isinstance(obj, Clinic) else getattr(obj, 'clinic', None)
        return clinic and clinic.owner == request.user
