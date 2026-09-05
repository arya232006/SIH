import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from app.models import (
    PatientSession, PatientRegistration, HistoryOfPresentIllness,
    DrugAllergyHistory, PersonalHistory, PriorInvestigation, RedFlag, QAPair
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "medikiosk.db")

class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, PatientSession] = {}
        self._token_counter: int = 40
        self._init_sqlite()
        self._load_from_sqlite()
        if len(self._sessions) == 0:
            self._seed_sample_patients()

    def _init_sqlite(self):
        """Initializes lightweight SQLite database for session persistence."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS patient_sessions (
                        session_id TEXT PRIMARY KEY,
                        patient_id TEXT,
                        visit_id TEXT,
                        token_number TEXT,
                        patient_name TEXT,
                        status TEXT,
                        data_json TEXT,
                        updated_at TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"[SessionStore] SQLite init warning: {e}")

    def _load_from_sqlite(self):
        """Loads sessions from SQLite on startup."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT session_id, data_json FROM patient_sessions")
                rows = cursor.fetchall()
                for s_id, data_str in rows:
                    try:
                        data = json.loads(data_str)
                        session = PatientSession(**data)
                        self._sessions[s_id] = session
                    except Exception as parse_err:
                        print(f"[SessionStore] Error parsing row {s_id}: {parse_err}")
        except Exception as e:
            print(f"[SessionStore] SQLite load warning: {e}")

    def _save_to_sqlite(self, session: PatientSession):
        """Persists a single session to SQLite."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO patient_sessions 
                    (session_id, patient_id, visit_id, token_number, patient_name, status, data_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.sessionId,
                    session.patientId,
                    session.visitId,
                    session.tokenNumber,
                    session.patientName,
                    session.status,
                    session.model_dump_json(),
                    session.updatedAt
                ))
                conn.commit()
        except Exception as e:
            print(f"[SessionStore] SQLite save warning: {e}")

    def _generate_token(self) -> str:
        self._token_counter += 1
        return f"OPD-{self._token_counter:03d}"

    def _generate_visit_id(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"OPD-{today}-{uuid.uuid4().hex[:5].upper()}"

    def create_session(self, reg: PatientRegistration) -> PatientSession:
        session_id = f"session_{uuid.uuid4().hex[:10]}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        patient_id = reg.abhaId if reg.abhaId and reg.abhaId.strip() else f"NEW-{uuid.uuid4().hex[:8].upper()}"
        token = self._generate_token()
        visit_id = self._generate_visit_id()

        session = PatientSession(
            sessionId=session_id,
            patientId=patient_id,
            visitId=visit_id,
            tokenNumber=token,
            patientName=reg.fullName,
            age=reg.age,
            gender=reg.gender,
            language=reg.language,
            ayushMode=reg.ayushMode or (reg.medicalSystem == "ayurveda"),
            homeopathyMode=reg.homeopathyMode or (reg.medicalSystem == "homeopathy"),
            medicalSystem=reg.medicalSystem if reg.medicalSystem != "allopathy" else ("homeopathy" if reg.homeopathyMode else ("ayurveda" if reg.ayushMode else "allopathy")),
            connectivityStatus="online",
            flaggedForStaff=False,
            chiefComplaint="",
            historyOfPresentIllness=HistoryOfPresentIllness(),
            pastMedicalHistory=[],
            drugAllergyHistory=DrugAllergyHistory(),
            familyHistory=[],
            personalHistory=PersonalHistory(),
            reviewOfSystems="",
            priorInvestigations=[],
            redFlag=RedFlag(),
            fieldProvenance={},
            enteredByStaffId=None,
            physicianReviewStatus="Pending confirmation",
            physicianNotes="",
            sectionReviews={},
            conversationTurns=[],
            createdAt=now,
            updatedAt=now,
            status="in_progress",
            version=1
        )
        self._sessions[session_id] = session
        self._save_to_sqlite(session)
        return session

    def get_session(self, session_id: str) -> Optional[PatientSession]:
        """Finds session by sessionId, patientId, visitId, or tokenNumber."""
        if not session_id:
            return None
            
        # 1. Direct match by sessionId key
        if session_id in self._sessions:
            return self._sessions[session_id]
            
        # 2. Match by any alias (patientId, visitId, tokenNumber, sessionId)
        for s_id, s in self._sessions.items():
            if (
                s.sessionId == session_id
                or s.patientId == session_id
                or s.visitId == session_id
                or s.tokenNumber == session_id
            ):
                return s
                
        return None

    def update_session(self, session_id: str, session: PatientSession) -> PatientSession:
        session.version += 1
        session.updatedAt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        key = session.sessionId if session.sessionId in self._sessions else session_id
        self._sessions[key] = session
        self._save_to_sqlite(session)
        return session

    def list_all_sessions(self) -> List[PatientSession]:
        return list(self._sessions.values())

    def get_physician_queue(self) -> List[dict]:
        """Returns sessions ready or reviewed by physician, sorted by triage priority (red flags first)."""
        queue = []
        for s_id, s in self._sessions.items():
            # Include confirmed, in_review, completed, or emergency red flag cases
            if s.status in ["confirmed", "in_physician_review", "completed"] or s.redFlag.triggered:
                queue.append({
                    "sessionId": s.sessionId,
                    "tokenNumber": s.tokenNumber,
                    "patientId": s.patientId,
                    "visitId": s.visitId,
                    "patientName": s.patientName,
                    "age": s.age,
                    "gender": s.gender,
                    "chiefComplaint": s.chiefComplaint or "General OPD Consultation",
                    "redFlag": s.redFlag,
                    "departmentRouting": s.departmentRouting,
                    "ayushMode": s.ayushMode,
                    "docCount": len(s.priorInvestigations),
                    "physicianReviewStatus": s.physicianReviewStatus,
                    "enteredByStaffId": s.enteredByStaffId,
                    "createdAt": s.createdAt,
                    "status": s.status,
                    "version": s.version
                })
        
        # Sort: Red flag triggered first, then descending token number
        queue.sort(key=lambda x: (not x["redFlag"].triggered, x["tokenNumber"]))
        return queue

    def get_staff_monitoring_list(self) -> List[dict]:
        """Returns active kiosk sessions prioritized by connectivity alerts and flags."""
        monitored = []
        for s_id, s in self._sessions.items():
            monitored.append({
                "sessionId": s.sessionId,
                "tokenNumber": s.tokenNumber,
                "patientId": s.patientId,
                "patientName": s.patientName,
                "age": s.age,
                "gender": s.gender,
                "connectivityStatus": s.connectivityStatus,
                "flaggedForStaff": s.flaggedForStaff,
                "staffCallActive": s.staffCallActive,
                "staffCallReason": s.staffCallReason,
                "departmentRouting": s.departmentRouting,
                "chiefComplaint": s.chiefComplaint,
                "redFlag": s.redFlag,
                "enteredByStaffId": s.enteredByStaffId,
                "turnsCount": len(s.conversationTurns),
                "status": s.status,
                "updatedAt": s.updatedAt,
                "version": s.version
            })
        
        # Sort: Flagged or Offline first
        def sort_key(item):
            is_offline = item["connectivityStatus"] == "offline"
            is_flagged = item["flaggedForStaff"]
            is_degraded = item["connectivityStatus"] == "degraded"
            return (not (is_offline or is_flagged), not is_degraded, item["tokenNumber"])

        monitored.sort(key=sort_key)
        return monitored

    def get_emergency_queue(self) -> List[dict]:
        """
        Returns ONLY patients with active emergency Red Flags (redFlag.triggered == True)
        who have not completed consultation, prioritized by triage urgency (emergency > urgent > routine).
        """
        emergency_list = []
        for s_id, s in self._sessions.items():
            if s.redFlag and s.redFlag.triggered and s.status != "completed":
                emergency_list.append({
                    "sessionId": s.sessionId,
                    "patientId": s.patientId,
                    "tokenNumber": s.tokenNumber,
                    "visitId": s.visitId,
                    "patientName": s.patientName,
                    "age": s.age,
                    "gender": s.gender,
                    "chiefComplaint": s.chiefComplaint,
                    "historyOfPresentIllness": s.historyOfPresentIllness,
                    "drugAllergyHistory": s.drugAllergyHistory,
                    "pastMedicalHistory": s.pastMedicalHistory,
                    "redFlag": s.redFlag,
                    "departmentRouting": s.departmentRouting,
                    "staffCallActive": s.staffCallActive,
                    "status": s.status,
                    "physicianReviewStatus": s.physicianReviewStatus,
                    "createdAt": s.createdAt,
                    "updatedAt": s.updatedAt,
                    "version": s.version,
                    "assignedBed": s.assignedBed,
                    "emergencyActionLog": s.emergencyActionLog
                })

        def emergency_sort_key(item):
            urgency_score = 0
            urgency = (item["redFlag"].urgency if hasattr(item["redFlag"], "urgency") else "routine") or "routine"
            if urgency == "emergency":
                urgency_score = 3
            elif urgency == "urgent":
                urgency_score = 2
            else:
                urgency_score = 1
            return (-urgency_score, item["updatedAt"])

        emergency_list.sort(key=emergency_sort_key)
        return emergency_list

    def _seed_sample_patients(self):
        """Pre-seeds realistic sample OPD patients for live demonstration."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Emergency Red-Flag Patient: Ramesh Kumar (Chest pain radiating to arm)
        s1 = PatientSession(
            sessionId="session_seed_ramesh",
            patientId="ABHA-14-9821-3401-9012",
            visitId="OPD-2026-08-25-00401",
            tokenNumber="OPD-041",
            patientName="Ramesh Kumar Verma",
            age=58,
            gender="Male",
            language="hi",
            ayushMode=False,
            connectivityStatus="online",
            flaggedForStaff=False,
            chiefComplaint="Sudden severe retrosternal chest pain with left arm numbness and breathlessness",
            historyOfPresentIllness=HistoryOfPresentIllness(
                onset="2 hours ago while climbing stairs at home",
                site="Substernal chest radiating down inner left arm and jaw",
                character="Heavy, squeezing pressure like an elephant sitting on chest (9/10)",
                radiation="Left arm and shoulder",
                aggravating="Physical exertion",
                relieving="Rest gave only partial relief",
                associatedSymptoms=["Profuse cold sweating", "Shortness of breath (Dyspnea)", "Mild dizziness"]
            ),
            pastMedicalHistory=["Type 2 Diabetes Mellitus (8 years)", "Hypertension (5 years)"],
            drugAllergyHistory=DrugAllergyHistory(
                currentMedications=["Tab. Telmisartan 40mg OD", "Tab. Metformin 500mg BD"],
                allergies="No known drug allergies (NKDA)"
            ),
            familyHistory=["Father had myocardial infarction at age 62"],
            personalHistory=PersonalHistory(
                diet="Vegetarian",
                smoking="Former smoker (Quit 3 years ago, 15 pack-years)",
                alcohol="Occasional social drinker"
            ),
            reviewOfSystems="Cardiovascular: Chest pressure and palpitations. Respiratory: Dyspnea on minimal effort. No GI symptoms.",
            priorInvestigations=[
                PriorInvestigation(
                    id="doc_seed_01",
                    document="Apollo Diagnostics Lipid Profile",
                    documentType="lab_report",
                    extracted={
                        "laboratory": "Apollo Diagnostics, New Delhi",
                        "test_date": "2026-08-10",
                        "investigations": [
                            {"test": "Total Cholesterol", "value": "242", "unit": "mg/dL", "ref_range": "< 200", "flag": "HIGH"},
                            {"test": "LDL Cholesterol", "value": "168", "unit": "mg/dL", "ref_range": "< 100", "flag": "HIGH"},
                            {"test": "HDL Cholesterol", "value": "35", "unit": "mg/dL", "ref_range": "> 40", "flag": "LOW"},
                            {"test": "Serum Triglycerides", "value": "210", "unit": "mg/dL", "ref_range": "< 150", "flag": "HIGH"}
                        ]
                    },
                    flag="High LDL (168 mg/dL) & Low HDL (35 mg/dL)",
                    confidence=0.97,
                    isSample=True,
                    timestamp="2026-08-25 10:15",
                    status="success",
                    extractionSource="sample_curated"
                )
            ],
            redFlag=RedFlag(
                triggered=True,
                reason="Potential Acute Coronary Syndrome (Chest pain with radiation to left arm and cold diaphoresis)",
                action="IMMEDIATE TRIAGE: Transfer to Emergency / ECG & Troponin stat",
                urgency="emergency"
            ),
            fieldProvenance={
                "chiefComplaint": "patient-conversation",
                "historyOfPresentIllness": "patient-conversation",
                "pastMedicalHistory": "patient-conversation",
                "drugAllergyHistory": "patient-conversation",
                "familyHistory": "patient-conversation",
                "personalHistory": "patient-conversation",
                "priorInvestigations": "document-extraction"
            },
            enteredByStaffId=None,
            physicianReviewStatus="Pending confirmation",
            physicianNotes="",
            sectionReviews={},
            conversationTurns=[
                QAPair(questionId="q1", field="onset", questionText="When did this chest pain begin?", patientAnswer="Started suddenly 2 hours ago", mode="voice", timestamp="10:10"),
                QAPair(questionId="q2", field="radiation", questionText="Does the pain spread anywhere?", patientAnswer="Spreads down left arm and neck", mode="voice", timestamp="10:11"),
                QAPair(questionId="q3", field="associated", questionText="Any breathlessness or sweating?", patientAnswer="Heavy cold sweating and breathlessness", mode="tap", timestamp="10:12")
            ],
            createdAt=now,
            updatedAt=now,
            status="confirmed",
            version=1
        )
        self._sessions["session_seed_ramesh"] = s1
        self._save_to_sqlite(s1)

        # 2. AYUSH Intake Patient: Harish Patel (Hyperacidity / Pitta Prakriti)
        s2 = PatientSession(
            sessionId="session_seed_harish",
            patientId="ABHA-22-1092-8834-5511",
            visitId="OPD-2026-08-25-00402",
            tokenNumber="OPD-042",
            patientName="Harish N. Patel",
            age=44,
            gender="Male",
            language="en",
            ayushMode=True,
            connectivityStatus="online",
            flaggedForStaff=False,
            chiefComplaint="Chronic acid regurgitation, epigastric burning (Amlapitta) and irregular digestion",
            historyOfPresentIllness=HistoryOfPresentIllness(
                onset="Last 3 weeks, aggravated after late dinners and spicy foods",
                site="Epigastrium and retrosternal burning (Urdhwaga Amlapitta)",
                character="Sour belching, burning sensation in throat and chest",
                radiation="None",
                aggravating="Spicy foods, tea on empty stomach, irregular meal times",
                relieving="Cold milk gives transient cooling relief",
                associatedSymptoms=["Bloating", "Headache after skipping lunch", "Irritability"],
                ayushDetails={
                    "prakriti": "Pitta-Vata (Medium build, prone to body heat, low tolerance to hunger)",
                    "agni": "Tikshnagni (Intense burning hunger, quick metabolism with hyperacidity)",
                    "kostha": "Madhyama Kostha (Regular bowel habit, occasional loose stools with spicy food)",
                    "ahara_vihara": "High intake of tea/coffee, spicy curries, irregular sleep patterns (Ratrijagarana)"
                }
            ),
            pastMedicalHistory=["Gastritis (diagnosed 2 years ago)"],
            drugAllergyHistory=DrugAllergyHistory(
                currentMedications=["Cap. Pantocid 40mg (taken intermittently)", "Avipattikar Churna 1 tsp hs"],
                allergies="No known allergies"
            ),
            familyHistory=["Mother had history of peptic ulcer"],
            personalHistory=PersonalHistory(
                diet="Vegetarian (Spicy, fried snacks)",
                smoking="Non-smoker",
                alcohol="Non-drinker"
            ),
            reviewOfSystems="Gastrointestinal: Acidity and sour eructations. CNS: Sleep disturbances due to late work hours.",
            priorInvestigations=[],
            redFlag=RedFlag(triggered=False, reason="", action="", urgency="routine"),
            fieldProvenance={
                "chiefComplaint": "patient-conversation",
                "historyOfPresentIllness": "patient-conversation",
                "pastMedicalHistory": "patient-conversation",
                "drugAllergyHistory": "patient-conversation",
                "familyHistory": "patient-conversation",
                "personalHistory": "patient-conversation"
            },
            enteredByStaffId=None,
            physicianReviewStatus="Pending confirmation",
            physicianNotes="",
            sectionReviews={},
            conversationTurns=[
                QAPair(questionId="q1", field="prakriti_assessment", questionText="Describe your body constitution and heat tolerance.", patientAnswer="Medium build / Prone to heat / Sweats easily (Pitta)", mode="tap", timestamp="10:20"),
                QAPair(questionId="q2", field="agni_digestion", questionText="How is your digestion and hunger regularity?", patientAnswer="Intense burning hunger & thirst (Tikshnagni)", mode="tap", timestamp="10:21")
            ],
            createdAt=now,
            updatedAt=now,
            status="confirmed",
            version=1
        )
        self._sessions["session_seed_harish"] = s2
        self._save_to_sqlite(s2)

        # 3. Staff Takeover Patient: Meena Devi (65/F) - Kiosk disconnected, manual intake by Nurse Priya
        s3 = PatientSession(
            sessionId="session_seed_meena",
            patientId="ABHA-88-7712-4409-1133",
            visitId="OPD-2026-08-25-00403",
            tokenNumber="OPD-043",
            patientName="Meena Devi Gupta",
            age=65,
            gender="Female",
            language="hi",
            ayushMode=False,
            connectivityStatus="offline",
            flaggedForStaff=True,
            chiefComplaint="Bilateral knee joint pain (Sandhivata) and morning stiffness x 6 months",
            historyOfPresentIllness=HistoryOfPresentIllness(
                onset="Gradual worsening over last 6 months, difficulty standing from squatting position",
                site="Bilateral knees (Right > Left)",
                character="Dull aching pain with crepitus on walking and climbing stairs",
                radiation="Down to upper calf muscles",
                aggravating="Cold weather, prolong standing, carrying household weight",
                relieving="Rest, hot fomentation and topical pain balm",
                associatedSymptoms=["Morning joint stiffness for ~20 mins", "Mild swelling in right knee"]
            ),
            pastMedicalHistory=["Primary Osteoarthritis Knees", "Osteopenia"],
            drugAllergyHistory=DrugAllergyHistory(
                currentMedications=["Tab. Calcium Carbonate 500mg OD", "Tab. Paracetamol 650mg SOS"],
                allergies="Allergic to NSAIDs (Diclofenac causes gastric burning)"
            ),
            familyHistory=["Elder sister has knee osteoarthritis"],
            personalHistory=PersonalHistory(
                diet="Vegetarian",
                smoking="Non-smoker",
                alcohol="Non-drinker"
            ),
            reviewOfSystems="Musculoskeletal: Knee joint crepitus and restricted flexion. No fever, no systemic rash.",
            priorInvestigations=[
                PriorInvestigation(
                    id="doc_seed_03",
                    document="X-Ray Both Knees (AP/Lateral Standing)",
                    documentType="other",
                    extracted={
                        "radiology_clinic": "Govt Hospital Radiodiagnosis Wing",
                        "findings": "Reduction of medial joint space in both knees (Right > Left). Subchondral sclerosis with marginal osteophytes.",
                        "impression": "Bilateral Osteoarthritis Knees (Kellgren-Lawrence Grade III)"
                    },
                    flag="Grade III Osteoarthritis with Medial Joint Space Narrowing",
                    confidence=0.91,
                    isSample=True,
                    timestamp="2026-08-25 09:30",
                    status="success",
                    extractionSource="sample_curated"
                )
            ],
            redFlag=RedFlag(triggered=False, reason="", action="", urgency="routine"),
            fieldProvenance={
                "chiefComplaint": "staff-manual",
                "historyOfPresentIllness": "staff-manual",
                "pastMedicalHistory": "staff-manual",
                "drugAllergyHistory": "staff-manual",
                "familyHistory": "staff-manual",
                "personalHistory": "staff-manual",
                "reviewOfSystems": "staff-manual",
                "priorInvestigations": "document-extraction"
            },
            enteredByStaffId="STAFF-OPD-101",
            physicianReviewStatus="Pending confirmation",
            physicianNotes="Manual intake completed by Sister Priya due to OPD Kiosk #2 temporary network drop. Patient verified details.",
            sectionReviews={},
            conversationTurns=[],
            createdAt=now,
            updatedAt=now,
            status="confirmed",
            version=1
        )
        self._sessions["session_seed_meena"] = s3
        self._save_to_sqlite(s3)

session_store = SessionStore()
