# QuickCare — Hospital Management System API

A Django REST Framework backend for managing clinic registrations, appointment booking, document sharing with patient consent, and SMS-based OTP authentication. Built for clinics, hospitals, and diagnostic centres.

---

## ��️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework 3.16 |
| Auth | JWT via `djangorestframework-simplejwt` |
| API Docs | `drf-spectacular` — Swagger UI + ReDoc |
| Database | PostgreSQL (Render) / SQLite (local dev) |
| OTP | `pyotp` TOTP (6-digit, 10-min window) + **Twilio SMS delivery** |
| SMS | Twilio (`twilio==9.10.2`) |
| File Storage | **AWS S3** via `django-storages` + `boto3` (local fallback: `media/`) |
| Config | `python-decouple` (.env) |
| Production | Gunicorn + Whitenoise on Render |

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
# Edit .env — fill in DB, Twilio, AWS keys (see Environment Variables section)

# 5. Run migrations
python manage.py migrate

# 6. Seed roles
python manage.py shell -c "
from users.models import Role
for id_, name in [(1,'IS_SUPERADMIN'),(2,'IS_ADMIN'),(3,'IS_PATIENT'),(4,'IS_DOCTOR'),(5,'IS_RECEPTIONIST'),(6,'IS_LAB_MEMBER'),(7,'IS_CLINIC_OWNER')]:
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

Copy `.env.example` to `.env` and fill in:

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

> If `TWILIO_*` vars are empty, OTP and temp passwords are **printed to the console** (dev mode).
> If `AWS_*` vars are empty, files are stored **locally** in the `media/` folder.

---

## 🔐 Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

Tokens are returned after OTP registration or login. The system uses **contact number** (mobile) as the username — no email needed.

### User Roles

| ID | Role | Description |
|---|---|---|
| 1 | Superadmin | Full system access + admin panel |
| 2 | Admin | Admin panel access |
| 3 | Patient | Books appointments, owns documents |
| 4 | Doctor | Added by clinic owner; belongs to one clinic |
| 5 | Receptionist | Clinic staff; added by clinic owner |
| 6 | Lab Member | Clinic staff; uploads lab reports for patients |
| 7 | Clinic Owner | Creates & manages clinics, adds staff |

---

## 🔄 Registration & Login Flows

### Patient Registration (3 steps)
```
Step 1: POST  /api/users/onboarding/patient/step1/  → contact + name + password → OTP sent via SMS
Step 2: POST  /api/users/onboarding/patient/step2/  → contact + otp → account created → JWT
Step 3: PATCH /api/users/onboarding/patient/step3/  → fill profile + medical details  🔒
```

### Clinic Owner Registration (3 steps)
```
Step 1: POST /api/users/onboarding/clinic/step1/    → contact + name + password → OTP sent via SMS
Step 2: POST /api/users/onboarding/clinic/step2/    → contact + otp → account created → JWT
Step 3: POST /api/clinics/onboarding/step3/         → clinic details + time slots  🔒
```

### Clinic Staff Auto-Registration (Doctor / Receptionist / Lab Member)
```
Clinic owner adds staff via POST /api/clinics/<id>/members/
  ↓
If the contact is NOT yet registered:
  • Account auto-created with a random 8-character temp password
  • Temp password sent via Twilio SMS to the staff member's number
  • Temp password also logged in Admin Panel → Temp Password Logs
  • is_partial_onboarding = True, is_complete_onboarding = False

Staff logs in with their temp password:
  POST /api/users/login/
  ↓  (response includes onboarding_required: true + tokens)

Staff fills in their profile:
  PATCH /api/users/onboarding/member/complete/   🔒
  ↓  (is_complete_onboarding = True, new tokens returned)
```

> **One-clinic rule:** A doctor can only be an active member of **one clinic** at a time.

### Login (all existing users — no OTP)
```
POST /api/users/login/   → contact + password → JWT
```

---

## 📋 API Reference

**Base URL (local):** `http://localhost:8000`
**Base URL (production):** `https://quickcare-kzis.onrender.com`

All endpoints are prefixed with `/api/`.
🔒 = requires `Authorization: Bearer <token>`

---

## 👤 Users — `/api/users/`

