# QuickCare — Hospital Management System API

A Django REST Framework backend for managing clinic registrations, appointment booking, and document sharing with patient consent. Built for clinics, hospitals, and diagnostic centres.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework 3.16 |
| Auth | JWT via `djangorestframework-simplejwt` |
| API Docs | `drf-spectacular` — Swagger UI + ReDoc |
| Database | PostgreSQL (Render) / SQLite (local dev) |
| OTP | `pyotp` TOTP (6-digit, 10-min window) |
| Config | `python-decouple` (.env) |
| File Uploads | Pillow + Django FileField |
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
# Edit .env — set USE_SQLITE=True for local dev

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
| 4 | Doctor | Auto-registered by clinic owner; belongs to one clinic |
| 5 | Receptionist | Clinic staff; auto-registered by clinic owner |
| 6 | Lab Member | Clinic staff; auto-registered by clinic owner |
| 7 | Clinic Owner | Creates & manages clinics, adds staff |

---

## 🔄 Registration & Login Flows

### Patient Registration (3 steps)
```
Step 1: POST /api/users/onboarding/patient/step1/  → contact + name + password → OTP sent
Step 2: POST /api/users/onboarding/patient/step2/  → contact + otp → account created → 🔑 JWT
Step 3: PUT  /api/users/onboarding/patient/step3/  → fill profile + medical details
```

### Clinic Owner Registration (3 steps)
```
Step 1: POST /api/users/onboarding/clinic/step1/   → contact + name + password → OTP sent
Step 2: POST /api/users/onboarding/clinic/step2/   → contact + otp → account created → 🔑 JWT
Step 3: POST /api/clinics/onboarding/step3/        → clinic details + time slots
```

### Clinic Staff Auto-Registration (Doctor / Receptionist / Lab Member)
```
Clinic owner adds staff via POST /api/clinics/<id>/members/
  ↓
If the contact is NOT yet registered:
  • Account auto-created with a random 8-character temp password
  • Temp password is logged in the admin panel (Temp Password Logs)
  • is_partial_onboarding = True, is_complete_onboarding = False

Staff logs in with their temp password:
  POST /api/users/login/
  ↓  (response includes onboarding_required: true + tokens)

Staff fills in their profile:
  PUT /api/users/onboarding/member/complete/    🔒
  ↓  (is_complete_onboarding = True, new tokens returned)
```

> **One-clinic rule:** A doctor can only be an active member of **one clinic** at a time. Trying to add an already-active doctor to a second clinic returns `409 Conflict`.

### Login (all existing users — no OTP)
```
POST /api/users/login/   → contact + password → verified against DB → 🔑 JWT
```

> OTP is only used during **registration** to verify the phone number. After that, all logins are contact + password.

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
{
  "contact": 9876543210,
  "password": "secret123"
}
```

**Response `200` (fully onboarded user):**
```json
{
  "access": "<token>",
  "refresh": "<token>",
  "user": { "id": "...", "name": "Raj Kumar", "contact": 9876543210, "roles": { "id": 3, "name": "is_patient" }, "is_complete_onboarding": true }
}
```

**Response `200` (partial-onboarding clinic staff):**
```json
{
  "message": "Login successful, but your profile is incomplete. Please complete your onboarding to access all features.",
  "onboarding_required": true,
  "onboarding_url": "/api/users/onboarding/member/complete/",
  "access": "<token>",
  "refresh": "<token>",
  "user": { "id": "...", "name": "", "roles": { "id": 4, "name": "is_doctor" }, "is_partial_onboarding": true, "is_complete_onboarding": false }
}
```

> When `onboarding_required: true` is returned, use the provided tokens to call `PUT /api/users/onboarding/member/complete/` immediately.

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
{ "message": "OTP sent to your contact number. Please verify to complete registration.", "contact": 9876543210, "next_step": "/api/users/onboarding/patient/step2/" }
```

---

### Step 2 — Verify OTP → Account Created
```
POST /api/users/onboarding/patient/step2/
```
**Request:**
```json
{ "contact": 9876543210, "otp": "482910" }
```
**Response `201`:**
```json
{
  "message": "OTP verified. Account created! Please complete your profile.",
  "access": "<token>", "refresh": "<token>",
  "user": { "id": "...", "name": "Rahul Sharma", "contact": 9876543210, "is_partial_onboarding": true, "is_complete_onboarding": false },
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
  "gender": "male", "age": 28, "email": "rahul@example.com", "blood_group": "B+",
  "address_area": "Near City Hospital", "house_no": "12A", "town": "Jaipur",
  "state": "Rajasthan", "pincode": "302001", "landmark": "Opp. SBI Bank",
  "allergies": "Penicillin", "chronic_conditions": "None",
  "current_medications": "None", "past_surgeries": "Appendectomy 2020",
  "family_history": "Diabetes (father)", "height_cm": 175, "weight_kg": 70.5,
  "emergency_contact_name": "Priya Sharma", "emergency_contact_number": 9123456789
}
```
All fields except `gender` and `age` are optional.

