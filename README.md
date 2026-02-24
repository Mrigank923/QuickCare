# QuickCare — Hospital Management System API

A Django REST Framework backend for managing clinic registrations, appointment booking, and document sharing with patient consent. Built for clinics, hospitals, and diagnostic centres.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework 3.16 |
| Auth | JWT via `djangorestframework-simplejwt` |
| Database | PostgreSQL (Render) / SQLite (local dev) |
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
python -m venv jenv
source jenv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set USE_SQLITE=True for local dev

# 5. Run migrations
python manage.py migrate

# 6. Seed roles
python manage.py shell -c "
from users.models import Role
for id_, name in [(1,'Superadmin'),(2,'Admin'),(3,'Patient'),(4,'Doctor'),(5,'Receptionist'),(6,'Lab Member'),(7,'Clinic Owner')]:
    Role.objects.get_or_create(id=id_, defaults={'name': name})
"

# 7. Create superuser
python manage.py shell -c "
from users.models import User
User.objects.create_superuser(contact=9999999999, password='admin@123', name='Super Admin')
"

# 8. Start server
python manage.py runserver
```

---

## 🔐 Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

Tokens are returned after OTP login or registration. The system uses **contact number** (mobile) as the username — no email needed.

### User Roles

| ID | Role | Description |
|---|---|---|
| 1 | Superadmin | Full system access |
| 2 | Admin | Admin panel access |
| 3 | Patient | Books appointments, owns documents |
| 4 | Doctor | Must belong to a clinic |
| 5 | Receptionist | Clinic staff |
| 6 | Lab Member | Must belong to a clinic |
| 7 | Clinic Owner | Creates & manages clinics, adds doctors |

---

## 🔄 Registration & Login Flows

### Patient Registration (3 steps)
```
Step 1: POST /api/users/onboarding/patient/step1/  → contact + name + password → OTP sent to phone
Step 2: POST /api/users/onboarding/patient/step2/  → contact + otp → account created → 🔑 JWT
Step 3: PUT  /api/users/onboarding/patient/step3/  → fill profile + medical details
```

### Clinic Owner Registration (3 steps)
```
Step 1: POST /api/users/onboarding/clinic/step1/   → contact + name + password → OTP sent to phone
Step 2: POST /api/users/onboarding/clinic/step2/   → contact + otp → account created → 🔑 JWT
Step 3: POST /api/clinics/onboarding/step3/        → clinic details + time slots
```

After Step 3, `is_complete_onboarding = true` and the owner can add doctors from their dashboard.

### Login (existing users — no OTP needed)
```
POST /api/users/login/   → contact + password → verified against DB → 🔑 JWT
```

> OTP is only used during **registration** to verify the phone number is real. After that, login is always contact + password.


---

## 📋 API Reference

**Base URL:** `http://localhost:8000`

All endpoints are prefixed with `/api/`.  
🔒 = requires `Authorization: Bearer <token>`

---

## 👤 Users — `/api/users/`

### Login
```
POST /api/users/login/
```
Standard login with contact + password. No OTP needed — verified directly against the database.

**Request:**
```json
{
  "contact": 9876543210,
  "password": "secret123"
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
    "roles": { "id": 3, "name": "is_patient" },
    "is_complete_onboarding": true
  }
}
```

---

