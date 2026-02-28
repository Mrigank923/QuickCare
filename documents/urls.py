from django.urls import path
from . import views

urlpatterns = [
    # Document upload & list
    path('', views.DocumentListView.as_view(), name='document-list'),
    path('<uuid:pk>/', views.DocumentDetailView.as_view(), name='document-detail'),

    # Doctor requests consent
    path('consent/request/', views.ConsentRequestView.as_view(), name='consent-request'),

    # Doctor browses patient document metadata (no file URL) before requesting consent
    path('patient-docs/', views.PatientDocumentListForDoctorView.as_view(), name='patient-docs-for-doctor'),

    # Patient views & actions on consent requests
    path('consent/mine/', views.PatientConsentListView.as_view(), name='patient-consent-list'),
    path('consent/<uuid:consent_id>/action/', views.PatientConsentActionView.as_view(), name='consent-action'),

    # Doctor views their own consent requests
    path('consent/doctor/', views.DoctorConsentListView.as_view(), name='doctor-consent-list'),

    # Audit log
    path('access-log/', views.DocumentAccessLogView.as_view(), name='access-log-all'),
    path('<uuid:doc_id>/access-log/', views.DocumentAccessLogView.as_view(), name='access-log-doc'),
]
