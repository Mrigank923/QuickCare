# QuickCare — Hospital Management System API

A Django REST Framework backend for managing clinic registrations, doctor onboarding, appointment booking, document sharing with patient consent, and SMS-based OTP authentication. Built for clinics, hospitals, and diagnostic centres.

**Production URL:** `https://quickcare-kzis.onrender.com`

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework 3.16 |
| Auth | JWT via `djangorestframework-simplejwt` |
| API Docs | `drf-spectacular` — Swagger UI + ReDoc |
| Database | PostgreSQL (Render) / SQLite (local dev) |
| OTP | `pyotp` TOTP (6-digit, 10-min window) + Twilio SMS |
| SMS | Twilio (`twilio==9.10.2`) |
| File Storage | AWS S3 via `django-storages` + `boto3` (local fallback: `media/`) |
| Config | `python-decouple` (.env) |
| Production | Gunicorn + Whitenoise on Render |

---

## ⚙️ Local Setup

```bash
# 1. Clone & enter project
git clone https://github.com/Mrigank923/QuickCare.git
cd QuickCare

# 2. Create virtual environment
python -m venv jenv
source jenv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — fill in DB, Twilio, AWS keys

# 5. Run migrations
python manage.py migrate

# 6. Seed roles (run once)
python manage.py shell -c "
from users.models import Role
for id_, name in [
    (1,'IS_SUPERADMIN'),(2,'IS_ADMIN'),(3,'IS_PATIENT'),
    (4,'IS_DOCTOR'),(5,'IS_RECEPTIONIST'),(6,'IS_LAB_MEMBER'),(7,'IS_CLINIC_OWNER')
]:
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

### API Docs (local)

| URL | Description |
|---|---|
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/api/schema/` | Raw OpenAPI schema |

---

## 🔑 Environment Variables

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=*

# Database (PostgreSQL)
DB_NAME=quickcare
DB_USER=quickcare_user
DB_PASSWORD=your-db-password
DB_HOST=your-db-host
DB_PORT=5432

# OTP bypass for development (leave empty in production)
MASTER_OTP=888888

# Twilio (SMS delivery for OTP and temp passwords)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# AWS S3 (document storage)
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=your-region-name
```

> If `TWILIO_*` vars are empty → OTP and temp passwords are **printed to the console** (dev mode).
> If `AWS_*` vars are empty → files are stored **locally** in `media/`.

---

## 🔐 Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

Tokens are returned after OTP registration or login. The system uses **contact number** (mobile) as the username — no email required.

### User Roles

| ID | Role | Description |
|---|---|---|
| 1 | Superadmin | Full system access + admin panel |
| 2 | Admin | Admin panel access |
| 3 | Patient | Books appointments, owns documents |
| 4 | Doctor | Added by clinic owner; one clinic at a time |
| 5 | Receptionist | Clinic staff; added by clinic owner |
| 6 | Lab Member | Clinic staff; uploads lab reports for patients |
| 7 | Clinic Owner | Creates and manages clinics, adds staff |

---

## 🔄 Registration & Login Flows

### Patient Registration (3 steps)
```
Step 1: POST  /api/users/onboarding/patient/step1/   contact + name + password → OTP sent via SMS
Step 2: POST  /api/users/onboarding/patient/step2/   contact + otp → account created → JWT returned
Step 3: PATCH /api/users/onboarding/patient/step3/   fill profile + medical details   🔒
```

### Clinic Owner Registration (3 steps)
```
Step 1: POST /api/users/onboarding/clinic/step1/     contact + name + password → OTP sent via SMS
Step 2: POST /api/users/onboarding/clinic/step2/     contact + otp → account created → JWT returned
Step 3: POST /api/clinics/onboarding/step3/          clinic details + time slots   🔒
```

### Clinic Staff Auto-Registration
```
Clinic owner  →  POST /api/clinics/<id>/members/
                   ↓
  If not yet registered → account auto-created + temp password sent via SMS
  is_partial_onboarding = True, is_complete_onboarding = False