### Refresh Token
```
POST /api/users/token/refresh/
```
**Request:**
```json
{ "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```
**Response `200`:**
```json
{ "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

---

## 🧍 Patient Registration

### Step 1 — Send OTP
```
POST /api/users/onboarding/patient/step1/
```
Accepts contact + name + password. Stores them temporarily and sends OTP to the phone number.

**Request:**
```json
{
  "contact": 9876543210,
  "name": "Rahul Sharma",
  "password": "secret123"
}
```
**Response `200`:**
```json
{
  "message": "OTP sent to your contact number. Please verify to complete registration.",
  "contact": 9876543210,
  "next_step": "/api/users/onboarding/patient/step2/"
}
```

---

### Step 2 — Verify OTP → Account Created
```
POST /api/users/onboarding/patient/step2/
```
Verifies OTP. On success, creates the user account and returns JWT.

**Request:**
```json
{
  "contact": 9876543210,
  "otp": "482910"
}
```
**Response `201`:**
```json
{
  "message": "OTP verified. Account created! Please complete your profile.",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "550e8400-...",
    "name": "Rahul Sharma",
    "contact": 9876543210,
    "roles": { "id": 3, "name": "is_patient" },
    "is_partial_onboarding": true,
    "is_complete_onboarding": false
  },
  "next_step": "/api/users/onboarding/patient/step3/"
}
```

---

### Step 3 — Complete Profile & Medical Details
```
PUT /api/users/onboarding/patient/step3/     🔒
```
Saves basic info (gender, age, email, blood group, address) and medical details. Sets `is_complete_onboarding = true`.

**Request:**
```json
{
  "gender": "male",
  "age": 28,
  "email": "rahul@example.com",
  "blood_group": "B+",
  "address_area": "Near City Hospital",
  "house_no": "12A",
  "town": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302001",
  "landmark": "Opp. SBI Bank",
  "allergies": "Penicillin",
  "chronic_conditions": "None",
  "current_medications": "None",
  "past_surgeries": "Appendectomy 2020",
  "family_history": "Diabetes (father)",
  "height_cm": 175,
  "weight_kg": 70.5,
  "emergency_contact_name": "Priya Sharma",
  "emergency_contact_number": 9123456789
}
```
All fields except `gender` and `age` are optional.

**Response `200`:**
```json
{
  "message": "Registration complete! Welcome to QuickCare.",
  "user": {
    "id": "550e8400-...",
    "name": "Rahul Sharma",
    "gender": "male",
    "age": 28,
    "blood_group": "B+",
    "is_complete_onboarding": true
  },
  "medical_profile": {
    "allergies": "Penicillin",
    "chronic_conditions": "None",
    "height_cm": 175,
    "weight_kg": "70.50",
    "emergency_contact_name": "Priya Sharma",
    "emergency_contact_number": 9123456789
  }
}
```

`blood_group` options: `A+` `A-` `B+` `B-` `AB+` `AB-` `O+` `O-`

---

## 🏥 Clinic Owner Registration

### Step 1 — Send OTP
```
POST /api/users/onboarding/clinic/step1/
```
Accepts contact + name + password. Sends OTP to the phone number.

**Request:**
```json
{
  "contact": 9876543210,
  "name": "Dr. Anil Gupta",
  "password": "secret123"
}
```
**Response `200`:**
```json
{
  "message": "OTP sent to your contact number. Please verify to complete registration.",
  "contact": 9876543210,
  "next_step": "/api/users/onboarding/clinic/step2/"
}
```

---

### Step 2 — Verify OTP → Account Created
```
POST /api/users/onboarding/clinic/step2/
```
Verifies OTP. On success, creates the Clinic Owner account and returns JWT.

**Request:**
```json
{
  "contact": 9876543210,
  "otp": "482910"
}
```
**Response `201`:**
```json
{
  "message": "OTP verified. Account created! Please complete clinic registration.",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "...",
    "name": "Dr. Anil Gupta",
    "roles": { "id": 7, "name": "is_clinic_owner" },
    "is_partial_onboarding": true,
    "is_complete_onboarding": false
  },
  "next_step": "/api/clinics/onboarding/step3/"
}
```

---

### Step 3 — Create Clinic + Time Slots
```
POST /api/clinics/onboarding/step3/     🔒
```
Creates the clinic and sets up weekly appointment time slots in one request. Sets `is_complete_onboarding = true`.

**Request:**
```json
{
  "name": "City Care Clinic",
  "clinic_type": "clinic",
  "phone": "9876543210",
  "email": "citycare@example.com",
  "address": "12, MG Road",
  "city": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302001",
  "registration_number": "RJ-MED-2024-001",
  "description": "Multi-specialty OPD clinic",
  "time_slots": [
    { "day_of_week": 0, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15, "max_appointments": 20 },
    { "day_of_week": 0, "start_time": "17:00", "end_time": "20:00", "slot_duration_minutes": 15, "max_appointments": 15 },
    { "day_of_week": 1, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15, "max_appointments": 20 }
  ]
}
```

`clinic_type`: `clinic` | `hospital` | `diagnostic_center` | `polyclinic`  
`day_of_week`: `0`=Monday `1`=Tuesday `2`=Wednesday `3`=Thursday `4`=Friday `5`=Saturday `6`=Sunday

**Response `201`:**
```json
{
  "message": "Clinic registration complete! You can now add doctors from your dashboard.",
  "clinic": {
    "id": "a1b2c3d4-...",
    "name": "City Care Clinic",
    "slug": "city-care-clinic",
    "clinic_type": "clinic",
    "city": "Jaipur",
    "member_count": 0
  },
  "time_slots": [
    {
      "id": "b2c3d4e5-...",
      "day_of_week": 0,
      "day_name": "Monday",
      "start_time": "09:00:00",
      "end_time": "13:00:00",
      "slot_duration_minutes": 15,
      "max_appointments": 20,
      "is_active": true
    }
  ]
}
```

---

## 👤 User — General Endpoints

### Get / Update Current User
```
GET  /api/users/me/     🔒
PUT  /api/users/me/     🔒
```
**GET Response `200`:**
```json
{
  "id": "550e8400-...",
  "name": "Rahul Sharma",
  "contact": 9876543210,
  "email": "rahul@example.com",
  "age": 28,
  "gender": "male",
  "blood_group": "B+",
  "roles": { "id": 3, "name": "is_patient" },
  "is_partial_onboarding": false,
  "is_complete_onboarding": true
}
```

---

### Get / Update Medical Profile
```
GET  /api/users/me/medical-profile/     🔒
PUT  /api/users/me/medical-profile/     🔒
```
**GET Response `200`:**
```json
{
  "allergies": "Penicillin",
  "chronic_conditions": "None",
  "current_medications": "None",
  "past_surgeries": "Appendectomy 2020",
  "family_history": "Diabetes (father)",
  "height_cm": 175,
  "weight_kg": "70.50",
  "emergency_contact_name": "Priya Sharma",
  "emergency_contact_number": 9123456789,
  "updated_at": "2026-02-24T10:00:00Z"
}
```

---

### Check User by Contact
```
GET /api/users/check/?contact=9876543210
```
**Response `200`:**
```json
{ "exists": true }
```

---

### Change Password
```
PUT /api/users/password/change/     🔒
```
**Request:**
```json
{ "password": "NewSecurePass@123" }
```
**Response `200`:**
```json
{ "message": "Password changed successfully." }
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
  "area": "Vaishali Nagar",
  "house_no": "12A",
  "town": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302021",
  "landmark": "Near SBI",
  "address_type": "home",
  "is_current": true
}
```
`address_type`: `home` | `work`

---

### User Address — Detail
```
GET    /api/users/address/<id>/     🔒
PUT    /api/users/address/<id>/     🔒
DELETE /api/users/address/<id>/     🔒
```

---

## 🏥 Clinics — `/api/clinics/`

> Doctors/lab members **must** belong to a clinic — they cannot operate independently.

### Browse Public Clinics
```
GET /api/clinics/public/
```
Query params: `?city=Jaipur`, `?type=hospital`, `?search=Apollo`

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
> Use `POST /api/clinics/onboarding/step2/` during initial registration. Use this endpoint to create additional clinics later.

---

### Get / Update / Delete Clinic
```
GET    /api/clinics/<clinic_id>/     (Public)
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