### Login
```
POST /api/users/login/
```
**Request:**
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
**Response `200` (partial-onboarding clinic staff):**
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
```
**Request:** `{ "refresh": "<token>" }`
**Response `200`:** `{ "access": "<token>" }`

---

## 🧍 Patient Registration

### Step 1 — Send OTP
```
POST /api/users/onboarding/patient/step1/
```
**Request:**
```json
{ "contact": 9876543210, "name": "Rahul Sharma", "password": "secret123" }
```
**Response `200`:**
```json
{ "message": "OTP sent to your contact number.", "contact": 9876543210, "next_step": "/api/users/onboarding/patient/step2/" }
```
> OTP is sent via **Twilio SMS**. In dev mode (no Twilio creds), printed to console.

---

### Step 2 — Verify OTP → Account Created
```
POST /api/users/onboarding/patient/step2/
```
**Request:** `{ "contact": 9876543210, "otp": "482910" }`
**Response `201`:**
```json
{
  "message": "OTP verified. Account created! Please complete your profile.",
  "access": "<token>", "refresh": "<token>",
  "user": { "id": "...", "name": "Rahul Sharma", "is_partial_onboarding": true },
  "next_step": "/api/users/onboarding/patient/step3/"
}
```

---

### Step 3 — Complete Profile & Medical Details
```
PATCH /api/users/onboarding/patient/step3/     🔒
```
> Requires token with `is_partial_onboarding=True` and role `IS_PATIENT`.

**Request:**
```json
{
  "gender": "male", "age": 28, "email": "rahul@example.com", "blood_group": "B+",
  "address_area": "Near City Hospital", "house_no": "12A", "town": "Jaipur",
  "state": "Rajasthan", "pincode": "302001",
  "allergies": "Penicillin", "chronic_conditions": "None",
  "current_medications": "None", "past_surgeries": "Appendectomy 2020",
  "family_history": "Diabetes (father)", "height_cm": 175, "weight_kg": 70.5,
  "emergency_contact_name": "Priya Sharma", "emergency_contact_number": 9123456789
}
```
**Response `200`:**
```json
{
  "message": "Registration complete! Welcome to QuickCare.",
  "user": { "name": "Rahul Sharma", "is_complete_onboarding": true },
  "medical_profile": { "allergies": "Penicillin", "height_cm": 175 }
}
```

`blood_group`: `A+` `A-` `B+` `B-` `AB+` `AB-` `O+` `O-`

---

## 🏥 Clinic Owner Registration

### Step 1 — Send OTP
```
POST /api/users/onboarding/clinic/step1/
```
**Request:** `{ "contact": 9876543210, "name": "Dr. Anil Gupta", "password": "secret123" }`

---

### Step 2 — Verify OTP → Account Created
```
POST /api/users/onboarding/clinic/step2/
```
**Request:** `{ "contact": 9876543210, "otp": "482910" }`
**Response `201`:** Returns JWT + `next_step: /api/clinics/onboarding/step3/`

---

### Step 3 — Create Clinic + Time Slots
```
POST /api/clinics/onboarding/step3/     🔒
```
**Request:**
```json
{
  "name": "City Care Clinic", "clinic_type": "clinic",
  "phone": "9876543210", "email": "citycare@example.com",
  "address": "12, MG Road", "city": "Jaipur", "state": "Rajasthan", "pincode": "302001",
  "registration_number": "RJ-MED-2024-001",
  "time_slots": [
    { "day_of_week": 0, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15, "max_appointments": 20 }
  ]
}
```
`clinic_type`: `clinic` | `hospital` | `diagnostic_center` | `polyclinic`
`day_of_week`: `0`=Mon `1`=Tue `2`=Wed `3`=Thu `4`=Fri `5`=Sat `6`=Sun

---

## 👨‍⚕️ Clinic Staff Auto-Registration

### Add a Member
```
POST /api/clinics/<clinic_id>/members/     🔒 (Clinic Owner)
```
**Request:**
```json
{
  "contact": 9988776655, "name": "Dr. Suresh Yadav",
  "member_role": "doctor", "department": "Cardiology", "joined_at": "2026-02-25"
}
```

| Field | Required | Notes |
|---|---|---|
| `contact` | ✅ | Phone number of the staff member |
| `name` | ⚠️ | Required only if person is NOT yet registered |
| `member_role` | ✅ | `doctor` \| `receptionist` \| `lab_member` |
| `department` | ❌ | Optional |
| `joined_at` | ❌ | Defaults to today |
| `notes` | ❌ | Optional internal notes |

**Response `201`:**
```json
{
  "member_role": "doctor", "status": "active",
  "_info": "New account created. A temporary password has been sent to 9988776655 via SMS."
}
```

> Temp password also visible in **Admin Panel → Temp Password Logs**.

**Response `409` (doctor already in another clinic):**
```json
{ "message": "This doctor is already an active member of \"Apollo Clinic\". A doctor can only belong to one clinic at a time." }
```

---

### Complete Member Onboarding
```
PATCH /api/users/onboarding/member/complete/     🔒
```
> Only works for clinic staff with `is_partial_onboarding=True`. Role must be doctor / receptionist / lab_member.

**Request (all optional):**
```json
{
  "name": "Dr. Suresh Yadav", "gender": "male", "age": 35, "email": "suresh@example.com",
  "specialty": "Cardiology", "qualification": "MBBS, MD", "experience_years": 10,
  "address_area": "Vaishali Nagar", "town": "Jaipur", "state": "Rajasthan", "pincode": "302021"
}
```
**Response `200`:** Returns new tokens + `is_complete_onboarding: true`

---

## 👤 User — General Endpoints

### Get / Update Current User
```
GET  /api/users/me/     🔒
PUT  /api/users/me/     🔒
```

---

### Get / Update Medical Profile
```
GET  /api/users/me/medical-profile/     🔒
PUT  /api/users/me/medical-profile/     ��
```

---

### Check User by Contact
```
GET /api/users/check/?contact=9876543210
```
**Response:** `{ "exists": true }`
*(Public — no auth required)*

---

### Patient Lookup by Contact  *(Doctor / Lab Member only)*
```
GET /api/users/patient/lookup/?contact=9876543210     🔒
```
Used by doctors and lab members to find a patient's `id` before uploading documents.

**Response `200`:**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "name": "Rahul Sharma",
  "contact": 9876543210,
  "gender": "male",
  "age": 28,
  "blood_group": "B+"
}
```
> `403` if called by a non-doctor/non-lab-member. `404` if patient not found.