Staff logs in  →  POST /api/users/login/   (contact + temp password)
                   ↓  response: { onboarding_required: true, tokens: ... }

Staff completes profile  →  PATCH /api/users/onboarding/member/complete/   🔒
                              ↓  is_complete_onboarding = True, new tokens returned
```

> **One-clinic rule:** A doctor can only be an active member of one clinic at a time.

### Login (all users)
```
POST /api/users/login/   →  contact + password  →  JWT
```

---

## 📋 API Reference

**Base URL (local):** `http://localhost:8000`
**Base URL (production):** `https://quickcare-kzis.onrender.com`

🔒 = requires `Authorization: Bearer <token>`

---

## 👤 Users — `/api/users/`

### Login
```
POST /api/users/login/
```
```json
{ "contact": 9876543210, "password": "secret123" }
```
**Response `200` (fully onboarded):**
```json
{
  "access": "<token>", "refresh": "<token>",
  "user": { "id": "...", "name": "Raj Kumar", "contact": 9876543210, "is_complete_onboarding": true }
}
```
**Response `200` (partial onboarding — clinic staff):**
```json
{
  "message": "Login successful, but your profile is incomplete.",
  "onboarding_required": true,
  "onboarding_url": "/api/users/onboarding/member/complete/",
  "access": "<token>", "refresh": "<token>"
}
```

---

### Refresh Token
```
POST /api/users/token/refresh/
{ "refresh": "<token>" }
```

---

### Patient Registration

**Step 1 — Send OTP**
```
POST /api/users/onboarding/patient/step1/
{ "contact": 9876543210, "name": "Rahul Sharma", "password": "secret123" }
```

**Step 2 — Verify OTP**
```
POST /api/users/onboarding/patient/step2/
{ "contact": 9876543210, "otp": "482910" }
```
Response: JWT tokens + `next_step`

**Step 3 — Complete Profile**
```
PATCH /api/users/onboarding/patient/step3/     🔒
```
```json
{
  "gender": "male", "age": 28, "blood_group": "B+",
  "address_area": "Near City Hospital", "house_no": "12A",
  "town": "Jaipur", "state": "Rajasthan", "pincode": "302001",
  "allergies": "Penicillin", "chronic_conditions": "None",
  "current_medications": "None", "past_surgeries": "Appendectomy 2020",
  "family_history": "Diabetes (father)", "height_cm": 175, "weight_kg": 70.5,
  "emergency_contact_name": "Priya Sharma", "emergency_contact_number": 9123456789
}
```
`blood_group`: `A+` `A-` `B+` `B-` `AB+` `AB-` `O+` `O-`

---

### Clinic Owner Registration

**Step 1**
```
POST /api/users/onboarding/clinic/step1/
{ "contact": 9876543210, "name": "Dr. Anil Gupta", "password": "secret123" }
```

**Step 2**
```
POST /api/users/onboarding/clinic/step2/
{ "contact": 9876543210, "otp": "482910" }
```

---

### Member Onboarding (Doctor / Lab Member / Receptionist)
```
PATCH /api/users/onboarding/member/complete/     🔒
```
```json
{
  "name": "Dr. Suresh Yadav", "gender": "male", "age": 35,
  "specialty": "Cardiology", "qualification": "MBBS, MD", "experience_years": 10,
  "town": "Jaipur", "state": "Rajasthan", "pincode": "302021"
}
```

---

### Current User
```
GET /api/users/me/     🔒
PUT /api/users/me/     🔒
```

### Medical Profile (Patient)
```
GET /api/users/me/medical-profile/     🔒
PUT /api/users/me/medical-profile/     🔒
```

### Utilities
```
GET /api/users/check/?contact=9876543210            (public — { "exists": true/false })
PUT /api/users/password/change/                     🔒  body: { "password": "NewPass@123" }
GET /api/users/patient/lookup/?contact=9876543210   🔒  (Doctor / Lab Member only)
```
**Patient lookup response:**
```json
{ "id": "<uuid>", "name": "Rahul", "contact": 9876543210, "gender": "male", "age": 28, "blood_group": "B+" }
```