**POST Request** (add by contact number — user must already be registered):
```json
{
  "contact": 9988776655,
  "member_role": "doctor",
  "department": "Cardiology",
  "joined_at": "2026-02-24"
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
  "joined_at": "2026-02-24"
}
```
> 📝 Adding a `doctor` member automatically creates a `DoctorProfile` for them.

---

### Get / Update / Remove Member
```
GET    /api/clinics/<clinic_id>/members/<member_id>/     🔒 (Owner)
PUT    /api/clinics/<clinic_id>/members/<member_id>/     🔒 (Owner)
DELETE /api/clinics/<clinic_id>/members/<member_id>/     🔒 (Owner — soft remove)
```
**PUT Request:**
```json
{
  "department": "Neurology",
  "notes": "Visiting doctor, available Tues/Thurs"
}
```
DELETE sets `status = inactive` and records `left_at` date. The user account is not deleted.

---

### Clinic Time Slots — List / Add
```
GET  /api/clinics/<clinic_id>/slots/     (Public)
POST /api/clinics/<clinic_id>/slots/     🔒 (Owner)
```
**POST Request:**
```json
{
  "day_of_week": 5,
  "start_time": "10:00",
  "end_time": "14:00",
  "slot_duration_minutes": 20,
  "max_appointments": 12
}
```
**Response `201`:**
```json
{
  "id": "c3d4e5f6-...",
  "day_of_week": 5,
  "day_name": "Saturday",
  "start_time": "10:00:00",
  "end_time": "14:00:00",
  "slot_duration_minutes": 20,
  "max_appointments": 12,
  "is_active": true
}
```

