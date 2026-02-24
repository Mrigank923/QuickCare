from django.urls import path
from . import views

urlpatterns = [
    # Public doctor listing & detail
    path('', views.DoctorListView.as_view(), name='doctor-list'),
    path('<int:pk>/', views.DoctorDetailView.as_view(), name='doctor-detail'),

    # Doctor manages own profile
    path('me/', views.MyDoctorProfile.as_view(), name='my-doctor-profile'),

    # Doctor availability (schedule)
    path('<int:doctor_id>/availability/', views.DoctorAvailabilityView.as_view(), name='doctor-availability'),
    path('<int:doctor_id>/availability/slots/', views.DoctorAvailableSlotsView.as_view(), name='doctor-available-slots'),

    # Doctor leaves
    path('me/leaves/', views.DoctorLeaveView.as_view(), name='doctor-leave-list'),
    path('me/leaves/<int:leave_id>/', views.DoctorLeaveView.as_view(), name='doctor-leave-delete'),
]
