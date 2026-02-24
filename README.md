# QuickCare — Hospital Management System API

A Django REST Framework backend for managing online appointment booking and document sharing with patient consent. Built for clinics, hospitals, and diagnostic centres.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework 3.16 |
| Auth | JWT via `djangorestframework-simplejwt` |
| Database | PostgreSQL (Render) |
| OTP | `pyotp` TOTP (6-digit, 10-min window) |
| Config | `python-decouple` (.env) |
| File Uploads | Pillow + Django FileField |

---

## ⚙️ Local Setup

```bash
# 1. Clone & enter project
git clone <repo-url>
cd QuickCare

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Run migrations
python manage.py migrate

# 6. Seed roles
python manage.py shell -c "
from users.models import Role
for id_, name in [(1,'Superadmin'),(2,'Admin'),(3,'Patient'),(4,'Doctor'),(5,'Receptionist'),(6,'Lab Member'),(7,'Clinic Owner')]:
    Role.objects.get_or_create(id=id_, defaults={'name': name})
"

# 7. Start server
python manage.py runserver
```

---

## 🔐 Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

Tokens are obtained via the OTP login flow. The system uses **contact number** (mobile) as the username — no email required.

### User Roles

| ID | Role | Description |
|---|---|---|
| 1 | Superadmin | Full system access |
| 2 | Admin | Admin panel access |
| 3 | Patient | Books appointments, owns documents |
| 4 | Doctor | Must belong to a clinic |
| 5 | Receptionist | Clinic staff |
| 6 | Lab Member | Must belong to a clinic |
| 7 | Clinic Owner | Creates & manages clinics |

---

## 📋 API Reference

**Base URL:** `http://localhost:8000`

All endpoints are prefixed with `/api/`.

---

## 👤 Users — `/api/users/`

### Generate OTP (Login)
```
POST /api/users/otp/generate/
```
Sends OTP to an existing user's contact number.

**Request:**
```json
{
  "contact": 9876543210
}
```
**Response `200`:**
```json
{
  "message": "OTP sent successfully."
}
```

---

### Generate OTP (Signup)
```
POST /api/users/otp/generate/signup/
```
Sends OTP to any contact number (new user registration flow).

**Request:**
```json
{
  "contact": 9876543210
}
```
**Response `200`:**
```json
{
  "message": "OTP sent successfully."
}
```

---

### Verify OTP (Login)
```
POST /api/users/otp/verify/
```
Verifies OTP and returns JWT tokens.

**Request:**
```json
{
  "contact": 9876543210,
  "otp": "482910"
}
```
**Response `200`:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Raj Kumar",
    "contact": 9876543210,
    "roles": 3
  }
}
```

---

### Verify OTP (Signup)
```
POST /api/users/otp/verify/signup/
```
Validates OTP before registration — does **not** create the user.

**Request:**
```json
{
  "contact": 9876543210,
  "otp": "482910"
}
```
**Response `200`:**
```json
{
  "message": "OTP verified. Proceed to registration."
}
```

---

### Refresh Token
```
POST /api/users/token/refresh/
```
**Request:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
**Response `200`:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### Register User
```
POST /api/users/register/
```
Creates a new user account (call after OTP verification).

**Request:**
```json
{
  "name": "Raj Kumar",
  "contact": 9876543210,
  "roles": 3
}
```
**Response `201`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Raj Kumar",
  "contact": 9876543210,
  "roles": 3
}
```

---

