from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth
    path('otp/generate/', views.GenerateOTP.as_view(), name='generate-otp'),
    path('otp/generate/signup/', views.GenerateSignupOTP.as_view(), name='generate-signup-otp'),
    path('otp/verify/', views.VerifyOTP.as_view(), name='verify-otp'),
    path('otp/verify/signup/', views.VerifySignupOTP.as_view(), name='verify-signup-otp'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # User
    path('register/', views.RegisterUser.as_view(), name='register'),
    path('me/', views.CurrentUser.as_view(), name='current-user'),
    path('check/', views.CheckUserByContact.as_view(), name='check-user'),
    path('password/change/', views.ChangePassword.as_view(), name='change-password'),

    # Address
    path('address/', views.UserAddressList.as_view(), name='address-list'),
    path('address/<int:pk>/', views.UserAddressDetail.as_view(), name='address-detail'),
]
