from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('public/', views.PublicClinicListView.as_view(), name='public-clinic-list'),

    # Clinic owner: CRUD on their clinics
    path('', views.ClinicListCreateView.as_view(), name='clinic-list-create'),
    path('<uuid:clinic_id>/', views.ClinicDetailView.as_view(), name='clinic-detail'),

    # Member management (owner only)
    path('<uuid:clinic_id>/members/', views.ClinicMemberListView.as_view(), name='clinic-member-list'),
    path('<uuid:clinic_id>/members/<uuid:member_id>/', views.ClinicMemberDetailView.as_view(), name='clinic-member-detail'),

    # Doctor / lab member: view their own clinic memberships
    path('my/memberships/', views.MyClinicMembershipsView.as_view(), name='my-clinic-memberships'),
]