### Get / Update Current User
```
GET  /api/users/me/         🔒
PUT  /api/users/me/         🔒
```
**GET Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Raj Kumar",
  "contact": 9876543210,
  "roles": 3,
  "avatar": null,
  "email": null
}
```
**PUT Request:**
```json
{
  "name": "Raj Kumar Updated",
  "email": "raj@example.com"
}
```

---

### Check User by Contact
```
GET /api/users/check/?contact=9876543210
```
Checks if a contact number is already registered.

**Response `200`:**
```json
{
  "exists": true,
  "name": "Raj Kumar"
}
```

---

### Change Password
```
POST /api/users/password/change/     🔒
```
**Request:**
```json
{
  "password": "NewSecurePass@123"
}
```
**Response `200`:**
```json
{
  "message": "Password changed successfully."
}
```

---

### User Address — List / Create
```
GET  /api/users/address/     🔒
POST /api/users/address/     🔒
```
**POST Request:**
```json
{
  "address_line1": "123 MG Road",
  "address_line2": "Near City Mall",
  "city": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302001"
}
```

---

### User Address — Detail
```
GET    /api/users/address/<id>/     🔒
PUT    /api/users/address/<id>/     🔒
DELETE /api/users/address/<id>/     🔒
```

---

## 🏥 Clinics — `/api/clinics/`

> Clinic owners manage their clinics. Doctors/lab members **must** belong to a clinic — they cannot operate independently.

### Browse Public Clinics (No Auth)
```
GET /api/clinics/public/
```
Optional query params: `?clinic_type=hospital`, `?search=Apollo`, `?city=Jaipur`

**Response `200`:**
```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "Apollo Clinic",
    "slug": "apollo-clinic",
    "clinic_type": "clinic",
    "city": "Jaipur",
    "phone": "0141-2222222",
    "member_count": 5
  }
]
```

---

### List / Create My Clinics
```
GET  /api/clinics/     🔒 (Clinic Owner)
POST /api/clinics/     🔒 (Clinic Owner)
```
**POST Request:**
```json
{
  "name": "MedPlus Clinic",
  "clinic_type": "clinic",
  "address": "45 Vaishali Nagar, Jaipur",
  "city": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302021",
  "phone": "9111111111",
  "email": "info@medplus.com"
}
```
`clinic_type` options: `clinic` | `hospital` | `diagnostic_center` | `polyclinic`

**Response `201`:**
```json
{
  "id": "a1b2c3d4-...",
  "name": "MedPlus Clinic",
  "slug": "medplus-clinic",
  "clinic_type": "clinic",
  "city": "Jaipur",
  "member_count": 0
}
```

---

### Get / Update / Delete Clinic
```
GET    /api/clinics/<clinic_id>/     🔒
PUT    /api/clinics/<clinic_id>/     🔒 (Owner only)
DELETE /api/clinics/<clinic_id>/     🔒 (Owner only — soft delete)
```

---

### List / Add Clinic Members
```
GET  /api/clinics/<clinic_id>/members/     🔒 (Owner)
POST /api/clinics/<clinic_id>/members/     🔒 (Owner)
```
**GET** query params: `?role=doctor`, `?status=active`

**POST Request** (add by contact number):
```json
{
  "contact": 9988776655,
  "member_role": "doctor",
  "department": "Cardiology"
}
```
`member_role` options: `doctor` | `lab_member` | `receptionist`

**Response `201`:**
```json
{
  "id": "b2c3d4e5-...",
  "user": {
    "id": "...",
    "name": "Dr. Suresh",
    "contact": 9988776655
  },
  "member_role": "doctor",
  "status": "active",
  "department": "Cardiology",
  "joined_at": "2026-02-24T10:00:00Z"
}
```
> 📝 If `member_role` is `doctor`, a `DoctorProfile` is automatically created for the user.

---

### Get / Update / Remove Member
```
GET    /api/clinics/<clinic_id>/members/<member_id>/     🔒 (Owner)
PUT    /api/clinics/<clinic_id>/members/<member_id>/     🔒 (Owner)
DELETE /api/clinics/<clinic_id>/members/<member_id>/     🔒 (Owner — sets status=inactive)
```
**PUT Request:**
```json
{
  "status": "inactive",
  "department": "Neurology"
}
```

---

### My Clinic Memberships (Doctor / Lab Member)
```
GET /api/clinics/my/memberships/     🔒
```
**Response `200`:**
```json
[
  {
    "id": "b2c3d4e5-...",
    "clinic": {
      "id": "a1b2c3d4-...",
      "name": "Apollo Clinic",
      "city": "Jaipur"
    },
    "member_role": "doctor",
    "status": "active",
    "department": "Cardiology",
    "joined_at": "2026-02-24T10:00:00Z"
  }
]
```

---

## 👨‍⚕️ Doctors — `/api/doctors/`

### List Doctors (Public)
```
GET /api/doctors/
```
Only returns doctors who are **active members** of a clinic.

Query params:
| Param | Example | Description |
|---|---|---|
| `clinic` | `?clinic=a1b2c3d4-...` | Filter by clinic UUID |
| `specialty` | `?specialty=cardiology` | Filter by specialty |
| `min_fee` | `?min_fee=200` | Min first visit fee |
| `max_fee` | `?max_fee=1000` | Max first visit fee |
| `video` | `?video=true` | Offers video consultation |
| `search` | `?search=Dr. Sharma` | Search by name |

**Response `200`:**
```json
[
  {
    "id": 1,
    "user": {
      "id": "...",
      "name": "Dr. Priya Sharma",
      "contact": 9988776655
    },
    "specialty": "cardiology",
    "qualification": "MBBS, MD",
    "experience_years": 8,
    "first_visit_fee": "500.00",
    "follow_up_fee": "300.00",
    "offers_video_consultation": true,
    "clinics": [
      {
        "clinic_id": "a1b2c3d4-...",
        "clinic_name": "Apollo Clinic",
        "city": "Jaipur",
        "department": "Cardiology",
        "joined_at": "2026-02-24"
      }
    ]
  }
]
```

---

### Get Doctor Detail (Public)
```
GET /api/doctors/<id>/
```

---

### Get / Update My Doctor Profile
```
GET /api/doctors/me/     🔒 (Doctor)
PUT /api/doctors/me/     🔒 (Doctor)
```
> Profile is auto-created when a clinic adds you. Use PUT to update professional details.

**PUT Request:**
```json
{
  "specialty": "cardiology",
  "qualification": "MBBS, MD (Cardiology)",
  "registration_number": "RJ-12345",
  "experience_years": 8,
  "biography": "Experienced cardiologist with 8+ years...",
  "languages": "English, Hindi",
  "first_visit_fee": 500,
  "follow_up_fee": 300,
  "offers_video_consultation": true
}
```

---

### Doctor Availability (Schedule)
```
GET  /api/doctors/<doctor_id>/availability/              (Public)
POST /api/doctors/<doctor_id>/availability/     🔒 (Doctor)
```
**POST Request:**
```json
{
  "clinic": "a1b2c3d4-...",
  "day": "monday",
  "start_time": "09:00",
  "end_time": "13:00",
  "slot_duration_minutes": 15,
  "max_patients": 20
}
```
`day` options: `monday` | `tuesday` | `wednesday` | `thursday` | `friday` | `saturday` | `sunday`

---

### Available Appointment Slots
```
GET /api/doctors/<doctor_id>/availability/slots/?date=2026-03-01&clinic_id=a1b2c3d4-...
```
Returns list of available time slots for a specific date.

**Response `200`:**
```json
{
  "doctor": 1,
  "date": "2026-03-01",
  "available_slots": [
    "09:00", "09:15", "09:30", "09:45", "10:00"
  ]
}
```

---

### Doctor Leaves
```
GET    /api/doctors/me/leaves/                  🔒 (Doctor)
POST   /api/doctors/me/leaves/                  🔒 (Doctor)
DELETE /api/doctors/me/leaves/<leave_id>/       🔒 (Doctor)
```
**POST Request:**
```json
{
  "clinic": "a1b2c3d4-...",
  "start_date": "2026-03-10",
  "end_date": "2026-03-15",
  "reason": "Personal leave"
}
```

---

## 📅 Appointments — `/api/appointments/`

### Patient: List / Book Appointments
```
GET  /api/appointments/my/     🔒 (Patient)
POST /api/appointments/my/     🔒 (Patient)
```
**GET** query params: `?status=pending`, `?status=confirmed`

**POST Request:**
```json
{
  "doctor": 1,
  "appointment_date": "2026-03-01",
  "appointment_time": "09:30",
  "appointment_type": "first_visit",
  "mode": "in_clinic",
  "notes": "Chest pain since 2 days"
}
```
`appointment_type`: `first_visit` | `follow_up`  
`mode`: `in_clinic` | `video`

**Response `201`:**
```json
{
  "id": 1,
  "doctor": {
    "id": 1,
    "user": {"name": "Dr. Priya Sharma"},
    "specialty": "cardiology"
  },
  "appointment_date": "2026-03-01",
  "appointment_time": "09:30:00",
  "status": "pending",
  "mode": "in_clinic",
  "fee_charged": "500.00"
}
```

---

### Patient: Get / Cancel Appointment
```
GET    /api/appointments/my/<id>/     🔒 (Patient)
PATCH  /api/appointments/my/<id>/     🔒 (Patient — cancel only)
```
**PATCH Request (cancel):**
```json
{
  "status": "cancelled"
}
```

---

### Doctor: List Appointments
```
GET /api/appointments/doctor/     🔒 (Doctor)
```
Query params: `?date=2026-03-01`, `?status=confirmed`, `?from_date=2026-03-01&to_date=2026-03-07`

---

### Doctor: Get / Update Appointment
```
GET   /api/appointments/doctor/<id>/     🔒 (Doctor)
PATCH /api/appointments/doctor/<id>/     🔒 (Doctor)
```
**PATCH Request:**
```json
{
  "status": "confirmed"
}
```
`status` options: `pending` | `confirmed` | `completed` | `cancelled` | `no_show`

---

## 📄 Documents — `/api/documents/`

> Patient owns documents. Doctors must request consent before accessing them. All access is logged.

### List / Upload Documents
```
GET  /api/documents/     🔒
POST /api/documents/     🔒
```
**POST Request** (multipart/form-data):
```
file         = <file>
title        = Blood Test Report
document_type = lab_report
description  = CBC report dated 2026-02-20
appointment  = 1   (optional)
```
`document_type` options: `prescription` | `lab_report` | `imaging` | `discharge_summary` | `insurance` | `other`

**GET** — Patients see their own docs; Doctors see docs they have active consent for.

---

### Get / Delete Document
```
GET    /api/documents/<uuid>/     🔒
DELETE /api/documents/<uuid>/     🔒 (Owner only — soft delete)
```
> Accessing a document creates an entry in the audit log automatically.

---

### Doctor: Request Document Access
```
POST /api/documents/consent/request/     🔒 (Doctor)
```
**Request:**
```json
{
  "document": "550e8400-e29b-41d4-a716-446655440000",
  "purpose": "Reviewing prior lab results before consultation",
  "expires_at": "2026-03-10T23:59:00Z"
}
```
**Response `201`:**
```json
{
  "id": "c3d4e5f6-...",
  "document": "550e8400-...",
  "doctor": 1,
  "status": "pending",
  "purpose": "Reviewing prior lab results before consultation",
  "expires_at": "2026-03-10T23:59:00Z"
}
```

---

### Patient: View Incoming Consent Requests
```
GET /api/documents/consent/mine/     🔒 (Patient)
```
Query params: `?status=pending`

**Response `200`:**
```json
[
  {
    "id": "c3d4e5f6-...",
    "document": {
      "id": "550e8400-...",
      "title": "Blood Test Report"
    },
    "doctor": {
      "id": 1,
      "user": {"name": "Dr. Priya Sharma"}
    },
    "status": "pending",
    "purpose": "Reviewing prior lab results before consultation",
    "expires_at": "2026-03-10T23:59:00Z"
  }
]
```

---

### Patient: Grant / Reject / Revoke Consent
```
PATCH /api/documents/consent/<consent_id>/action/     🔒 (Patient)
```
**Grant:**
```json
{ "action": "grant" }
```
**Reject:**
```json
{ "action": "reject" }
```
**Revoke** (after granting):
```json
{ "action": "revoke" }
```
**Response `200`:**
```json
{
  "id": "c3d4e5f6-...",
  "status": "granted",
  "actioned_at": "2026-02-24T11:30:00Z"
}
```

Consent state transitions:
```
pending → granted
pending → rejected
granted → revoked
```

---

### Doctor: View My Consent Requests
```
GET /api/documents/consent/doctor/     🔒 (Doctor)
```
Query params: `?status=granted`, `?status=pending`

---

### Document Access Audit Log
```
GET /api/documents/access-log/                  🔒 (Patient — all their docs)
GET /api/documents/<doc_id>/access-log/         🔒 (Patient — specific doc)
```
**Response `200`:**
```json
[
  {
    "id": "d4e5f6g7-...",
    "document": "550e8400-...",
    "accessed_by": {
      "id": "...",
      "name": "Dr. Priya Sharma"
    },
    "accessed_at": "2026-02-24T12:00:00Z",
    "ip_address": "103.21.244.1"
  }
]
```

---

## 🗂️ Project Structure

```
QuickCare/
├── QuickCare/          # Project config (settings, urls, wsgi)
├── users/              # Custom User, OTP auth, JWT, addresses
├── clinic/             # Clinic CRUD, member management
├── doctors/            # Doctor profiles, availability, leaves
├── appointments/       # Appointment booking
├── documents/          # Document upload, consent, audit log
├── .env                # Local secrets (never commit)
├── .env.example        # Template for environment variables
├── requirements.txt    # Python dependencies
└── manage.py
```

---

## 🚦 Error Responses

All errors follow this shape:
```json
{
  "message": "Human-readable error description."
}
```
Or for field validation errors:
```json
{
  "field_name": ["This field is required."]
}
```

| Code | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Missing or invalid token |
| `403` | Authenticated but not authorised |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate slot) |

---

## 🔒 Permissions Summary

| Endpoint Group | Who Can Access |
|---|---|
| OTP & Register | Anyone |
| `/api/users/me/` | Logged-in user |
| `/api/clinics/public/` | Anyone |
| `/api/clinics/` (CRUD) | Clinic Owner |
| `/api/clinics/<id>/members/` | Clinic Owner |
| `/api/clinics/my/memberships/` | Doctor / Lab Member |
| `/api/doctors/` (list/detail) | Anyone |
| `/api/doctors/me/` | Doctor |
| `/api/appointments/my/` | Patient |
| `/api/appointments/doctor/` | Doctor |
| `/api/documents/` | Patient (own) / Doctor (consented) |
| `/api/documents/consent/request/` | Doctor |
| `/api/documents/consent/mine/` | Patient |
| `/api/documents/consent/<id>/action/` | Patient (owner) |
| `/api/documents/consent/doctor/` | Doctor |
| `/api/documents/access-log/` | Patient (own docs) |

---

## 📝 Notes

- **OTP** is printed to the server console in dev. Integrate an SMS/WhatsApp provider (e.g. Twilio, MSG91) before going to production.
- **`MASTER_OTP`** in `.env` allows bypassing OTP in development. Remove or leave empty in production.
- **Doctors cannot self-register** as doctors — they must be added to a clinic by a Clinic Owner via `POST /api/clinics/<id>/members/`.
- **Document access** is always logged. Doctors can only download a file if they have an active (non-expired, non-revoked) consent record.
- **SSL** is enforced on the PostgreSQL connection (`sslmode=require`).