---

### Change Password
```
PUT /api/users/password/change/     🔒
```
**Request:** `{ "password": "NewSecurePass@123" }`

---

### User Address
```
GET    /api/users/address/           🔒
POST   /api/users/address/           🔒
GET    /api/users/address/<id>/      🔒
PUT    /api/users/address/<id>/      🔒
DELETE /api/users/address/<id>/      🔒
```

---

## 🏥 Clinics — `/api/clinics/`

### Browse Public Clinics
```
GET /api/clinics/public/
```
Query params: `?city=Jaipur`, `?type=hospital`, `?search=Apollo`

---

### My Clinics (Clinic Owner)
```
GET  /api/clinics/     🔒
POST /api/clinics/     🔒
```

---

### Clinic Detail
```
GET    /api/clinics/<clinic_id>/     (Public)
PUT    /api/clinics/<clinic_id>/     🔒 (Owner)
DELETE /api/clinics/<clinic_id>/     🔒 (Owner — soft delete)
```

---

### Clinic Members
```
GET    /api/clinics/<clinic_id>/members/                  🔒 (Owner)
POST   /api/clinics/<clinic_id>/members/                  🔒 (Owner)
GET    /api/clinics/<clinic_id>/members/<member_id>/      🔒 (Owner)
PUT    /api/clinics/<clinic_id>/members/<member_id>/      🔒 (Owner)
DELETE /api/clinics/<clinic_id>/members/<member_id>/      🔒 (Owner — soft remove)
```
**GET** query params: `?role=doctor`, `?status=active`

---

### Clinic Time Slots
```
GET    /api/clinics/<clinic_id>/slots/               (Public)
POST   /api/clinics/<clinic_id>/slots/               🔒 (Owner)
PUT    /api/clinics/<clinic_id>/slots/<slot_id>/     🔒 (Owner)
DELETE /api/clinics/<clinic_id>/slots/<slot_id>/     🔒 (Owner — deactivates)
```

---

### My Memberships (Doctor / Lab Member / Receptionist)
```
GET /api/clinics/my/memberships/     🔒
```

---

## 👨‍⚕️ Doctors — `/api/doctors/`

### List Doctors (Public)
```
GET /api/doctors/
```

| Query Param | Example | Description |
|---|---|---|
| `clinic` | `?clinic=<uuid>` | Filter by clinic |
| `specialty` | `?specialty=cardiology` | Filter by specialty |
| `min_fee` / `max_fee` | `?min_fee=200&max_fee=800` | Fee range |
| `video` | `?video=true` | Offers video consult |
| `search` | `?search=Dr. Sharma` | Search by name |

---

### Doctor Detail (Public)
```
GET /api/doctors/<id>/
```

---

### My Doctor Profile
```
GET  /api/doctors/me/     🔒 (Doctor)
PUT  /api/doctors/me/     🔒 (Doctor)
```

---

