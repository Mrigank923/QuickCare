from django.urls import path
from . import views

urlpatterns = [
    # Patient routes
    path('my/', views.PatientAppointmentListView.as_view(), name='patient-appointments'),
    path('my/<int:pk>/', views.PatientAppointmentDetailView.as_view(), name='patient-appointment-detail'),

    # Doctor routes
    path('doctor/', views.DoctorAppointmentListView.as_view(), name='doctor-appointments'),
    path('doctor/<int:pk>/', views.DoctorAppointmentDetailView.as_view(), name='doctor-appointment-detail'),
]