---

### Clinic Time Slots — Update / Deactivate
```
PUT    /api/clinics/<clinic_id>/slots/<slot_id>/     🔒 (Owner)
DELETE /api/clinics/<clinic_id>/slots/<slot_id>/     🔒 (Owner — deactivates)
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
    "clinic": "a1b2c3d4-...",
    "clinic_name": "Apollo Clinic",
    "member_role": "doctor",
    "status": "active",
    "department": "Cardiology",
    "joined_at": "2026-02-24"
  }
]
```

---

## 👨‍⚕️ Doctors — `/api/doctors/`

### List Doctors (Public)
```
GET /api/doctors/
```
Only returns doctors who are **active members** of at least one clinic.

| Query Param | Example | Description |
|---|---|---|
| `clinic` | `?clinic=a1b2c3d4-...` | Filter by clinic UUID |
| `specialty` | `?specialty=cardiology` | Filter by specialty |
| `min_fee` | `?min_fee=200` | Min first-visit fee |
| `max_fee` | `?max_fee=1000` | Max first-visit fee |
| `video` | `?video=true` | Offers video consult |
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
        "department": "Cardiology"
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
GET  /api/doctors/me/     🔒 (Doctor)
PUT  /api/doctors/me/     🔒 (Doctor)
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

### Doctor Availability
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
`day` options: `monday` `tuesday` `wednesday` `thursday` `friday` `saturday` `sunday`

---

### Available Appointment Slots
```
GET /api/doctors/<doctor_id>/availability/slots/?date=2026-03-01&clinic_id=a1b2c3d4-...
```
**Response `200`:**
```json
{
  "doctor": 1,
  "date": "2026-03-01",
  "available_slots": ["09:00", "09:15", "09:30", "09:45", "10:00"]
}
```

---

### Doctor Leaves
```
GET    /api/doctors/me/leaves/                    🔒 (Doctor)
POST   /api/doctors/me/leaves/                    🔒 (Doctor)
DELETE /api/doctors/me/leaves/<leave_id>/         🔒 (Doctor)
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
    "user": { "name": "Dr. Priya Sharma" },
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
GET   /api/appointments/my/<id>/     🔒 (Patient)
PATCH /api/appointments/my/<id>/     🔒 (Patient — cancel only)
```
**PATCH Request:**
```json
{ "status": "cancelled" }
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
{ "status": "confirmed" }
```
`status` options: `pending` | `confirmed` | `completed` | `cancelled` | `no_show`

---

## 📄 Documents — `/api/documents/`

> Patient owns documents. Doctors must request consent before accessing. All access is logged.

