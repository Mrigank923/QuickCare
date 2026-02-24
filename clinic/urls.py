from django.urls import path
from . import views

urlpatterns = [
    # ── Public ───────────────────────────────────────────────
    path('public/', views.PublicClinicListView.as_view(), name='public-clinic-list'),

    # ── Clinic owner onboarding Step 3 ───────────────────────
    # Step 1 (send OTP)      → POST /api/users/onboarding/clinic/step1/
    # Step 2 (verify OTP)    → POST /api/users/onboarding/clinic/step2/
    # Step 3 (clinic+slots)  → POST /api/clinics/onboarding/step3/
    path('onboarding/step3/', views.ClinicOnboardingStep2.as_view(), name='clinic-onboarding-step3'),

    # ── Clinic owner: CRUD on their clinics ──────────────────
    path('', views.ClinicListCreateView.as_view(), name='clinic-list-create'),
    path('<uuid:clinic_id>/', views.ClinicDetailView.as_view(), name='clinic-detail'),

    # ── Member management (owner only) ───────────────────────
    path('<uuid:clinic_id>/members/', views.ClinicMemberListView.as_view(), name='clinic-member-list'),
    path('<uuid:clinic_id>/members/<uuid:member_id>/', views.ClinicMemberDetailView.as_view(), name='clinic-member-detail'),

    # ── Time slot management ──────────────────────────────────
    path('<uuid:clinic_id>/slots/', views.ClinicTimeSlotListView.as_view(), name='clinic-slot-list'),
    path('<uuid:clinic_id>/slots/<uuid:slot_id>/', views.ClinicTimeSlotDetailView.as_view(), name='clinic-slot-detail'),

    # ── Doctor / lab member: view own clinic memberships ─────
    path('my/memberships/', views.MyClinicMembershipsView.as_view(), name='my-clinic-memberships'),
]
