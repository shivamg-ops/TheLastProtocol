# JANSAHAYAK AI — 3-MINUTE LIVE HACKATHON DEMO SCRIPT

**Pitch Theme**: *From Voice to Resolution — Autonomous Multilingual Civic Grievance Management*  
**Duration**: Exactly 3 Minutes (180 Seconds)  
**Target Audience**: Hackathon Judges, Civic Tech Evaluators, and Engineers  

---

### ACT 1: THE PROBLEM & CITIZEN VOICE INTAKE (0:00 – 1:00)

**Spoken Narration**:
> *"India has over 800 million smartphone users, yet municipal grievance portals remain text-heavy, English-centric, and bureaucratic. When a citizen sees an open manhole or an overflowing garbage dump, they don't know the exact municipal department code or ward number.*
> *Meet **JanSahayak AI** — a conversational, multilingual voice agent that transforms spoken grievances in Hindi, Marathi, Hinglish, or English into structured, actionable municipal tickets."*

**Live Action on Screen**:
1. Open **`http://localhost:3000`** — showcase modern, clean landing page.
2. Click **Voice / AI Report** (`/report`).
3. Click the **Microphone** icon (or type):
   > *"Hamare gali me kachra pada hai aur badboo aa rahi hai."*
4. **Show AI Prompting for Missing Info**: The AI responds in Hindi/Hinglish: *"Maine aapki complaint note kar li hai. Kya aap please exact location ya landmark share kar sakte hain?"*
5. Follow up with:
   > *"Near Shiv Mandir, Ward 5."*
6. **Show Right Pane**: Live structured preview card auto-populates:
   - **Category**: *Garbage and Sanitation*
   - **Priority**: *High*
   - **Location**: *Near Shiv Mandir*
   - **Ward**: *Ward 5*
7. Click the **Camera** icon, attach a photo, and click **Confirm & Submit Complaint**.
8. **Show Output**: Unique tracking ID generated (e.g. `JSH-9C9F6394`) with green confirmation that photo evidence was uploaded and linked.

---

### ACT 2: MUNICIPAL ADMIN TRIAGE & DISPATCH (1:00 – 2:00)

**Spoken Narration**:
> *"Once submitted, municipal officers don't receive raw, unstructured text. The ticket is classified by department SLA, checked for duplicates, and queued in the Command Centre."*

**Live Action on Screen**:
1. Log in as **`admin`** (`adminpassword123`) and open **`/admin`**.
2. **Showcase Metrics Grid**: Real-time totals, pending triage, active field tasks, and resolution rate (computed live from Django ORM, 0 fake data).
3. Find the newly submitted ticket in **All Civic Tickets**.
4. Click **Dispatch Staff**:
   - Show the dynamic **Staff Member Dropdown** (fetching active field officers from the authenticated staff directory).
   - Select **Ramesh Shinde (staff1) • Zone 4 Field Action Unit**.
   - Click **Confirm Assignment**.
   - The ticket status immediately updates to `ASSIGNED` with SLA countdown.

---

### ACT 3: FIELD RESOLUTION & CITIZEN VERIFICATION (2:00 – 3:00)

**Spoken Narration**:
> *"Now let's switch to the field officer on the ground. Once the work is done, JanSahayak enforces accountability by requiring photographic proof of resolution before a ticket can be closed."*

**Live Action on Screen**:
1. Switch browser or log in as **`staff1`** (`staffpassword123`) and open **`/staff`**.
2. Select the assigned ticket.
3. Select status: **Resolved (Work Completed)**.
4. Add Field Note: *"Cleared 2 tons of waste and sanitized area with disinfectant powder."*
5. Attach **Resolution Proof Photo** (`resolution_proof.jpg`) and click **Commit Status & Notify Citizen**.
6. Switch back to **`/citizen`** as **`citizen1`**:
   - The ticket shows status `Resolved`.
   - Click the eye icon: citizen inspects both the **Reported Evidence** and the staff's **Resolution Proof**.
   - Citizen rates resolution: Click **5 Stars**, add a note: *"Very fast cleanup, thank you!"*, and click **Confirm & Submit Rating**.
   - The ticket permanently marks as `Verified by Citizen`.

**Closing Sentence**:
> *"With JanSahayak AI, municipal governance becomes conversational, transparent, and accountable — from voice to resolution in under 3 minutes."*

