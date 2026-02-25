from django.urls import path
from . import views

urlpatterns = [
    # ── Login (contact + password → JWT) ─────────────────────
    path('login/', views.LoginView.as_view(), name='login'),
    path('token/refresh/', views.RefreshTokenView.as_view(), name='token-refresh'),

    # ── Patient Registration (3 steps) ───────────────────────
    # Step 1: POST contact+name+password → OTP sent
    # Step 2: POST contact+otp           → account created → JWT
    # Step 3: PUT  profile+medical       → onboarding complete
    path('onboarding/patient/step1/', views.PatientRegisterStep1.as_view(), name='patient-step1'),
    path('onboarding/patient/step2/', views.PatientRegisterStep2.as_view(), name='patient-step2'),
    path('onboarding/patient/step3/', views.PatientRegisterStep3.as_view(), name='patient-step3'),

    # ── Clinic Owner Registration (3 steps, Step 3 in clinic app) ──
    # Step 1: POST contact+name+password → OTP sent
    # Step 2: POST contact+otp           → account created → JWT
    # Step 3: POST /api/clinics/onboarding/step3/ → clinic + time slots
    path('onboarding/clinic/step1/', views.ClinicOwnerRegisterStep1.as_view(), name='clinic-owner-step1'),
    path('onboarding/clinic/step2/', views.ClinicOwnerRegisterStep2.as_view(), name='clinic-owner-step2'),

    # ── Clinic Member Onboarding (doctor / lab member / receptionist) ──
    # After clinic owner adds them, they log in and call this to complete profile
    path('onboarding/member/complete/', views.MemberOnboardingView.as_view(), name='member-onboarding'),

    # ── Current user ─────────────────────────────────────────
    path('me/', views.CurrentUser.as_view(), name='current-user'),
    path('me/medical-profile/', views.PatientMedicalProfileView.as_view(), name='medical-profile'),

    # ── Utilities ─────────────────────────────────────────────
    path('check/', views.CheckUserByContact.as_view(), name='check-user'),
    path('password/change/', views.ChangePassword.as_view(), name='change-password'),

    # ── Address ──────────────────────────────────────────────
    path('address/', views.UserAddressList.as_view(), name='address-list'),
    path('address/<int:pk>/', views.UserAddressDetail.as_view(), name='address-detail'),
]