### Doctor Availability
```
GET  /api/doctors/<doctor_id>/availability/              (Public)
POST /api/doctors/<doctor_id>/availability/     🔒 (Doctor)
```

---

### Available Appointment Slots
```
GET /api/doctors/<doctor_id>/availability/slots/?date=2026-03-01&clinic_id=<uuid>
```
**Response:** `{ "available_slots": ["09:00", "09:15", ...] }`

---

### Doctor Leaves
```
GET    /api/doctors/me/leaves/                 🔒
POST   /api/doctors/me/leaves/                 🔒
DELETE /api/doctors/me/leaves/<leave_id>/      🔒
```

---

## 📅 Appointments — `/api/appointments/`

### Patient: List / Book
```
GET  /api/appointments/my/     🔒
POST /api/appointments/my/     🔒
```
**POST Request:**
```json
{
  "doctor": 1, "appointment_date": "2026-03-01", "appointment_time": "09:30",
  "appointment_type": "first_visit", "mode": "in_clinic",
  "notes": "Chest pain since 2 days"
}
```
`appointment_type`: `first_visit` | `follow_up`
`mode`: `in_clinic` | `video`

---

### Patient: Get / Cancel
```
GET   /api/appointments/my/<id>/     🔒
PATCH /api/appointments/my/<id>/     🔒   body: { "status": "cancelled" }
```

---

### Doctor: Appointments
```
GET   /api/appointments/doctor/          🔒
GET   /api/appointments/doctor/<id>/     🔒
PATCH /api/appointments/doctor/<id>/     🔒   body: { "status": "confirmed" }
```
**GET** query params: `?date=2026-03-01`, `?status=confirmed`, `?from_date=...&to_date=...`
Status options: `pending` | `confirmed` | `completed` | `cancelled` | `no_show`

---

## 📄 Documents — `/api/documents/`

> Documents are **PDF only, max 5 MB**. Stored on **AWS S3** (presigned URLs, valid 1 hour).
> Patients own their documents. Doctors must request consent before accessing. All access is logged.

### Upload Rules by Role

| Role | Can Upload? | Requires `patient_id`? | Sees in List |
|---|---|---|---|
| Patient | ✅ | ❌ (uploads their own) | Their own docs |
| Doctor | ✅ | ✅ | Docs they have active consent for |
| Lab Member | ✅ | ✅ | Docs they personally uploaded |
| Others | ❌ 403 | — | — |

---

### How Lab Member / Doctor Gets Patient ID

```
GET /api/users/patient/lookup/?contact=<patient_phone>     🔒
```
Returns the patient's `id`, `name`, `age`, `gender` — use the `id` as `patient_id` in the upload.

---

### List / Upload
```
GET  /api/documents/     🔒
POST /api/documents/     🔒  (multipart/form-data)
```

**POST form-data fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | text | ✅ | e.g. `CBC Report` |
| `document_type` | text | ✅ | see options below |
| `file` | file | ✅ | PDF only, max 5 MB |
| `description` | text | ❌ | optional |
| `appointment` | text | ❌ | appointment UUID |
| `patient_id` | text | ✅ (doctor/lab) | patient's user UUID |

`document_type`: `prescription` | `lab_report` | `scan` | `discharge_summary` | `vaccination` | `insurance` | `other`

**Validation errors:**
- `400` — `"Only PDF files are accepted."`
- `400` — `"File size must not exceed 5 MB. Uploaded file is X.X MB."`
- `400` — `"patient_id is required when a doctor or lab member uploads a document."`
- `403` — `"You do not have permission to upload documents."`

---

### Get / Delete
```
GET    /api/documents/<uuid>/     🔒   (owner or consented doctor)
DELETE /api/documents/<uuid>/     🔒   (owner only — soft delete)
```
> The `file` field in the response is a **presigned S3 URL** valid for 1 hour — open in a browser to download.

---

### Doctor: Request Consent
```
POST /api/documents/consent/request/     🔒 (Doctor)
```
**Request:**
```json
{ "document": "<uuid>", "purpose": "Reviewing prior lab results", "expires_at": "2026-03-10T23:59:00Z" }
```

---

### Patient: View / Action Consent Requests
```
GET   /api/documents/consent/mine/                         🔒 (Patient)
PATCH /api/documents/consent/<consent_id>/action/          🔒 (Patient)
```
**PATCH:** `{ "action": "granted" }` — options: `granted` | `rejected` | `revoked`

---

### Doctor: My Consent Requests
```
GET /api/documents/consent/doctor/     🔒 (Doctor)
```

---