### List / Upload Documents
```
GET  /api/documents/     🔒
POST /api/documents/     🔒
```
**POST Request** (multipart/form-data):
```
file          = <file>
title         = Blood Test Report
document_type = lab_report
description   = CBC report dated 2026-02-20
appointment   = 1   (optional)
```
`document_type`: `prescription` | `lab_report` | `imaging` | `discharge_summary` | `insurance` | `other`

**GET** — Patients see their own docs; Doctors see docs they have active consent for.

---

### Get / Delete Document
```
GET    /api/documents/<uuid>/     🔒
DELETE /api/documents/<uuid>/     🔒 (Owner only — soft delete)
```
> Accessing a document automatically creates an audit log entry.

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

---

### Patient: Grant / Reject / Revoke Consent
```
PATCH /api/documents/consent/<consent_id>/action/     🔒 (Patient)
```
**Request:**
```json
{ "action": "grant" }
```
`action` options: `grant` | `reject` | `revoke`

Consent transitions:
```
pending → granted
pending → rejected
granted → revoked
```

**Response `200`:**
```json
{
  "id": "c3d4e5f6-...",
  "status": "granted",
  "actioned_at": "2026-02-24T11:30:00Z"
}
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
GET /api/documents/access-log/              🔒 (Patient — all their docs)
GET /api/documents/<doc_id>/access-log/     🔒 (Patient — specific doc)
```
**Response `200`:**
```json
[
  {
    "id": "d4e5f6g7-...",
    "document": "550e8400-...",
    "accessed_by": { "id": "...", "name": "Dr. Priya Sharma" },
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
├── users/              # Custom User, OTP auth, JWT, addresses, medical profile
├── clinic/             # Clinic CRUD, member management, time slots
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

```json
{ "message": "Human-readable error description." }
```
Or for field validation:
```json
{ "field_name": ["This field is required."] }
```

| Code | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Missing or invalid token |
| `403` | Authenticated but not authorised |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate member, slot overlap) |

---

## 🔒 Permissions Summary

| Endpoint | Who Can Access |
|---|---|
| `POST /api/users/login/` | Anyone |
| `POST /api/users/token/refresh/` | Anyone |
| `POST /api/users/onboarding/patient/step1/` | Anyone |
| `POST /api/users/onboarding/patient/step2/` | Anyone |
| `PUT /api/users/onboarding/patient/step3/` | Authenticated (partial onboarding) |
| `POST /api/users/onboarding/clinic/step1/` | Anyone |
| `POST /api/users/onboarding/clinic/step2/` | Anyone |
| `POST /api/clinics/onboarding/step3/` | Authenticated Clinic Owner |
| `/api/users/me/` | Logged-in user |
| `/api/users/me/medical-profile/` | Logged-in user |
| `/api/clinics/public/` | Anyone |
| `/api/clinics/<id>/slots/` (GET) | Anyone |
| `/api/clinics/` (CRUD) | Clinic Owner |
| `/api/clinics/<id>/members/` | Clinic Owner |
| `/api/clinics/<id>/slots/` (POST/PUT/DELETE) | Clinic Owner |
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

- **OTP** is only used during **registration** to verify the phone number. It is printed to the server console in dev — integrate an SMS/WhatsApp provider (e.g. Twilio, MSG91) before production.
- **Login** uses contact + password verified directly against the database. No OTP required after registration.
- **`MASTER_OTP`** in `.env` bypasses OTP in development. Leave empty in production.
- **`USE_SQLITE=True`** in `.env` uses local SQLite. Set `USE_SQLITE=False` for PostgreSQL in production.
- **Doctors cannot self-register** — they must be added to a clinic by a Clinic Owner via `POST /api/clinics/<id>/members/`.
- **Document access** is always logged. Doctors can only access a file with an active (non-expired, non-revoked) consent record.
- **Onboarding flags**: `is_partial_onboarding=True` after Step 1, `is_complete_onboarding=True` after Step 2. Frontend can use these to resume an interrupted signup.


---