### Address
```
GET/POST        /api/users/address/          🔒
GET/PUT/DELETE  /api/users/address/<id>/     🔒
```

---

## 🏥 Clinics — `/api/clinics/`

### Public Clinic Listing
```
GET /api/clinics/public/
```
Query params: `?city=Jaipur`, `?type=hospital`, `?search=Apollo`

Response includes per clinic:
- `doctor_count` — active doctors only
- `staff_count` — all active members (doctors + lab + reception)

---

### Create Clinic — Step 3 of Clinic Owner Onboarding
```
POST /api/clinics/onboarding/step3/     🔒
```
```json
{
  "name": "City Care Clinic", "clinic_type": "clinic",
  "phone": "9876543210", "address": "12, MG Road",
  "city": "Jaipur", "state": "Rajasthan", "pincode": "302001",
  "registration_number": "RJ-MED-2024-001",
  "time_slots": [
    { "day_of_week": 0, "start_time": "09:00", "end_time": "13:00",
      "slot_duration_minutes": 15, "max_appointments": 20 }
  ]
}
```
`clinic_type`: `clinic` | `hospital` | `diagnostic_center` | `polyclinic`
`day_of_week`: `0`=Mon `1`=Tue `2`=Wed `3`=Thu `4`=Fri `5`=Sat `6`=Sun

---

### My Clinics (Owner)
```
GET  /api/clinics/     🔒
POST /api/clinics/     🔒
```

### Clinic Detail
```
GET           /api/clinics/<clinic_id>/     (public)
PUT / DELETE  /api/clinics/<clinic_id>/     🔒 (owner)
```

---

### Member Management (Owner)
```
GET    /api/clinics/<clinic_id>/members/                    🔒
POST   /api/clinics/<clinic_id>/members/                    🔒
GET    /api/clinics/<clinic_id>/members/<member_id>/        🔒
PUT    /api/clinics/<clinic_id>/members/<member_id>/        🔒
DELETE /api/clinics/<clinic_id>/members/<member_id>/        🔒  (soft remove)
```
**POST body:**
```json
{
  "contact": 9988776655, "name": "Dr. Suresh Yadav",
  "member_role": "doctor", "department": "Cardiology", "joined_at": "2026-02-25"
}
```
`member_role`: `doctor` | `receptionist` | `lab_member`

**GET query params:** `?role=doctor`, `?status=active`

---

### Time Slots (Weekly — set once, repeats automatically)
```
GET           /api/clinics/<clinic_id>/slots/                 (public)
POST          /api/clinics/<clinic_id>/slots/                 🔒 (owner)
PUT / DELETE  /api/clinics/<clinic_id>/slots/<slot_id>/       🔒 (owner)
```

---

### My Memberships (Doctor / Lab Member / Receptionist)
```
GET /api/clinics/my/memberships/     🔒
```

---

### Admission Document Requirements
```
GET    /api/clinics/<clinic_id>/admission-docs/                    (public)
GET    /api/clinics/<clinic_id>/admission-docs/?mandatory=true     (public — filter)
POST   /api/clinics/<clinic_id>/admission-docs/                    🔒 (owner)
PUT    /api/clinics/<clinic_id>/admission-docs/<doc_id>/           🔒 (owner)
DELETE /api/clinics/<clinic_id>/admission-docs/<doc_id>/           🔒 (owner)
GET    /api/clinics/<clinic_id>/admission-docs/patient/            🔒 (patient with appointment)
```
The `/patient/` endpoint verifies the patient has an active appointment at that clinic, then returns the checklist split into `mandatory_documents` and `optional_documents`.

---

## 👨‍⚕️ Doctors — `/api/doctors/`

### List Doctors (Public)
```
GET /api/doctors/
```

| Query param | Example | Description |
|---|---|---|
| `clinic` | `?clinic=<uuid>` | Filter by clinic |
| `specialty` | `?specialty=cardiology` | Filter by specialty |
| `min_fee` / `max_fee` | `?min_fee=200&max_fee=800` | Fee range |
| `video` | `?video=true` | Offers video consultation |
| `search` | `?search=Dr. Sharma` | Name search |

