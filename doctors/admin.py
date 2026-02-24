from django.contrib import admin
from .models import DoctorProfile, DoctorAvailability, DoctorLeave


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialty', 'experience_years',
                    'first_visit_fee', 'is_verified', 'is_active']
    list_filter = ['specialty', 'is_verified', 'is_active', 'offers_video_consultation']
    search_fields = ['user__name', 'user__contact', 'registration_number']
    list_editable = ['is_verified', 'is_active']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'day', 'start_time', 'end_time', 'slot_duration_minutes', 'max_patients', 'is_active']
    list_filter = ['day', 'is_active']
    search_fields = ['doctor__user__name']


@admin.register(DoctorLeave)
class DoctorLeaveAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'start_date', 'end_date', 'reason']
    search_fields = ['doctor__user__name']
