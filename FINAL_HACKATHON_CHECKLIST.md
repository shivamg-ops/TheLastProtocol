# FINAL HACKATHON READINESS CHECKLIST

**Project**: JanSahayak AI (*From Voice to Resolution*)  
**Version**: 1.0.0 (Release Candidate for Live Hackathon Demo)  
**Status**: **READY FOR LIVE HACKATHON DEMO**  
**Audit Date**: November 21, 2026  

---

## 1. PRE-FLIGHT VERIFICATION MATRIX

| Area | Component | Verification Check | Status | Evidence / Notes |
|---|---|---|---|---|
| **Frontend** | Navigation | Role-based Dashboard routing (`/admin`, `/staff`, `/citizen`) | **PASS** | Auto-detects JWT role and highlights active portal |
| **Frontend** | Speech Input | Continuous Web Speech (`lang: 'hi-IN'`, interim preview) | **PASS** | Tested in Hindi, Marathi, Hinglish, and English |
| **Frontend** | Attachment | Photo evidence upload (`multipart/form-data`) | **PASS** | Linked to ticket ID upon complaint confirmation |
| **Frontend** | Build | Next.js Turbopack compilation | **PASS** | `next build` 0 errors, 10/10 routes prerendered |
| **Backend** | Auth | SimpleJWT Token Issuance & Refresh | **PASS** | Transparent token retry interceptor in `api.ts` |
| **Backend** | Roles | Role sanitization on signup (`admin` forced to `citizen`) | **PASS** | Tested via exploit payload; privilege escalation blocked |
| **Backend** | BOLA / IDOR | Object-level access control on complaints & evidence | **PASS** | Cross-citizen query returns `HTTP 404` |
| **Backend** | Staff Dispatch | Admin-only staff list & role validation | **PASS** | Dynamic `<select>` dropdown populated via `/api/user/staff-list/` |
| **Backend** | Resolution | Staff proof attachment & status update to `resolved` | **PASS** | Resolution photo persisted and visible to citizen |
| **Backend** | Citizen Rating | 1–5 star rating & feedback submission | **PASS** | Enforces resolved status, prevents duplicate submissions |
| **AI Engine** | Classification | 6 Municipal verticals + urgency prioritization | **PASS** | Fallback rule engine ensures 100% uptime without API keys |
| **AI Engine** | Missing Info | Prompts for location/landmark if missing | **PASS** | Blocks premature ticket creation until location is provided |

---

## 2. PORTAL ENDPOINTS & ACCESS CREDENTIALS (LOCAL DEMO)

> [!NOTE]
> All demo accounts exist exclusively in the local SQLite database (`backend/db.sqlite3`) and are pre-seeded with realistic municipal tickets.

* **Citizen Portal**: `http://localhost:3000/citizen`
  - Demo Username: `citizen1`
  - Demo Password: `citizenpassword123`
* **Field Staff Portal**: `http://localhost:3000/staff`
  - Demo Username: `staff1`
  - Demo Password: `staffpassword123`
* **Municipal Admin Command Centre**: `http://localhost:3000/admin`
  - Demo Username: `admin`
  - Demo Password: `adminpassword123`

---

## 3. SEEDING & REPEATABLE DEMO DATA COMMANDS

To restore or seed the clean hackathon presentation dataset at any time:

```bash
# 1. Activate virtual environment
cd /Users/shivam/Desktop/hackathon/doomdays/TheLastProtocol/backend
source venv/bin/activate

# 2. Seed departments and civic categories
python manage.py seed_data

# 3. Seed 6 realistic multi-lingual demo complaints (Hindi, Marathi, Hinglish, English)
python manage.py seed_demo_data
```

---

## 4. LOCAL RUNTIME LAUNCH INSTRUCTIONS

```bash
# Terminal 1 — Django REST Framework Backend
cd /Users/shivam/Desktop/hackathon/doomdays/TheLastProtocol/backend
./venv/bin/python manage.py runserver 127.0.0.1:8000

# Terminal 2 — Next.js Frontend Client
cd /Users/shivam/Desktop/hackathon/doomdays/TheLastProtocol/frontend
npm run dev
```

Visit **`http://localhost:3000`** in Google Chrome or Microsoft Edge for microphone access.