### Doctor Detail (Public)
```
GET /api/doctors/<id>/
```

### My Doctor Profile
```
GET /api/doctors/me/     🔒
PUT /api/doctors/me/     🔒
```

### Availability (Weekly Schedule)
```
GET  /api/doctors/<doctor_id>/availability/     (public)
POST /api/doctors/<doctor_id>/availability/     🔒 (Doctor)
```
> Set once per day-of-week. Repeats automatically every week — **no re-entry needed**.

**POST body:**
```json
{
  "clinic": "<clinic_uuid>", "day": "monday",
  "start_time": "09:00", "end_time": "13:00",
  "slot_duration_minutes": 15, "max_patients": 20
}
```
`day`: `monday` `tuesday` `wednesday` `thursday` `friday` `saturday` `sunday`

### Available Appointment Slots
```
GET /api/doctors/<doctor_id>/availability/slots/?date=2026-03-01&clinic_id=<uuid>
```
Returns: `{ "available_slots": ["09:00", "09:15", "09:30", ...] }`

Already-booked slots are automatically excluded.

### Doctor Leaves
```
GET    /api/doctors/me/leaves/                 🔒
POST   /api/doctors/me/leaves/                 🔒
DELETE /api/doctors/me/leaves/<leave_id>/      🔒
```
**POST body:**
```json
{ "clinic": "<uuid>", "start_date": "2026-03-10", "end_date": "2026-03-12", "reason": "Conference" }
```

### Doctor Verification
`is_verified` defaults to `False`. Only superadmin can set it via `/admin/doctors/doctorprofile/`. Unverified doctors are **not visible** in `GET /api/doctors/`.

---

## 📅 Appointments — `/api/appointments/`

### Patient: List / Book
```
GET  /api/appointments/my/     🔒
POST /api/appointments/my/     🔒
```
**POST body:**
```json
{
  "doctor": 1,
  "appointment_date": "2026-03-01",
  "appointment_time": "09:30",
  "appointment_type": "first_visit",
  "mode": "in_clinic",
  "reason": "Chest pain since 2 days"
}
```
`appointment_type`: `first_visit` | `follow_up`
`mode`: `in_clinic` | `video`

**GET query params:** `?status=confirmed`

---

### Patient: Get / Cancel
```
GET   /api/appointments/my/<id>/     🔒
PATCH /api/appointments/my/<id>/     🔒
```
**PATCH (patient can only cancel):**
```json
{ "status": "cancelled", "cancellation_reason": "Schedule conflict" }
```

---

### Doctor: List Appointments
```
GET /api/appointments/doctor/     🔒
```
**Query params:** `?date=2026-03-01`, `?status=confirmed`, `?from_date=...&to_date=...`

---

### Doctor: Get / Update Appointment
```
GET   /api/appointments/doctor/<id>/     🔒
PATCH /api/appointments/doctor/<id>/     🔒
```
**PATCH examples:**
```json
{ "status": "confirmed" }
{ "status": "completed", "notes": "Prescribed antibiotics. Follow up in 5 days." }
{ "status": "no_show" }
{ "status": "cancelled", "cancellation_reason": "Doctor emergency." }
{ "is_paid": true }
```

**Allowed status transitions for doctor:**

| Current status | Can change to |
|---|---|
| `pending` | `confirmed`, `cancelled` |
| `confirmed` | `completed`, `cancelled`, `no_show` |
| `completed` | ❌ terminal |
| `cancelled` | ❌ terminal |
| `no_show` | ❌ terminal |

Invalid transitions return `400` with `{ "message": "...", "allowed_transitions": [...] }`.

---

### Clinic Owner: Appointment Dashboard
```
GET /api/appointments/clinic/<clinic_id>/dashboard/     🔒 (Clinic Owner)
```
**Query params:** `?date=2026-03-01` (default: today), `?status=confirmed`, `?doctor_id=5`

