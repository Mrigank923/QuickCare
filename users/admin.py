from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from .models import User, UserAddress, Role, PatientMedicalProfile, OTPLog, TempPasswordLog


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['contact', 'name', 'email', 'roles', 'is_active',
                    'is_partial_onboarding', 'is_complete_onboarding', 'date_joined']
    list_filter = ['roles', 'is_active', 'gender', 'is_complete_onboarding']
    search_fields = ['contact', 'name', 'email']
    ordering = ['-date_joined']
    fieldsets = (
        (None, {'fields': ('contact', 'password')}),
        ('Personal Info', {'fields': ('name', 'email', 'age', 'gender', 'blood_group', 'avatar')}),
        ('Roles & Status', {'fields': ('roles', 'is_active', 'is_staff', 'is_partial_onboarding', 'is_complete_onboarding')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('contact', 'name', 'roles', 'password1', 'password2'),
        }),
    )


@admin.register(PatientMedicalProfile)
class PatientMedicalProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'height_cm', 'weight_kg', 'emergency_contact_name', 'updated_at']
    search_fields = ['user__name', 'user__contact', 'chronic_conditions', 'allergies']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'address_type', 'town', 'state', 'pincode', 'is_current']
    list_filter = ['address_type', 'is_current']
    search_fields = ['user__contact', 'user__name', 'town', 'pincode']


@admin.register(OTPLog)
class OTPLogAdmin(admin.ModelAdmin):
    list_display = ['contact', 'otp', 'purpose', 'is_used', 'is_expired', 'created_at', 'expires_at']
    list_filter = ['purpose', 'is_used']
    search_fields = ['contact']
    readonly_fields = ['contact', 'otp', 'purpose', 'created_at', 'expires_at', 'is_used']
    ordering = ['-created_at']

    def is_expired(self, obj):
        return timezone.now() > obj.expires_at
    is_expired.boolean = True
    is_expired.short_description = 'Expired?'

    def has_add_permission(self, request):
        return False  # OTPs are created by the system, not manually


@admin.register(TempPasswordLog)
class TempPasswordLogAdmin(admin.ModelAdmin):
    list_display = ['contact', 'temp_password', 'added_by', 'is_used', 'created_at']
    list_filter = ['is_used']
    search_fields = ['contact', 'added_by__name', 'added_by__contact']
    readonly_fields = ['contact', 'temp_password', 'added_by', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False  # Created automatically by the system
