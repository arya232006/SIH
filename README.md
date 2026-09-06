# MediKiosk (मेडीकियोस्क) 🩺
> **AI-Powered Clinical Pre-Consultation History Platform for Indian Hospital OPDs**

MediKiosk is an intelligent, patient-centric clinical intake and triage platform designed to streamline outpatient department (OPD) workflows across Indian government and private hospitals.

---

## 🌟 Key Highlights & Architectural Overview

- **🗣️ Multilingual Patient Intake**: Supports English, Hindi, Bengali, Tamil, and Telugu with voice-first and guided touch-chip interactions.
- **🧠 Adaptive LLM Conversational History**: Real LLM calls (swappable: Google Gemini Flash, Groq Llama 3.3, OpenRouter) dynamically formulate the next SOCRATES question based on the patient's previous response — not a pre-scripted decision tree.
- **🌿 AYUSH Dashavidha Pariksha Support**: Dedicated toggle switches the intake ontology to Ayurvedic Ten-Fold Assessment (Prakriti, Agni, Kostha, Ahara/Vihara).
- **🚨 Non-LLM Clinical Safety Red-Flag Guardrail**: Deterministic rule-based engine running independently of the LLM on every conversation turn to identify emergencies (Acute Coronary Syndrome, Stroke, Acute Hemorrhage, Anaphylaxis) and trigger immediate triage alerts.
- **📄 Dual-Path Document OCR & Anomaly Detection**: Genuine Vision-LLM extraction pipeline for real camera/photo uploads alongside an honest "Try a sample document instead" demo mode with 3 pre-bundled authentic medical templates (Printed Lab Report with High LDL/Glucose alerts, Printed Cardiology Rx, Handwritten Rx).
- **📊 Traceable Fact Provenance**: Full audit provenance tagging (`from conversation`, `from uploaded document`, `entered manually by staff`) across every clinical section.
- **👨‍⚕️ Physician Review Dashboard**: Priority queue sorting red flags first, inline section-by-section Accept/Amend/Reject governance, and EHR/ABHA linkage.
- **🛡️ Staff Operator Failover & Reconnection Guard**: Hospital staff dashboard with real-time WebSocket connectivity heartbeat (`online`, `degraded`, `offline`), manual takeover with `staff-manual` provenance, and non-destructive reconnection resolution.

---

## 🏗️ Project Architecture

```
MediKiosk/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint & WebSocket handler
│   │   ├── config.py                   # Swappable LLM providers (Gemini / Groq / OpenRouter)
│   │   ├── models.py                   # Strict Pydantic models for full clinical schema
│   │   ├── store.py                    # Session store with realistic pre-seeded OPD cases
│   │   ├── services/
│   │   │   ├── llm_service.py          # Adaptive question engine (SOCRATES & AYUSH Dashavidha)
│   │   │   ├── red_flag_service.py     # Deterministic non-LLM emergency pattern detector
│   │   │   ├── ocr_service.py          # Multimodal vision OCR & lab anomaly detector
│   │   │   └── staff_service.py        # Staff auth, session monitoring, manual entry & WebSocket broadcaster
│   │   └── sample_docs/                # Bundled sample document images (Lab report, Printed Rx, Handwritten Rx)
│   ├── tests/
│   │   └── test_api.py                 # Automated pytest test suite (6 passing test suites)
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.tsx         # Persona selector (Kiosk, Physician, Staff)
│   │   │   ├── Kiosk/                  # 4-step Patient Kiosk (Identify, Converse, Scan, Summarize)
│   │   │   ├── Physician/              # Physician Queue & Structured Note Review
│   │   │   └── Staff/                  # Staff Operator Monitoring & Manual Takeover
│   │   ├── components/                 # Navbar, AudioVisualizer, ProvenanceTag, AbnormalBadge
│   │   ├── services/api.ts             # API client & connectivity manager
│   │   ├── utils/i18n.ts               # Multilingual translations (en, hi, bn, ta, te)
│   │   └── types/index.ts              # TypeScript schemas
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ (Python 3.14 supported)
- Node.js v18+ & pnpm / npm

---

### Step 1: Start Backend (FastAPI)

```bash
cd backend

# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Configure Free-Tier LLM API Keys
cp .env.example .env
# Edit .env with your free Gemini or Groq API key

# 3. Run Backend Server
uvicorn app.main:app --reload --port 8000
```
Backend API will run at `http://localhost:8000` (Swagger docs: `http://localhost:8000/docs`).

---

### Step 2: Start Frontend (React + Vite + Tailwind)

```bash
cd frontend

# 1. Install dependencies
pnpm install  # or npm install

# 2. Start Vite Dev Server
pnpm dev      # or npm run dev
```
Frontend Web App will open at `http://localhost:5173`.

---

## 🧪 Run Automated Tests

To run the backend automated pytest suite:
```bash
cd backend
python -m pytest tests/ -v
```

---

## 🔑 Pre-Registered Staff Accounts

For logging into the **Staff Operator Portal** (`/staff`):
- `nurse_priya` / `hospital123` (Sister Priya Sharma — OPD Triage Staff Nurse)
- `admin_raj` / `admin123` (Rajesh Varma — Kiosk & IT Operator)
- `sister_anita` / `nurse123` (Anita Sen — Senior Staff Nurse)


---

## 📋 Data Model (ABDM & DPDP Compliant)

```json
{
  "patientId": "ABHA-14-9821-3401-9012",
  "visitId": "OPD-2026-08-25-00417",
  "connectivityStatus": "online",
  "flaggedForStaff": false,
  "chiefComplaint": "Severe retrosternal chest pain radiating to left arm",
  "historyOfPresentIllness": {
    "onset": "2 hours ago while climbing stairs",
    "site": "Substernal chest",
    "character": "Heavy squeezing pressure (9/10)",
    "radiation": "Left arm and shoulder",
    "aggravating": "Physical exertion",
    "relieving": "Rest gives partial relief",
    "associatedSymptoms": ["Cold sweating", "Shortness of breath"]
  },
  "pastMedicalHistory": ["Type 2 Diabetes Mellitus (8 yrs)", "Hypertension (5 yrs)"],
  "drugAllergyHistory": {
    "currentMedications": ["Tab. Telmisartan 40mg OD", "Tab. Metformin 500mg BD"],
    "allergies": "No known drug allergies (NKDA)"
  },
  "familyHistory": ["Father had myocardial infarction at 62"],
  "personalHistory": {
    "diet": "Vegetarian",
    "smoking": "Former smoker",
    "alcohol": "Occasional"
  },
  "reviewOfSystems": "Cardiovascular: Chest pressure. Respiratory: Dyspnea.",
  "priorInvestigations": [
    {
      "document": "Apollo Diagnostics Lipid Profile",
      "extracted": { "LDL Cholesterol": "168 mg/dL", "HbA1c": "8.2%" },
      "flag": "High LDL (168 mg/dL) & HbA1c (8.2%) Detected"
    }
  ],
  "redFlag": {
    "triggered": true,
    "reason": "Potential Acute Coronary Syndrome",
    "action": "IMMEDIATE TRIAGE: Direct to Emergency Room for ECG & Troponin"
  },
  "fieldProvenance": {
    "chiefComplaint": "patient-conversation",
    "historyOfPresentIllness": "patient-conversation",
    "priorInvestigations": "document-extraction"
  },
  "enteredByStaffId": null,
  "physicianReviewStatus": "Pending confirmation"
}
```

