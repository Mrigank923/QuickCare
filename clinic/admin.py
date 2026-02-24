from django.contrib import admin
from .models import Clinic, ClinicMember


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
