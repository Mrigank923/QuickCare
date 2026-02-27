from datetime import timedelta, datetime

from django.contrib import admin
from django.utils.html import format_html

from .models import DoctorProfile, DoctorAvailability, DoctorLeave


# ─────────────────────────────────────────────────────────────────────────────
# Inline: availability rows shown directly inside the DoctorProfile change page
# ─────────────────────────────────────────────────────────────────────────────

class DoctorAvailabilityInline(admin.TabularInline):
    model = DoctorAvailability
    extra = 1
    fields = ['clinic', 'day', 'start_time', 'end_time', 'slot_duration_minutes', 'max_patients', 'is_active']
    ordering = ['day', 'start_time']
    verbose_name = "Weekly Schedule Slot"
    verbose_name_plural = "Weekly Schedule (set once — repeats every week automatically)"


class DoctorLeaveInline(admin.TabularInline):
    model = DoctorLeave
    extra = 0
    fields = ['clinic', 'start_date', 'end_date', 'reason']
    ordering = ['-start_date']
    verbose_name = "Leave / Holiday"
    verbose_name_plural = "Leaves / Holidays"


# ─────────────────────────────────────────────────────────────────────────────
# DoctorProfile — includes both inlines
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'doctor_name', 'contact', 'specialty', 'experience_years',
        'first_visit_fee', 'slot_count', 'is_verified', 'is_active',
    ]
    list_filter = ['specialty', 'is_verified', 'is_active', 'offers_video_consultation']
    search_fields = ['user__name', 'user__contact', 'registration_number']
    list_editable = ['is_verified', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DoctorAvailabilityInline, DoctorLeaveInline]

    @admin.display(description='Doctor')
    def doctor_name(self, obj):
        return f"Dr. {obj.user.name}"

    @admin.display(description='Contact')
    def contact(self, obj):
        return obj.user.contact

    @admin.display(description='Schedule Slots')
    def slot_count(self, obj):
        count = obj.availability.filter(is_active=True).count()
        if count == 0:
            return format_html('<span style="color:red;">⚠ No slots set</span>')
        return format_html('<span style="color:green;">✔ {} day(s)</span>', count)


# ─────────────────────────────────────────────────────────────────────────────
# DoctorAvailability — standalone list so admin can also filter/sort globally
# ─────────────────────────────────────────────────────────────────────────────

DAY_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = [
        'doctor', 'clinic', 'day_display', 'start_time', 'end_time',
        'slot_duration_minutes', 'computed_slots', 'max_patients', 'is_active',
    ]
    list_filter = ['day', 'is_active', 'clinic']
    search_fields = ['doctor__user__name', 'clinic__name']
    list_editable = ['is_active']
    ordering = ['doctor', 'day', 'start_time']

    @admin.display(description='Day', ordering='day')
    def day_display(self, obj):
        return obj.day.capitalize()

    @admin.display(description='Slots / session')
    def computed_slots(self, obj):
        """How many appointment slots fit in this time block."""
        if obj.slot_duration_minutes and obj.start_time and obj.end_time:
            start = datetime.combine(datetime.today(), obj.start_time)
            end = datetime.combine(datetime.today(), obj.end_time)
            duration = (end - start).seconds // 60
            if duration > 0:
                return duration // obj.slot_duration_minutes
        return '—'


# ─────────────────────────────────────────────────────────────────────────────
# DoctorLeave
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(DoctorLeave)
class DoctorLeaveAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'clinic', 'start_date', 'end_date', 'days_off', 'reason']
    list_filter = ['clinic', 'start_date']
    search_fields = ['doctor__user__name', 'clinic__name']
    ordering = ['-start_date']

    @admin.display(description='Days Off')
    def days_off(self, obj):
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return '—'