**Response `200`:**
```json
{
  "message": "Registration complete! Welcome to QuickCare.",
  "user": { "name": "Rahul Sharma", "gender": "male", "age": 28, "blood_group": "B+", "is_complete_onboarding": true },
  "medical_profile": { "allergies": "Penicillin", "height_cm": 175, "weight_kg": "70.50" }
}
```

`blood_group` options: `A+` `A-` `B+` `B-` `AB+` `AB-` `O+` `O-`

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
  "address": "12, MG Road", "city": "Jaipur",
  "state": "Rajasthan", "pincode": "302001",
  "registration_number": "RJ-MED-2024-001",
  "time_slots": [
    { "day_of_week": 0, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15, "max_appointments": 20 },
    { "day_of_week": 1, "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15, "max_appointments": 20 }
  ]
}
```

`clinic_type`: `clinic` | `hospital` | `diagnostic_center` | `polyclinic`  
`day_of_week`: `0`=Mon `1`=Tue `2`=Wed `3`=Thu `4`=Fri `5`=Sat `6`=Sun

---

## 👨‍⚕️ Clinic Staff Auto-Registration

### Add a Member (auto-creates account if not registered)
```
POST /api/clinics/<clinic_id>/members/     🔒 (Clinic Owner)
```
**Request:**
```json
{
  "contact": 9988776655,
  "name": "Dr. Suresh Yadav",
  "member_role": "doctor",
  "department": "Cardiology",
  "joined_at": "2026-02-25"
}
```

| Field | Required | Notes |
|---|---|---|
| `contact` | ✅ | Phone number of the staff member |
| `name` | ⚠️ | Required only if the person is NOT yet registered |
| `member_role` | ✅ | `doctor` \| `receptionist` \| `lab_member` |
| `department` | ❌ | Optional |
| `joined_at` | ❌ | Defaults to today |
| `notes` | ❌ | Optional |

**Response `201` (new user auto-created):**
```json
{
  "id": "b2c3d4e5-...",
  "user": { "id": "...", "name": "Dr. Suresh Yadav", "contact": 9988776655 },
  "member_role": "doctor",
  "status": "active",
  "department": "Cardiology",
  "_info": "New account created. A temporary password has been sent to 9988776655. They must log in and complete their profile at /api/users/onboarding/member/complete/"
}
```

**Response `409` (doctor already in another clinic):**
```json
{ "message": "This doctor is already an active member of \"Apollo Clinic\". A doctor can only belong to one clinic at a time." }
```

> The temp password is also visible to superadmin in **Admin Panel → Temp Password Logs**.

---

### Complete Member Onboarding
```
PUT /api/users/onboarding/member/complete/     🔒
```
Called by the clinic staff member after their first login to fill in their profile.

**Request (all fields optional):**
```json
{
  "name": "Dr. Suresh Yadav",
  "gender": "male",
  "age": 35,
  "email": "suresh@example.com",
  "blood_group": "O+",
  "specialty": "Cardiology",
  "qualification": "MBBS, MD",
  "experience_years": 10,
  "address_area": "Vaishali Nagar",
  "house_no": "5B",
  "town": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302021"
}
```

**Response `200`:**
```json
{
  "message": "Onboarding complete! Welcome to QuickCare.",
  "access": "<token>",
  "refresh": "<token>",
  "user": { "id": "...", "name": "Dr. Suresh Yadav", "is_complete_onboarding": true }
}
```

> New tokens are issued immediately so the user doesn't need to log in again.

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
PUT  /api/users/me/medical-profile/     🔒
```

---

### Check User by Contact
```
GET /api/users/check/?contact=9876543210
```
**Response:** `{ "exists": true }`

---

### Change Password
```
PUT /api/users/password/change/     🔒
```
**Request:** `{ "password": "NewSecurePass@123" }`

---