**Response:**
```json
{
  "clinic": "Raj Nursing Home",
  "date": "2026-03-01",
  "summary": {
    "pending": 3, "confirmed": 5, "completed": 2,
    "cancelled": 1, "no_show": 0, "total": 11
  },
  "appointments": [ ... ]
}
```

---

## 📄 Documents — `/api/documents/`

> **PDF only, max 5 MB.** Stored on AWS S3 (presigned URLs valid 1 hour). Patients own their documents. Doctors must request consent before accessing. All access is logged.

### Upload Permissions

| Role | Can Upload? | Requires `patient_id`? | Sees in GET list |
|---|---|---|---|
| Patient | ✅ | ❌ (own docs) | Their own docs |
| Doctor | ✅ | ✅ | Docs with active consent only |
| Lab Member | ✅ | ✅ | Docs they personally uploaded |
| Others | ❌ 403 | — | — |

---

### List / Upload
```
GET  /api/documents/     🔒
POST /api/documents/     🔒  (multipart/form-data)
```
**POST fields:**

| Field | Required | Notes |
|---|---|---|
| `title` | ✅ | e.g. `CBC Report` |
| `document_type` | ✅ | see choices below |
| `file` | ✅ | PDF only, max 5 MB |
| `description` | ❌ | optional |
| `appointment` | ❌ | appointment id |
| `patient_id` | ✅ if doctor/lab | patient's user UUID |

`document_type`: `prescription` | `lab_report` | `scan` | `discharge_summary` | `vaccination` | `insurance` | `other`

**GET query params (patient only):**
```
?document_type=prescription             → prescriptions only
?uploaded_by_role=doctor                → docs uploaded by a doctor
?document_type=lab_report&uploaded_by_role=lab_member
```
`uploaded_by_role`: `doctor` | `patient` | `lab_member`

---

### Get / Delete
```
GET    /api/documents/<uuid>/     🔒  (owner or consented doctor)
DELETE /api/documents/<uuid>/     🔒  (owner only — soft delete)
```
> `file` in the response is a **presigned S3 URL** valid for 1 hour.

---

### Doctor Consent Flow (3 steps)

**Step 1 — Find the patient**
```
GET /api/users/patient/lookup/?contact=9876543210     🔒 (Doctor)
```
Returns patient UUID.

**Step 2 — Browse patient's document metadata (no file URL)**
```
GET /api/documents/patient-docs/?patient_id=<uuid>     🔒 (Doctor)
```
Returns titles, types, and current `consent_status` — never the file URL:
```json
{
  "patient": { "id": "...", "name": "Rahul", "contact": 9876543210 },
  "total": 3,
  "documents": [
    { "id": "abc-123", "title": "Blood Report", "document_type": "lab_report",
      "uploaded_by_role": "lab_member", "created_at": "...", "consent_status": null },
    { "id": "def-456", "title": "Prescription", "document_type": "prescription",
      "consent_status": "granted" }
  ]
}
```
`consent_status`: `null` | `pending` | `granted` | `rejected` | `revoked` | `expired`

**Step 3 — Request consent**
```
POST /api/documents/consent/request/     🔒 (Doctor)
{ "document": "abc-123", "purpose": "Review before consultation" }
```

---

### Patient: Manage Consent Requests
```
GET   /api/documents/consent/mine/                          🔒
PATCH /api/documents/consent/<consent_id>/action/           🔒
```
**PATCH:** `{ "action": "granted" }` — options: `granted` | `rejected` | `revoked`
Optional: `"expires_at": "2026-03-10T23:59:00Z"`

**Consent transitions (patient):**

| Current | Can change to |
|---|---|
| `pending` | `granted`, `rejected` |
| `granted` | `revoked` |
| `rejected` | `granted` |
| `revoked` | `granted` |

---

### Doctor: View Own Consent Requests
```
GET /api/documents/consent/doctor/     🔒
```

### Access Audit Log
```
GET /api/documents/access-log/                  🔒 (patient — all their docs)
GET /api/documents/<doc_id>/access-log/         🔒 (patient — specific doc)
```

---

## 🛡️ Admin Panel — `/admin/`

