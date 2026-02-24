from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'patient', 'doctor', 'appointment_date', 'appointment_time',
        'appointment_type', 'mode', 'status', 'is_paid', 'fee_charged'
    ]
    list_filter = ['status', 'mode', 'appointment_type', 'is_paid', 'appointment_date']
    search_fields = ['patient__name', 'patient__contact', 'doctor__user__name']
    ordering = ['-appointment_date', '-appointment_time']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status', 'is_paid']