### User Address
```
GET    /api/users/address/           🔒   — list addresses
POST   /api/users/address/           🔒   — add address
GET    /api/users/address/<id>/      🔒
PUT    /api/users/address/<id>/      🔒
DELETE /api/users/address/<id>/      🔒
```
`address_type`: `home` | `work`

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
GET  /api/clinics/<clinic_id>/members/                      🔒 (Owner)
POST /api/clinics/<clinic_id>/members/                      🔒 (Owner) — see auto-registration above
GET  /api/clinics/<clinic_id>/members/<member_id>/          🔒 (Owner)
PUT  /api/clinics/<clinic_id>/members/<member_id>/          🔒 (Owner)
DELETE /api/clinics/<clinic_id>/members/<member_id>/        🔒 (Owner — soft remove, sets left_at)
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
Only returns doctors who are **active members** of at least one clinic.

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
> Profile is auto-created when a clinic owner adds you. Use PUT to update specialization and fees.

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
{ "clinic": "<uuid>", "day": "monday", "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15, "max_patients": 20 }
```

---

### Available Appointment Slots
```
GET /api/doctors/<doctor_id>/availability/slots/?date=2026-03-01&clinic_id=<uuid>
```
**Response:** `{ "doctor": 1, "date": "2026-03-01", "available_slots": ["09:00", "09:15", ...] }`

---

### Doctor Leaves
```
GET    /api/doctors/me/leaves/                    🔒
POST   /api/doctors/me/leaves/                    🔒
DELETE /api/doctors/me/leaves/<leave_id>/         🔒
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

---

### Patient: Get / Cancel
```
GET   /api/appointments/my/<id>/     🔒
PATCH /api/appointments/my/<id>/     🔒  — body: { "status": "cancelled" }
```

---

### Doctor: List Appointments
```
GET /api/appointments/doctor/     🔒
```
Query params: `?date=2026-03-01`, `?status=confirmed`, `?from_date=...&to_date=...`

---

### Doctor: Get / Update
```
GET   /api/appointments/doctor/<id>/     🔒
PATCH /api/appointments/doctor/<id>/     🔒
```
**PATCH:** `{ "status": "confirmed" }`  
Status options: `pending` | `confirmed` | `completed` | `cancelled` | `no_show`

---

## 📄 Documents — `/api/documents/`

> Patient owns documents. Doctors must request consent before accessing. All access is logged.

### List / Upload
```
GET  /api/documents/     🔒
POST /api/documents/     🔒  (multipart/form-data)
```
`document_type`: `prescription` | `lab_report` | `imaging` | `discharge_summary` | `insurance` | `other`

---

### Get / Delete
```
GET    /api/documents/<uuid>/     🔒
DELETE /api/documents/<uuid>/     🔒 (Owner — soft delete)
```

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
GET   /api/documents/consent/mine/                          🔒 (Patient)
PATCH /api/documents/consent/<consent_id>/action/           🔒 (Patient)
```
**PATCH:** `{ "action": "grant" }` — options: `grant` | `reject` | `revoke`

---

### Doctor: My Consent Requests
```
GET /api/documents/consent/doctor/     🔒
```

---

### Access Audit Log
```
GET /api/documents/access-log/              🔒 (Patient)
GET /api/documents/<doc_id>/access-log/     🔒 (Patient)
```

---

## 🛡️ Admin Panel

**URL:** `/admin/`

Superadmin can view:

| Section | What's visible |
|---|---|
| **Users** | All user accounts, roles, onboarding status |
| **OTP Logs** | Every OTP generated, whether used, expiry time |
| **Temp Password Logs** | Temp passwords issued to auto-registered clinic staff, whether used |
| **Clinics / Members** | All clinics and their member rosters |
| **Roles** | Role definitions |

> **Temp Password Logs** are marked `is_used = True` automatically once the staff member completes onboarding via `PUT /api/users/onboarding/member/complete/`.

---

## 🗂️ Project Structure

```
QuickCare/
├── QuickCare/          # Project config (settings, urls, wsgi)
├── users/              # Custom User, OTP auth, JWT, addresses, medical profile, temp password logs
├── clinic/             # Clinic CRUD, member management, time slots, auto-registration
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
| `409` | Conflict (e.g. duplicate member, doctor already in another clinic) |

---

## 🔒 Permissions Summary

| Endpoint | Who |
|---|---|
| `POST /api/users/login/` | Anyone |
| `POST /api/users/token/refresh/` | Anyone |
| `POST /api/users/onboarding/patient/step1-2/` | Anyone |
| `POST /api/users/onboarding/clinic/step1-2/` | Anyone |
| `PUT /api/users/onboarding/patient/step3/` | Authenticated (partial onboarding) |
| `POST /api/clinics/onboarding/step3/` | Authenticated Clinic Owner |
| `PUT /api/users/onboarding/member/complete/` | Authenticated clinic staff (partial onboarding) |
| `/api/users/me/` | Logged-in user |
| `/api/users/me/medical-profile/` | Logged-in user |
| `/api/clinics/public/` | Anyone |
| `/api/clinics/<id>/slots/` (GET) | Anyone |
| `/api/clinics/` (CRUD) | Clinic Owner |
| `POST /api/clinics/<id>/members/` | Clinic Owner |
| `GET /api/clinics/<id>/members/` | Clinic Owner |
| `/api/clinics/my/memberships/` | Doctor / Lab Member / Receptionist |
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
- **Temp passwords** for auto-registered clinic staff are printed to console in dev and stored in **Admin Panel → Temp Password Logs**.
- **`MASTER_OTP`** in `.env` bypasses OTP verification in development. Leave empty in production.
- **`USE_SQLITE=True`** in `.env` uses local SQLite. Set `USE_SQLITE=False` for PostgreSQL in production.
- **Doctors cannot self-register** — they must be added to a clinic by a Clinic Owner. The account is auto-created on their first addition.
- **One clinic per doctor** — a doctor can only be an active member of one clinic at a time.
- **Document access** is always logged. Doctors can only access a file with an active (non-expired, non-revoked) consent record.
- **Onboarding flags**: `is_partial_onboarding=True` after account creation, `is_complete_onboarding=True` after profile completion. Frontend should use these to redirect users to the correct screen.


---