| Section | What's visible / editable |
|---|---|
| **Users** | All accounts, roles, onboarding flags |
| **OTP Logs** | Every OTP generated, used status, expiry |
| **Temp Password Logs** | Temp passwords for staff; `is_used` flips after onboarding |
| **Clinics** | All clinics — active/inactive toggle |
| **Clinic Members** | All memberships, `member_role`, `status` — inline editable |
| **Doctor Profiles** | `is_verified` checkbox — must be ticked for doctor to appear publicly |
| **Doctor Availability** | Weekly schedule per doctor per clinic |
| **Doctor Leaves** | Leave / holiday records |
| **Admission Documents** | Per-clinic required document checklists |

---

## 📦 Complete URL Reference

### `/api/users/`

| Method | URL | Auth | Who |
|---|---|---|---|
| POST | `/api/users/login/` | ❌ | All |
| POST | `/api/users/token/refresh/` | ❌ | All |
| POST | `/api/users/onboarding/patient/step1/` | ❌ | Public |
| POST | `/api/users/onboarding/patient/step2/` | ❌ | Public |
| PATCH | `/api/users/onboarding/patient/step3/` | 🔒 | Patient |
| POST | `/api/users/onboarding/clinic/step1/` | ❌ | Public |
| POST | `/api/users/onboarding/clinic/step2/` | ❌ | Public |
| PATCH | `/api/users/onboarding/member/complete/` | 🔒 | Clinic staff |
| GET/PUT | `/api/users/me/` | 🔒 | Logged-in user |
| GET/PUT | `/api/users/me/medical-profile/` | 🔒 | Patient |
| GET | `/api/users/check/?contact=...` | ❌ | Public |
| GET | `/api/users/patient/lookup/?contact=...` | 🔒 | Doctor / Lab Member |
| PUT | `/api/users/password/change/` | 🔒 | Logged-in user |
| GET/POST | `/api/users/address/` | 🔒 | Logged-in user |
| GET/PUT/DELETE | `/api/users/address/<id>/` | 🔒 | Logged-in user |

### `/api/clinics/`

| Method | URL | Auth | Who |
|---|---|---|---|
| GET | `/api/clinics/public/` | ❌ | Public |
| POST | `/api/clinics/onboarding/step3/` | 🔒 | Clinic Owner |
| GET/POST | `/api/clinics/` | 🔒 | Clinic Owner |
| GET | `/api/clinics/<id>/` | ❌ | Public |
| PUT/DELETE | `/api/clinics/<id>/` | 🔒 | Clinic Owner |
| GET/POST | `/api/clinics/<id>/members/` | 🔒 | Clinic Owner |
| GET/PUT/DELETE | `/api/clinics/<id>/members/<member_id>/` | 🔒 | Clinic Owner |
| GET | `/api/clinics/<id>/slots/` | ❌ | Public |
| POST | `/api/clinics/<id>/slots/` | 🔒 | Clinic Owner |
| PUT/DELETE | `/api/clinics/<id>/slots/<slot_id>/` | 🔒 | Clinic Owner |
| GET | `/api/clinics/my/memberships/` | 🔒 | Doctor / Lab / Receptionist |
| GET | `/api/clinics/<id>/admission-docs/` | ❌ | Public |
| POST | `/api/clinics/<id>/admission-docs/` | 🔒 | Clinic Owner |
| PUT/DELETE | `/api/clinics/<id>/admission-docs/<doc_id>/` | 🔒 | Clinic Owner |
| GET | `/api/clinics/<id>/admission-docs/patient/` | 🔒 | Patient (with appointment) |

### `/api/doctors/`

| Method | URL | Auth | Who |
|---|---|---|---|
| GET | `/api/doctors/` | ❌ | Public |
| GET | `/api/doctors/<id>/` | ❌ | Public |
| GET/PUT | `/api/doctors/me/` | 🔒 | Doctor |
| GET | `/api/doctors/<id>/availability/` | ❌ | Public |
| POST | `/api/doctors/<id>/availability/` | 🔒 | Doctor |
| GET | `/api/doctors/<id>/availability/slots/` | ❌ | Public |
| GET/POST | `/api/doctors/me/leaves/` | 🔒 | Doctor |
| DELETE | `/api/doctors/me/leaves/<leave_id>/` | 🔒 | Doctor |

