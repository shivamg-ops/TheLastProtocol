# JANSAHAYAK AI — From Voice to Resolution
**Autonomous Multilingual Complaint Management Platform**

JanSahayak AI empowers citizens to report civic grievances through speech, multilingual text (Hindi, Marathi, Hinglish, English), photos, and video evidence. The platform automatically extracts problem category, SLA urgency, and location, checks duplicate reports, coordinates municipal department dispatch, and tracks verified photo resolution.

---

## 🎨 Design System & Color Palette
- **Charcoal**: `#17191D`
- **Copper**: `#A94D37`
- **Off-white**: `#F7F7F5`
- **Success Green**: `#25845B`
- **Typography**: Clean modern sans-serif with high contrast hierarchy

---

## 🏗️ Architecture & Modules

### End-to-End System Flowchart

<p align="center">
  <img src="docs/flowchart.png" alt="JanSahayak AI Architecture Flowchart" width="850"/>
</p>

<details>
<summary><b>Click to view Mermaid Diagram Source Code</b></summary>

```mermaid
flowchart TD
    A["Citizen opens JanSahayak"] --> B["Login / Register"]
    B --> C["AI Interface"]
    C --> D{"Input Type"}
    D --> E["Text"]
    D --> F["Voice"]
    D --> G["Photo"]
    D --> H["Video"]
    E --> I["AI Complaint Understanding"]
    F --> J["Speech to Text"]
    J --> I
    G --> I
    H --> I
    I --> K["Extract Category and Location"]
    K --> L["Ask Missing Questions"]
    L --> M["Show Complaint Preview"]
    M --> N{"User Confirms?"}
    N -->|No| L
    N -->|Yes| O["Create Complaint Ticket"]
    O --> P["Save in PostgreSQL"]
    O --> Q["Notify Admin"]
    P --> R["Citizen Tracks Complaint"]
    Q --> S["Admin Reviews and Assigns"]
    S --> T["Update Status"]
    T --> R
```

</details>

### 1. Backend (`/backend`)
- **Framework**: Python Django, Django REST Framework, SimpleJWT
- **Database**: SQLite (Ready for PostgreSQL swap via `.env`)
- **AI Engine**: Multilingual Gemini API integration (`google-genai` 3.6.1) with rule-based fallback heuristic engine for Hindi, Marathi, Hinglish, and English
- **Pre-configured Departments**:
  1. Solid Waste Management (SWM)
  2. Water Supply & Sewerage (WSS)
  3. Roads & Traffic Infrastructure (RTI)
  4. Electrical & Street Lighting (ESL)
  5. Stormwater & Drainage (SWD)
  6. Traffic & Encroachment Control (TEC)

### 2. Frontend (`/frontend`)
- **Framework**: Next.js 16 (App Router) + TypeScript + Tailwind CSS
- **Portals**:
  - **Landing Page (`/`)**: Overview, live statistics, civic verticals & autonomous workflow
  - **Voice & AI Report (`/report`)**: Speech recognition (Web Speech API) + Gemini AI multilingual understanding + editable draft confirmation
  - **Citizen Portal (`/citizen`)**: Real-time grievance tracking with audit timeline history
  - **Admin Command Centre (`/admin`)**: Municipal overview, SLA tracking & field staff dispatch
  - **Staff Resolution Workspace (`/staff`)**: Field task status updates and resolution evidence logging
  - **Authentication (`/login`, `/signup`)**: Role-based access control with one-click demo credentials

---

## 🚀 Quick Start Guide

### Step 1: Start Backend Server

> **Note on Windows / PowerShell**: Always activate the virtual environment (`venv`) before running `manage.py`, or invoke `venv\Scripts\python.exe` directly so all dependencies are found.

**Option A: Virtual Environment (Recommended)**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
# or on CMD: venv\Scripts\activate.bat
python manage.py runserver 8000
```

**Option B: Direct Virtual Environment Python (No activation needed)**
```powershell
cd backend
.\venv\Scripts\python.exe manage.py runserver 8000
```
Backend API will be accessible at: `http://127.0.0.1:8000/api/`

### Step 2: Start Frontend Application
```bash
cd frontend
npm run dev
```
Frontend Web App will be accessible at: `http://localhost:3000`

---

## 🔑 Account Access & User Creation

To create your initial administrator, staff, and citizen accounts securely:
```bash
cd backend
source venv/bin/activate
python manage.py createsuperuser
```
Citizens and Community Organizations can also register directly via the **Sign Up** page in the application.

