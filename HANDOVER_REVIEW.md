# JANSAHAYAK AI — Technical Handover & Architecture Review

**Project**: JanSahayak AI (*From Voice to Resolution*)  
**GitHub Repository**: `https://github.com/shivamg-ops/TheLastProtocol.git`  
**Active Branch**: `main`  
**Purpose**: Ready-to-share technical overview for external peer review or automated grading agents.

---

## 1. Project Overview & Objectives
JanSahayak AI is an autonomous, AI-powered multilingual civic grievance management platform where citizens report local civic issues (garbage, water leaks, potholes, streetlights, drainage, traffic obstructions) through speech, text, photos, and video evidence. 

The AI understands complaints in **Hindi, Marathi, English, and Hinglish**, collects missing details via conversational follow-ups, auto-suggests municipal departments, generates structured drafts, checks for duplicate complaints, and provides citizens with verifiable resolution evidence.

---

## 2. Technology Stack
- **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS, Lucide React, Web Speech API (`hi-IN`).
- **Backend**: Python 3.15, Django 6.1.3, Django REST Framework, SimpleJWT, SQLite.
- **AI Engine**: Google Gemini API (`google-genai` 3.6.1) with robust rule-based multilingual heuristic fallback.
- **Security Standard**: Cloudflare Security Audit Specification (6-phase methodology).

---

## 3. What Has Been Built & Completed

### A. Frontend Architecture (`/frontend`)
1. **Public Web Experience (`/`)**:
   - Clean, SaaS-styled navbar with Overview, Civic Verticals, How It Works, and Role-Aware Dashboard redirection.
   - Dynamic 6-category vertical showcase and 4-step autonomous workflow visualization.
2. **Interactive AI Voice & Chat Assistant (`/report`)**:
   - Multi-turn interactive chat interface with real-time speech-to-text streaming.
   - In-chat photo/video attachment preview.
   - Dynamic right-hand *"Structured Complaint Preview"* card that extracts category, urgency, landmark, ward, and duration.
   - Editable citizen confirmation card before official ticket creation.
3. **Citizen Portal (`/citizen`)**:
   - Grievance tracking table with live status badges (`submitted`, `assigned`, `in_progress`, `resolved`).
   - Deep inspection pane with an append-only audit timeline log.
4. **Staff Workspace (`/staff`)**:
   - Departmental field task queue.
   - Progress update form with mandatory resolution note logging.
5. **Admin AI Command Centre (`/admin`)**:
   - Municipal overview metrics and resolution rate tracking.
   - Suspected duplicate complaint detection alerts.
   - Department SLA monitoring and field staff dispatch modal.
6. **Authentication (`/login`, `/signup`)**:
   - Role-safe registration and JWT login with automatic role routing.

### B. Backend Architecture (`/backend`)
1. **Relational Models (`api/models.py`)**:
   - `User`: Extended `AbstractUser` with roles (`citizen`, `ngo`, `small_society`, `large_society`, `staff`, `admin`).
   - `Department`: 6 pre-seeded departments (SWM, WSS, RTI, ESL, SWD, TEC).
   - `ComplaintCategory`: 6 pre-seeded categories mapped to departments with SLA defaults.
   - `Complaint`: Unique tracking IDs (`JSH-XXXXXXXX`), geolocation, ward, duration, duplicate pointers, and SLA target dates.
   - `ComplaintEvidence`: Uploaded files with validation constraints.
   - `ComplaintTimeline`: Append-only audit history of every status transition.
2. **AI Multilingual Service (`api/ai_service.py`)**:
   - Multi-turn conversation history analysis.
   - Language detection (Hindi, Marathi, English, Hinglish).
   - Duplicate detection engine matching category, ward, and landmark proximity.
3. **Backend Landing Gateway (`jansahayak_project/urls.py`)**:
   - Custom branded landing page at `http://127.0.0.1:8000/` replacing default 404s with direct links to Admin, API root, and Frontend.

---

## 4. Security Hardening (Cloudflare Audit Verified)
A complete six-phase security audit was conducted using the Cloudflare `security-audit` skill:
1. **Privilege Escalation Patched**: `RegisterSerializer.create` enforces that client-supplied `role` inputs cannot assign `admin` or `staff`.
2. **Broken Object-Level Authorization (BOLA) Patched**: `ComplaintViewSet.update_status` strictly verifies that only administrators or assigned staff members can update ticket statuses. Regular citizens receive `HTTP 403 Forbidden`.
3. **Rate Limiting / DoS Protection**: Global Django REST Framework `AnonRateThrottle` (20 req/min) and `UserRateThrottle` (120 req/min) protect AI endpoints.
4. **CORS Allowlist**: `CORS_ALLOW_ALL_ORIGINS = False` with explicit localhost allowlists.
5. **Upload Protection**: File size capped at 25 MB with strict extension whitelisting (`.jpg`, `.png`, `.mp4`, `.pdf`, etc.).
6. **Zero Leaked Secrets**: Complete git history purged of test passwords; remote `main` branch is 100% clean.

---

## 5. Verification & Tests
- ✅ **Next.js Production Build**: `npm run build` passes with 0 errors.
- ✅ **Django Automated Test Suite**: `python manage.py test api` passes with 0 errors.
- ✅ **End-to-End Simulation**: Automated script successfully executed full flow:
  `Citizen Auth → Voice AI Intake → Complaint Creation → BOLA Defense → Admin Dispatch → Staff Resolution → Citizen Timeline Verification`.

---

## 6. How to Run Locally

### Start Backend
```bash
cd backend
source venv/bin/activate
python manage.py runserver 8000
```
- Gateway URL: `http://127.0.0.1:8000/`
- Admin Panel: `http://127.0.0.1:8000/admin/`

### Start Frontend
```bash
cd frontend
npm run dev
```
- Web Application: `http://localhost:3000`
- AI Voice/Chat Report: `http://localhost:3000/report`

### Local Test Accounts
- **Admin**: `admin` / `adminpassword123`
- **Staff**: `staff1` / `staffpassword123`
- **Citizen**: `citizen1` / `citizenpassword123`
