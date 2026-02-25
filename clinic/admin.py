from django.contrib import admin
from .models import Clinic, ClinicMember, ClinicTimeSlot, ClinicAdmissionDocument


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ['name', 'clinic_type', 'owner', 'city', 'state', 'is_active', 'created_at']
    list_filter = ['clinic_type', 'is_active', 'city']
    search_fields = ['name', 'owner__name', 'owner__contact', 'city', 'registration_number']
    list_editable = ['is_active']
    readonly_fields = ['id', 'slug', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('id', 'name', 'slug', 'clinic_type', 'owner', 'logo', 'description')}),
        ('Contact & Location', {'fields': ('phone', 'email', 'address', 'city', 'state', 'pincode')}),
        ('Registration', {'fields': ('registration_number',)}),
        ('Status', {'fields': ('is_active', 'created_at', 'updated_at')}),
    )


@admin.register(ClinicMember)
class ClinicMemberAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'clinic', 'member_role', 'status', 'department',
        'joined_at', 'left_at', 'added_by', 'created_at'
    ]
    list_filter = ['member_role', 'status', 'clinic']
    search_fields = ['user__name', 'user__contact', 'clinic__name', 'department']
    list_editable = ['status', 'member_role']
    readonly_fields = ['id', 'invite_token', 'invite_accepted_at', 'created_at', 'updated_at']


@admin.register(ClinicTimeSlot)
class ClinicTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['clinic', 'day_of_week', 'start_time', 'end_time',
                    'slot_duration_minutes', 'max_appointments', 'is_active']
    list_filter = ['clinic', 'day_of_week', 'is_active']
    search_fields = ['clinic__name']
    list_editable = ['is_active']
    readonly_fields = ['id', 'created_at']


@admin.register(ClinicAdmissionDocument)
class ClinicAdmissionDocumentAdmin(admin.ModelAdmin):
    list_display = ['clinic', 'document_name', 'document_type', 'is_mandatory', 'created_at']
    list_filter = ['clinic', 'document_type', 'is_mandatory']
    search_fields = ['clinic__name', 'document_name']
    list_editable = ['is_mandatory']
    readonly_fields = ['id', 'created_at', 'updated_at']