### Access Audit Log
```
GET /api/documents/access-log/                🔒 (Patient — all their docs)
GET /api/documents/<doc_id>/access-log/       🔒 (Patient — specific doc)
```

---

## 🛡️ Admin Panel

**URL:** `/admin/`

| Section | What's visible |
|---|---|
| **Users** | All user accounts, roles, onboarding flags |
| **OTP Logs** | Every OTP generated, whether used, expiry time |
| **Temp Password Logs** | Temp passwords issued to staff; `is_used` flips after onboarding |
| **Clinics / Members** | All clinics and their member rosters |
| **Roles** | Role definitions |

---

## 📦 Complete URL Reference

### `/api/users/`
| Method | URL | Auth | Who |
|---|---|---|---|
| POST | `/api/users/login/` | ❌ | All |
| POST | `/api/users/token/refresh/` | ❌ | All |
| POST | `/api/users/onboarding/patient/step1/` | ❌ | Public |
| POST | `/api/users/onboarding/patient/step2/` | ❌ | Public |
| PATCH | `/api/users/onboarding/patient/step3/` | 🔒 | Patient (partial onboarding) |
| POST | `/api/users/onboarding/clinic/step1/` | ❌ | Public |
| POST | `/api/users/onboarding/clinic/step2/` | ❌ | Public |
| PATCH | `/api/users/onboarding/member/complete/` | 🔒 | Clinic staff (partial onboarding) |
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
| GET/POST | `/api/clinics/` | �� | Clinic Owner |
| GET/PUT/DELETE | `/api/clinics/<id>/` | 🔒 | Clinic Owner |
| GET/POST | `/api/clinics/<id>/members/` | 🔒 | Clinic Owner |
| GET/PUT/DELETE | `/api/clinics/<id>/members/<member_id>/` | 🔒 | Clinic Owner |
| GET | `/api/clinics/<id>/slots/` | ❌ | Public |
| POST | `/api/clinics/<id>/slots/` | 🔒 | Clinic Owner |
| PUT/DELETE | `/api/clinics/<id>/slots/<slot_id>/` | 🔒 | Clinic Owner |
| GET | `/api/clinics/my/memberships/` | 🔒 | Doctor / Lab Member / Receptionist |

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

### `/api/documents/`
| Method | URL | Auth | Who |
|---|---|---|---|
| GET/POST | `/api/documents/` | 🔒 | Patient / Doctor / Lab Member |
| GET/DELETE | `/api/documents/<uuid>/` | 🔒 | Owner / Consented Doctor |
| POST | `/api/documents/consent/request/` | 🔒 | Doctor |
| GET | `/api/documents/consent/mine/` | 🔒 | Patient |
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
├── clinic/             # Clinic CRUD, member management, time slots, auto-registration
├── doctors/            # Doctor profiles, availability, leaves
├── appointments/       # Appointment booking & management
├── documents/          # Document upload (S3), consent system, audit log
├── .env                # Local secrets (never commit)
├── .env.example        # Template — copy to .env and fill in
├── requirements.txt    # Python dependencies
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
| `409` | Conflict (e.g. doctor already in another clinic) |

---

## 📝 Notes

- **OTP** is sent via **Twilio SMS**. Falls back to `print()` in dev if Twilio credentials are not set. `MASTER_OTP` in `.env` bypasses OTP checks in development.
- **Temp passwords** for auto-registered clinic staff are sent via **Twilio SMS** and stored in **Admin Panel → Temp Password Logs**. Marked `is_used=True` after the member completes onboarding.
- **Document storage** uses **AWS S3** when `AWS_*` env vars are set. Falls back to local `media/` folder in dev. S3 presigned URLs are valid for **1 hour**.
- **PDF only, 5 MB max** — document uploads are validated server-side. Non-PDF or oversized files return `400`.
- **Lab member workflow**: call `GET /api/users/patient/lookup/?contact=<phone>` to get the patient's `id`, then `POST /api/documents/` with that `id` as `patient_id`.
- **Doctors cannot self-register** — they must be added to a clinic by a Clinic Owner.
- **One clinic per doctor** — a doctor can only be active in one clinic at a time.
- **Document consent** — doctors must have a `granted` (non-expired, non-revoked) consent before accessing a patient's document. All access events are logged.
- **Onboarding flags**: `is_partial_onboarding=True` after account creation, `is_complete_onboarding=True` after profile completion. Frontend should check these to redirect users correctly.
- **Twilio trial limitation** — Twilio trial accounts can only SMS **verified numbers**. Upgrade to a paid account to send to any number.