### `/api/appointments/`

| Method | URL | Auth | Who |
|---|---|---|---|
| GET/POST | `/api/appointments/my/` | 🔒 | Patient |
| GET/PATCH | `/api/appointments/my/<id>/` | 🔒 | Patient |
| GET | `/api/appointments/doctor/` | 🔒 | Doctor |
| GET/PATCH | `/api/appointments/doctor/<id>/` | 🔒 | Doctor |
| GET | `/api/appointments/clinic/<clinic_id>/dashboard/` | 🔒 | Clinic Owner |

### `/api/documents/`

| Method | URL | Auth | Who |
|---|---|---|---|
| GET/POST | `/api/documents/` | 🔒 | Patient / Doctor / Lab Member |
| GET/DELETE | `/api/documents/<uuid>/` | 🔒 | Owner / Consented Doctor |
| GET | `/api/documents/patient-docs/?patient_id=<uuid>` | 🔒 | Doctor |
| POST | `/api/documents/consent/request/` | 🔒 | Doctor |
| GET | `/api/documents/consent/mine/` | �� | Patient |
| PATCH | `/api/documents/consent/<id>/action/` | 🔒 | Patient |
| GET | `/api/documents/consent/doctor/` | 🔒 | Doctor |
| GET | `/api/documents/access-log/` | 🔒 | Patient |
| GET | `/api/documents/<doc_id>/access-log/` | 🔒 | Patient |

---

## 🗂️ Project Structure

```
QuickCare/
├── QuickCare/          # Project config (settings, urls, wsgi)
├── users/              # User model, OTP/JWT auth, addresses, medical profile, temp password logs
├── clinic/             # Clinic CRUD, member management, time slots, admission docs
├── doctors/            # Doctor profiles, availability (weekly), leaves, verification
├── appointments/       # Booking, status management, clinic dashboard
├── documents/          # Document upload (S3), consent system, metadata browsing, audit log
├── .env                # Local secrets (never commit)
├── .env.example        # Template
├── requirements.txt
└── manage.py
```

---

## 🚦 Error Responses

```json
{ "message": "Human-readable error description." }
```
Or for field-level validation:
```json
{ "field_name": ["This field is required."] }
```

| Code | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Missing or invalid token |
| `403` | Authenticated but not authorised |
| `404` | Resource not found |
| `409` | Conflict (duplicate slot, doctor already in another clinic, etc.) |

---

## 📝 Key Behaviours

- **OTP** sent via Twilio SMS. Falls back to `print()` in dev. `MASTER_OTP` in `.env` bypasses OTP checks in development.
- **Temp passwords** for auto-registered staff are sent via Twilio SMS and logged in Admin → Temp Password Logs. Marked `is_used=True` after onboarding is completed.
- **Document storage** uses AWS S3 when `AWS_*` env vars are set. Files are private — served via presigned URLs valid 1 hour. Falls back to local `media/` in dev.
- **PDF only, 5 MB max** — enforced server-side. Non-PDF or oversized uploads return `400`.
- **Doctor verification** — `is_verified=False` by default. Superadmin must tick it in `/admin/` before the doctor appears in public listings.
- **Doctor availability** — set once per day-of-week, repeats every week automatically. No re-entry required.
- **Consent flow** — doctors browse document metadata only (no file URL) → request consent → patient approves → doctor gets presigned URL access via `GET /api/documents/<uuid>/`.
- **Onboarding flags** — `is_partial_onboarding=True` after account creation. `is_complete_onboarding=True` after profile completion. Both stay `True` permanently — never reset to `False`.
- **Appointment transitions** — enforced server-side. Invalid status changes return `400` with the list of allowed transitions.
- **member_role backfill** — migration `0005` auto-fixes any blank `member_role` rows (from old admin entries) to `'doctor'` on deploy.
