import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from fastapi import (
    FastAPI, HTTPException, UploadFile, File, WebSocket, 
    WebSocketDisconnect, Query, Header, Depends, status, Body
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import io
import urllib.parse
import httpx

from app.config import settings
from app.models import (
    PatientRegistration, PatientSession, PatientAnswerRequest,
    AdaptiveQuestionResponse, QAPair, DocumentManualCorrectionRequest,
    StaffLoginRequest, StaffTakeoverRequest, ConnectivityUpdateRequest,
    PhysicianSectionReviewRequest, StaffAccount, AudioTranscriptionResponse,
    DepartmentRouting, StaffCallRequest, DepartmentAssignmentRequest,
    CDSSResponse, EmergencyActionRequest, MedicationClarificationPlan,
    MedicationClarificationAnswerRequest, MedicationClarificationAnswerResponse,
    ExtractedMedicationItem, PainAssessment, SafetyCheckResponse,
    TriageAcuityScore, PrescriptionOrder, PrescriptionItem, FHIRBundleResponse,
    PrescriptionGenerateRequest, HistoryOfPresentIllness, DrugAllergyHistory
)
from app.store import session_store
from app.services.red_flag_service import red_flag_detector
from app.services.llm_service import llm_service
from app.services.routing_service import routing_service
from app.services.ocr_service import ocr_service, SAMPLE_DOCS_DIR, UPLOADS_DIR
from app.services.staff_service import staff_service
from app.services.audio_service import audio_service
from app.services.medication_clarification_service import MedicationClarificationService
from app.services.ddi_service import DDIService
from app.services.triage_service import TriageService
from app.services.fhir_service import FHIRService
from app.services.drug_matching_service import DrugMatchingService

# Ensure sample images exist on disk on startup
ocr_service.ensure_sample_images_exist()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MediKiosk AI Clinical History Platform API — FastAPI Backend",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Staff Auth Dependency ---
async def get_current_staff(authorization: Optional[str] = Header(None)) -> StaffAccount:
    """Verifies Bearer token for protected staff routes."""
    if not authorization:
        # Check query param or fallback for prototype
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff authentication token required. Please sign in."
        )
    staff = staff_service.verify_token(authorization)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired staff token."
        )
    return staff

# --- Health Check ---
@app.get("/api/healthz")
async def health_check():
    return {
        "status": "healthy",
        "service": "MediKiosk Backend",
        "llm_provider": settings.LLM_PROVIDER,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY),
        "openrouter_configured": bool(settings.OPENROUTER_API_KEY),
        "timestamp": datetime.now().isoformat()
    }

# --- KIOSK SESSION ENDPOINTS ---

@app.post("/api/session/start", response_model=PatientSession)
async def start_session(reg: PatientRegistration):
    """
    Initializes a new patient kiosk intake session.
    """
    session = session_store.create_session(reg)
    return session

@app.get("/api/session/{session_id}", response_model=PatientSession)
async def get_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.post("/api/session/{session_id}/answer")
async def submit_answer(session_id: str, req: PatientAnswerRequest):
    """
    Submits patient response (voice/tap/manual), evaluates safety red flags,
    and returns next adaptive question from the LLM.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # If first turn or chief complaint field, set chief complaint
    if not session.chiefComplaint or req.field == "chief_complaint":
        session.chiefComplaint = req.answer
        session.fieldProvenance["chiefComplaint"] = "patient-conversation"
    else:
        # Append QA turn with proper field key and question text
        turn_num = len(session.conversationTurns) + 1
        field_key = req.field if req.field else f"clinical_turn_{turn_num}"
        q_text = req.questionText if req.questionText else f"Clinical triage question {turn_num}"
        session.conversationTurns.append(QAPair(
            questionId=f"q{turn_num}",
            field=field_key,
            questionText=q_text,
            patientAnswer=req.answer,
            mode=req.mode,
            timestamp=datetime.now().strftime("%H:%M:%S")
        ))

    if req.medicalSystem:
        session.medicalSystem = req.medicalSystem
        if req.medicalSystem == "ayurveda":
            session.ayushMode = True
        elif req.medicalSystem == "homeopathy":
            session.homeopathyMode = True

    # 1. Non-LLM Red Flag Safety Check (Independent of LLM)
    red_flag = red_flag_detector.evaluate(session.chiefComplaint, session.conversationTurns)
    session.redFlag = red_flag

    if red_flag.triggered:
        # Broadcast priority alert to staff
        await staff_service.broadcast_event("red_flag_alert", {
            "sessionId": session.sessionId,
            "patientName": session.patientName,
            "tokenNumber": session.tokenNumber,
            "reason": red_flag.reason,
            "action": red_flag.action,
            "urgency": red_flag.urgency
        })

    # 2. Adaptive LLM Question Generation
    adaptive_resp = await llm_service.get_next_question(
        chief_complaint=session.chiefComplaint,
        conversation_turns=session.conversationTurns,
        ayush_mode=session.ayushMode or req.ayushMode or (session.medicalSystem == "ayurveda"),
        homeopathy_mode=session.homeopathyMode or req.homeopathyMode or (session.medicalSystem == "homeopathy"),
        medical_system=req.medicalSystem or session.medicalSystem or "allopathy",
        language=session.language,
        red_flag_active=red_flag.triggered
    )

    # 3. Structure clinical summary in background
    structured = llm_service.structure_history_summary(
        session.chiefComplaint,
        session.conversationTurns,
        ayush_mode=session.ayushMode or req.ayushMode or (session.medicalSystem == "ayurveda"),
        homeopathy_mode=session.homeopathyMode or req.homeopathyMode or (session.medicalSystem == "homeopathy"),
        medical_system=req.medicalSystem or session.medicalSystem or "allopathy"
    )
    session.historyOfPresentIllness = structured["historyOfPresentIllness"]
    session.pastMedicalHistory = structured["pastMedicalHistory"]
    session.drugAllergyHistory = structured["drugAllergyHistory"]
    session.familyHistory = structured["familyHistory"]
    session.personalHistory = structured["personalHistory"]
    session.reviewOfSystems = structured["reviewOfSystems"]
    session.vitals = structured.get("vitals", session.vitals)
    session.nurseSummary = structured["nurseSummary"]
    session.pertinentPositives = structured["pertinentPositives"]
    session.pertinentNegatives = structured["pertinentNegatives"]
    session.nurseRecommendations = structured.get("nurseRecommendations", [])
    session.triageAcuity = structured.get("triageAcuity", "Routine")
    # 4. Determine Automated Department & Specialist Doctor Routing
    if session.fieldProvenance.get("departmentRouting") != "staff-manual":
        routing = routing_service.determine_routing(
            chief_complaint=session.chiefComplaint,
            conversation_turns=session.conversationTurns,
            age=session.age,
            red_flag_triggered=session.redFlag.triggered,
            ayush_mode=session.ayushMode or req.ayushMode or (session.medicalSystem == "ayurveda"),
            homeopathy_mode=session.homeopathyMode or req.homeopathyMode or (session.medicalSystem == "homeopathy"),
            medical_system=req.medicalSystem or session.medicalSystem or "allopathy"
        )
        session.departmentRouting = routing

        # If ambiguous, notify staff triage dashboard
        if routing.isAmbiguous and not session.staffCallActive:
            session.flaggedForStaff = True
            session.staffCallActive = True
            session.staffCallReason = routing.routingReason
            await staff_service.broadcast_event("staff_call", {
                "sessionId": session.sessionId,
                "patientName": session.patientName,
                "tokenNumber": session.tokenNumber,
                "reason": routing.routingReason,
                "isAmbiguous": True,
                "kioskId": "KIOSK-01"
            })

    # Set provenance for generated fields if not already staff-manual
    for f_key in ["historyOfPresentIllness", "pastMedicalHistory", "drugAllergyHistory", "familyHistory", "personalHistory", "reviewOfSystems", "nurseSummary"]:
        if session.fieldProvenance.get(f_key) != "staff-manual":
            session.fieldProvenance[f_key] = "patient-conversation"

    session_store.update_session(session_id, session)

    return {
        "adaptive": adaptive_resp,
        "redFlag": session.redFlag,
        "departmentRouting": session.departmentRouting,
        "session": session
    }

@app.post("/api/session/{session_id}/audio-transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_patient_audio(
    session_id: str,
    file: UploadFile = File(...),
    languageHint: str = Query("en-IN"),
    accentHint: Optional[str] = Query(None)
):
    """
    Transcribes patient voice input with support for Indian regional accents,
    multilingual speech, and clinical colloquial normalizations.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    audio_bytes = await file.read()
    result = await audio_service.transcribe_audio(
        audio_bytes=audio_bytes,
        filename=file.filename or "audio_recording.webm",
        content_type=file.content_type or "audio/webm",
        language_hint=languageHint or session.language,
        accent_hint=accentHint
    )
    return result

@app.get("/api/audio/tts")
async def get_text_to_speech_audio(
    text: str = Query(..., description="Text content to convert to speech"),
    lang: str = Query("bn", description="Language code: bn, hi, ta, te, en")
):
    """
    High-fidelity Text-to-Speech audio streaming endpoint.
    Provides clear Bengali, Hindi, Tamil, Telugu, and English speech 
    even on operating systems without native local language voice packs.
    """
    lang_clean = lang.lower().split("-")[0]
    if lang_clean not in ["bn", "hi", "ta", "te", "en"]:
        lang_clean = "en"

    encoded = urllib.parse.quote(text[:300]) # Cap length for quick responsive streaming
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded}&tl={lang_clean}&client=tw-ob"

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200 and len(resp.content) > 100:
                return StreamingResponse(io.BytesIO(resp.content), media_type="audio/mpeg")
    except Exception as e:
        print(f"[TTS Stream Fallback Error]: {e}")

    raise HTTPException(status_code=502, detail="TTS audio stream temporarily unavailable")

@app.post("/api/session/{session_id}/back")
async def undo_last_answer(session_id: str):
    """
    Rewinds previous answer and regenerates the adaptive next question cleanly.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.conversationTurns:
        session.conversationTurns.pop()
    elif session.chiefComplaint:
        session.chiefComplaint = ""

    # Re-evaluate red flags
    session.redFlag = red_flag_detector.evaluate(session.chiefComplaint, session.conversationTurns)

    # Re-generate next question
    adaptive_resp = await llm_service.get_next_question(
        chief_complaint=session.chiefComplaint or "General consultation",
        conversation_turns=session.conversationTurns,
        ayush_mode=session.ayushMode,
        language=session.language,
        red_flag_active=session.redFlag.triggered
    )

    session_store.update_session(session_id, session)
    return {
        "adaptive": adaptive_resp,
        "session": session
    }

@app.post("/api/session/{session_id}/call-staff")
async def call_triage_staff(session_id: str, req: StaffCallRequest):
    """
    Triggers an immediate dedicated triage nurse call to the kiosk terminal.
    Broadcasts real-time priority assistance event over WebSocket.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.flaggedForStaff = True
    session.staffCallActive = True
    session.staffCallReason = req.reason or "Patient requested triage nurse assistance at kiosk."
    session_store.update_session(session_id, session)

    await staff_service.broadcast_event("staff_call", {
        "sessionId": session.sessionId,
        "patientName": session.patientName,
        "tokenNumber": session.tokenNumber,
        "age": session.age,
        "gender": session.gender,
        "chiefComplaint": session.chiefComplaint or "Initial intake in progress",
        "reason": session.staffCallReason,
        "kioskId": req.kioskId or "KIOSK-01",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    return {
        "status": "staff_called",
        "message": "Sister Priya Sharma (OPD Triage Nurse) has been paged to assist you.",
        "session": session
    }

@app.get("/api/departments")
async def get_hospital_departments():
    """Returns directory of all OPD departments, specialist doctors, and room numbers."""
    return routing_service.DEPARTMENT_DIRECTORY

def _sync_document_to_session_clinical_data(session, investigation):
    """
    Cross-populates medications and diagnoses extracted from prescriptions
    into the session's clinical profile (drug history, past history, nurse summary).
    """
    extracted = investigation.extracted or {}
    meds = extracted.get("medications") or []
    if meds:
        current_med_names = set(session.drugAllergyHistory.currentMedications)
        for m in meds:
            if isinstance(m, dict):
                name = m.get("name", "").strip()
                dosage = m.get("dosage", "").strip()
                freq = m.get("frequency", "").strip()
                dur = m.get("duration", "").strip()
                
                parts = [p for p in [dosage, freq, f"for {dur}" if dur else ""] if p]
                desc = f"{name} ({', '.join(parts)})" if parts else name
                if desc and desc not in current_med_names and name not in current_med_names:
                    session.drugAllergyHistory.currentMedications.append(desc)
                    current_med_names.add(desc)
            elif isinstance(m, str) and m.strip() and m.strip() not in current_med_names:
                session.drugAllergyHistory.currentMedications.append(m.strip())
                current_med_names.add(m.strip())
        
        session.fieldProvenance["drugAllergyHistory"] = "document-extraction"

    diagnoses = extracted.get("diagnoses") or []
    if diagnoses:
        current_past = set(session.pastMedicalHistory)
        for dx in diagnoses:
            if isinstance(dx, str) and dx.strip() and dx.strip() not in current_past:
                if "No prior chronic hospital admissions reported" in session.pastMedicalHistory:
                    session.pastMedicalHistory.remove("No prior chronic hospital admissions reported")
                session.pastMedicalHistory.append(f"Documented Rx Diagnosis: {dx.strip()}")
                current_past.add(dx.strip())

    if session.nurseSummary and meds:
        med_list_str = ", ".join(session.drugAllergyHistory.currentMedications)
        if "no regular daily prescription tablets" in session.nurseSummary:
            session.nurseSummary = session.nurseSummary.replace("no regular daily prescription tablets", f"Prescribed Rx: {med_list_str}")
        elif "Current medications:" in session.nurseSummary:
            session.nurseSummary = session.nurseSummary + f" Attached prescription records indicate active regimen: {med_list_str}."

# --- DOCUMENT SCANNING & OCR ENDPOINTS ---

@app.post("/api/session/{session_id}/document/upload")
async def upload_document(session_id: str, file: UploadFile = File(...)):
    """
    Upload real document image (printed lab report, prescription, handwriting)
    and process through the Vision-LLM extraction pipeline.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    file_bytes = await file.read()
    investigation = await ocr_service.process_document_upload(
        file_bytes=file_bytes,
        filename=file.filename or "uploaded_document.png",
        content_type=file.content_type or "image/png"
    )

    session.priorInvestigations.append(investigation)
    _sync_document_to_session_clinical_data(session, investigation)
    session.fieldProvenance["priorInvestigations"] = "document-extraction"
    session.status = "scanned"
    session_store.update_session(session_id, session)

    return investigation

@app.post("/api/session/{session_id}/document/sample/{sample_id}")
async def load_sample_document(session_id: str, sample_id: str):
    """
    Demo mode: Load bundled sample document (lab report, printed Rx, handwritten Rx)
    and process it through the exact same extraction pipeline.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    investigation = await ocr_service.process_sample_document(sample_id)
    session.priorInvestigations.append(investigation)
    _sync_document_to_session_clinical_data(session, investigation)
    session.fieldProvenance["priorInvestigations"] = "document-extraction"
    session.status = "scanned"
    session_store.update_session(session_id, session)

    return investigation

@app.post("/api/session/{session_id}/document/manual-correct")
async def correct_document_extraction(session_id: str, req: DocumentManualCorrectionRequest):
    """
    Allows patient or staff to manually correct extracted OCR/Vision fields when confidence is low.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    updated = False
    for doc in session.priorInvestigations:
        if doc.id == req.documentId:
            doc.extracted = req.extracted
            doc.confidence = 1.0
            doc.status = "success"
            doc.extractionSource = "manual_correction"
            _sync_document_to_session_clinical_data(session, doc)
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Document ID not found in session")

    session.fieldProvenance["priorInvestigations"] = "manual-correction"
    session_store.update_session(session_id, session)
    return {"status": "corrected", "session": session}

def _rebuild_session_document_data(session: PatientSession):
    """
    Rebuilds medications, past diagnoses, and clinical summary when a document is deleted.
    """
    # Reset baseline medications from interview conversation turns
    base_meds = []
    for t in session.conversationTurns:
        f_lower = t.field.lower()
        if any(k in f_lower for k in ["meds", "medication", "tablet", "prescription"]):
            ans_clean = t.patientAnswer.strip()
            if not any(w in ans_clean.lower() for w in ["no ", "none", "without", "denies", "no regular"]):
                base_meds.append(ans_clean)
    session.drugAllergyHistory.currentMedications = base_meds

    # Reset baseline past medical history
    base_past = []
    for t in session.conversationTurns:
        f_lower = t.field.lower()
        if any(k in f_lower for k in ["past", "comorbid", "chronic", "history"]):
            ans_clean = t.patientAnswer.strip()
            if not any(w in ans_clean.lower() for w in ["no ", "none", "without", "denies", "no prior"]):
                base_past.append(ans_clean)
    session.pastMedicalHistory = base_past if base_past else ["No prior chronic hospital admissions reported"]

    # Re-sync from remaining attached documents
    for doc in session.priorInvestigations:
        _sync_document_to_session_clinical_data(session, doc)

@app.delete("/api/session/{session_id}/document/{doc_id}")
async def delete_document(session_id: str, doc_id: str):
    """
    Deletes an erroneously uploaded or scanned document from the patient's session.
    Rebuilds medication and clinical profile dynamically.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    initial_len = len(session.priorInvestigations)
    session.priorInvestigations = [d for d in session.priorInvestigations if d.id != doc_id]

    if len(session.priorInvestigations) == initial_len:
        raise HTTPException(status_code=404, detail="Document not found in session")

    # Rebuild clinical state and cross-synced medications
    _rebuild_session_document_data(session)

    if len(session.priorInvestigations) == 0:
        session.status = "in_progress"
    
    session_store.update_session(session_id, session)
    return session

@app.post("/api/session/{session_id}/document/{doc_id}/replace")
async def replace_document(session_id: str, doc_id: str, file: UploadFile = File(...)):
    """
    Replaces an existing document with a newly uploaded or scanned photo/PDF.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Remove old document
    session.priorInvestigations = [d for d in session.priorInvestigations if d.id != doc_id]

    # Process new document
    file_bytes = await file.read()
    investigation = await ocr_service.process_document_upload(
        file_bytes=file_bytes,
        filename=file.filename or "replaced_document.png",
        content_type=file.content_type or "image/png"
    )

    session.priorInvestigations.append(investigation)
    _rebuild_session_document_data(session)
    session.fieldProvenance["priorInvestigations"] = "document-extraction"
    session.status = "scanned"
    session_store.update_session(session_id, session)

    return investigation

@app.get("/api/sample-docs/{sample_id}/image")
async def get_sample_document_image(sample_id: str):
    """Serves generated sample document PNG preview images."""
    if sample_id not in ocr_service.SAMPLE_DOCS_METADATA:
        raise HTTPException(status_code=404, detail="Sample image not found")
    meta = ocr_service.SAMPLE_DOCS_METADATA[sample_id]
    filename = meta.get("preview_filename", meta["filename"])
    img_path = os.path.join(SAMPLE_DOCS_DIR, filename)
    if not os.path.exists(img_path):
        ocr_service.ensure_sample_images_exist()
    return FileResponse(img_path, media_type="image/png")

@app.get("/api/documents/{doc_id}/image")
async def get_uploaded_document_image(doc_id: str):
    """Serves real uploaded document image preview or converted PDF thumbnail."""
    # First look for rendered PNG thumbnail
    png_path = os.path.join(UPLOADS_DIR, f"{doc_id}.png")
    if os.path.exists(png_path):
        return FileResponse(png_path, media_type="image/png")

    for filename in os.listdir(UPLOADS_DIR):
        if filename.startswith(doc_id):
            img_path = os.path.join(UPLOADS_DIR, filename)
            if filename.lower().endswith((".jpg", ".jpeg")):
                return FileResponse(img_path, media_type="image/jpeg")
            elif filename.lower().endswith(".png"):
                return FileResponse(img_path, media_type="image/png")
            elif filename.lower().endswith(".pdf"):
                return FileResponse(img_path, media_type="application/pdf")
            else:
                return FileResponse(img_path, media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="Uploaded document image not found")

@app.get("/api/documents/{doc_id}/raw")
async def get_uploaded_document_raw(doc_id: str):
    """Serves raw original uploaded file (including original PDF)."""
    for filename in os.listdir(UPLOADS_DIR):
        if filename.startswith(doc_id):
            file_path = os.path.join(UPLOADS_DIR, filename)
            media_type = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
            return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Uploaded file not found")

# --- DYNAMIC MEDICATION CLARIFICATION ENDPOINTS ---

@app.post("/api/session/{session_id}/document/{doc_id}/medications/clarify/plan", response_model=MedicationClarificationPlan)
async def plan_medication_clarification(session_id: str, doc_id: str, language: Optional[str] = None):
    """
    Dynamically evaluates extracted prescription medications using field confidence analysis.
    Plans the single minimal necessary question for the patient, or determines if all data is reliable
    or if >2 unclear items require staff escalation.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    doc = next((d for d in session.priorInvestigations if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in session")

    meds = doc.medicationItems or []
    if not meds and doc.extracted and "medications" in doc.extracted:
        meds = MedicationClarificationService.normalize_extracted_medications(
            doc.extracted["medications"],
            doc.documentType,
            doc.confidence
        )
        doc.medicationItems = meds

    lang = language or session.language or "en"
    plan = MedicationClarificationService.plan_next_question(
        medications=meds,
        patient_age=session.age,
        language=lang
    )
    
    # Check if document has image URL to attach as crop context
    plan.cropUrl = doc.imageUrl

    # If >2 unclear medications require staff escalation
    if plan.escalateToStaff:
        doc.clarificationStatus = "escalated_to_staff"
        session.flaggedForStaff = True
        session_store.update_session(session_id, session)
        await staff_service.broadcast_event("medication_escalated_to_staff", {
            "sessionId": session.sessionId,
            "patientName": session.patientName,
            "documentId": doc.id,
            "documentTitle": doc.document,
            "unclearCount": plan.unclearMedicationCount,
            "reason": plan.reason
        })
    elif plan.shouldAskPatient:
        doc.clarificationStatus = "in_progress"
        session_store.update_session(session_id, session)
    else:
        doc.clarificationStatus = "completed"
        session_store.update_session(session_id, session)

    return plan

@app.post("/api/session/{session_id}/document/{doc_id}/medications/clarify/answer", response_model=MedicationClarificationAnswerResponse)
async def answer_medication_clarification(session_id: str, doc_id: str, req: MedicationClarificationAnswerRequest):
    """
    Submits patient answer (voice or text), resolves multiple fields simultaneously,
    updates the medication record, and dynamically re-evaluates the next minimal question.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    doc = next((d for d in session.priorInvestigations if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in session")

    meds = doc.medicationItems or []
    target_med = next((m for m in meds if m.id == req.medicationId), None)
    if not target_med:
        raise HTTPException(status_code=404, detail="Target medication not found in document")

    # Multi-field resolution from patient natural language answer
    updated_med, resolved_fields = MedicationClarificationService.interpret_patient_answer(
        answer=req.answer,
        target_med=target_med,
        language=req.language or session.language
    )

    # Update in document medication list
    for i, m in enumerate(meds):
        if m.id == updated_med.id:
            meds[i] = updated_med
            break
    doc.medicationItems = meds

    # Cross-sync verified medications into session clinical profile
    _sync_document_to_session_clinical_data(session, doc)

    # Dynamically plan next step
    lang = req.language or session.language or "en"
    next_plan = MedicationClarificationService.plan_next_question(
        medications=meds,
        patient_age=session.age,
        language=lang
    )
    next_plan.cropUrl = doc.imageUrl

    if not next_plan.shouldAskPatient:
        doc.clarificationStatus = "escalated_to_staff" if next_plan.escalateToStaff else "completed"

    session_store.update_session(session_id, session)

    return MedicationClarificationAnswerResponse(
        updatedMedication=updated_med,
        resolvedFields=resolved_fields,
        nextPlan=next_plan,
        allMedications=meds
    )

@app.post("/api/session/{session_id}/document/{doc_id}/medications/escalate")
async def escalate_medication_to_staff(session_id: str, doc_id: str, reason: Optional[str] = None):
    """
    Manually or deterministically escalates illegible prescription to hospital staff desk.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    doc = next((d for d in session.priorInvestigations if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in session")

    doc.clarificationStatus = "escalated_to_staff"
    session.flaggedForStaff = True
    session_store.update_session(session_id, session)

    await staff_service.broadcast_event("medication_escalated_to_staff", {
        "sessionId": session.sessionId,
        "patientName": session.patientName,
        "documentId": doc.id,
        "documentTitle": doc.document,
        "reason": reason or "Patient requested staff assistance for handwritten prescription."
    })
    return {"status": "escalated_to_staff", "sessionId": session_id, "documentId": doc_id}

# --- SUMMARY & CONFIRMATION ---

@app.get("/api/session/{session_id}/summary")
async def get_summary(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.post("/api/session/{session_id}/confirm")
async def confirm_patient_summary(session_id: str):
    """
    Patient reviews and confirms summary. Pushes record to physician queue.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "confirmed"
    session_store.update_session(session_id, session)

    # Broadcast event to staff / physician dashboard
    await staff_service.broadcast_event("patient_confirmed", {
        "sessionId": session.sessionId,
        "tokenNumber": session.tokenNumber,
        "patientName": session.patientName,
        "chiefComplaint": session.chiefComplaint,
        "redFlag": session.redFlag.triggered,
        "docCount": len(session.priorInvestigations)
    })

    return {
        "status": "confirmed",
        "sessionId": session.sessionId,
        "tokenNumber": session.tokenNumber,
        "visitId": session.visitId,
        "message": "Clinical history successfully linked to ABHA & Hospital Information System (HIS) [SIMULATED]."
    }

# --- CONNECTIVITY TRACKING & ALERTING ---

@app.post("/api/session/{session_id}/connectivity")
async def update_connectivity(session_id: str, req: ConnectivityUpdateRequest):
    """
    Updates kiosk session connectivity status.
    If offline or degraded past threshold, marks flaggedForStaff: True and alerts staff.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.connectivityStatus = req.status
    if req.status == "offline" or req.failCount >= 2:
        session.flaggedForStaff = True
        await staff_service.broadcast_event("connectivity_alert", {
            "sessionId": session.sessionId,
            "patientName": session.patientName,
            "tokenNumber": session.tokenNumber,
            "status": req.status,
            "failCount": req.failCount,
            "message": f"Kiosk connectivity {req.status.upper()} — Staff attention required!"
        })
    elif req.status == "online" and req.failCount == 0 and not session.enteredByStaffId:
        session.flaggedForStaff = False

    session_store.update_session(session_id, session)
    return {"status": session.connectivityStatus, "flaggedForStaff": session.flaggedForStaff, "version": session.version}

# --- STAFF OPERATOR ENDPOINTS ---

@app.post("/api/staff/login")
async def staff_login(req: StaffLoginRequest):
    """Pre-registered staff authentication."""
    auth_result = staff_service.authenticate(req.username, req.password)
    if not auth_result:
        raise HTTPException(status_code=401, detail="Invalid staff username or password")
    token, account = auth_result
    return {
        "token": token,
        "staff": account
    }

@app.get("/api/staff/sessions")
async def get_staff_sessions(staff: StaffAccount = Depends(get_current_staff)):
    """Returns active kiosk sessions sorted with offline/flagged at the top."""
    return session_store.get_staff_monitoring_list()

@app.post("/api/staff/session/{session_id}/takeover")
async def staff_takeover(
    session_id: str, 
    req: StaffTakeoverRequest,
    staff: StaffAccount = Depends(get_current_staff)
):
    """
    Staff manually enters patient clinical data when kiosk disconnects or fails.
    Tags fields with 'staff-manual' provenance and records staff ID.
    Includes conflict detection if kiosk updated the session in between.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Conflict check
    if req.expectedVersion is not None and not req.forceOverride and session.version > req.expectedVersion:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Conflict detected: The kiosk reconnected and updated session data.",
                "currentVersion": session.version,
                "currentSession": session.model_dump()
            }
        )

    session.enteredByStaffId = req.staffId or staff.staffId
    session.flaggedForStaff = False
    
    if req.chiefComplaint:
        session.chiefComplaint = req.chiefComplaint
        session.fieldProvenance["chiefComplaint"] = "staff-manual"

    if req.historyOfPresentIllness:
        session.historyOfPresentIllness = req.historyOfPresentIllness
        session.fieldProvenance["historyOfPresentIllness"] = "staff-manual"

    if req.pastMedicalHistory:
        session.pastMedicalHistory = req.pastMedicalHistory
        session.fieldProvenance["pastMedicalHistory"] = "staff-manual"

    if req.drugAllergyHistory:
        session.drugAllergyHistory = req.drugAllergyHistory
        session.fieldProvenance["drugAllergyHistory"] = "staff-manual"

    if req.familyHistory:
        session.familyHistory = req.familyHistory
        session.fieldProvenance["familyHistory"] = "staff-manual"

    if req.personalHistory:
        session.personalHistory = req.personalHistory
        session.fieldProvenance["personalHistory"] = "staff-manual"

    if req.reviewOfSystems:
        session.reviewOfSystems = req.reviewOfSystems
        session.fieldProvenance["reviewOfSystems"] = "staff-manual"

    if req.manualNotes:
        session.physicianNotes = (session.physicianNotes or "") + f" [Staff Note: {req.manualNotes}]"

    # Evaluate red flags for manual entry
    session.redFlag = red_flag_detector.evaluate(session.chiefComplaint, session.conversationTurns)
    session.status = "confirmed"
    session_store.update_session(session_id, session)

    await staff_service.broadcast_event("staff_takeover_completed", {
        "sessionId": session.sessionId,
        "staffId": session.enteredByStaffId,
        "tokenNumber": session.tokenNumber
    })

    return {"status": "takeover_completed", "session": session}

@app.post("/api/staff/session/{session_id}/handback")
async def staff_handback(
    session_id: str,
    staff: StaffAccount = Depends(get_current_staff)
):
    """
    Hands back the session to the kiosk once reconnected.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.flaggedForStaff = False
    session.connectivityStatus = "online"
    session_store.update_session(session_id, session)

    await staff_service.broadcast_event("session_handed_back", {
        "sessionId": session.sessionId,
        "tokenNumber": session.tokenNumber
    })

    return {"status": "handed_back", "session": session}

@app.post("/api/staff/session/{session_id}/assign-department")
async def assign_patient_department(
    session_id: str,
    req: DepartmentAssignmentRequest,
    staff: StaffAccount = Depends(get_current_staff)
):
    """
    Staff Nurse / Operator manually assigns or overrides the patient's OPD Department and specialist doctor.
    Clears staff triage call and records 'staff-manual' audit provenance.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    dept_meta = routing_service.DEPARTMENT_DIRECTORY.get(req.department, {})
    
    session.departmentRouting = DepartmentRouting(
        department=req.department,
        departmentCode=dept_meta.get("departmentCode", "DEPT_MANUAL"),
        doctorName=req.doctorName or dept_meta.get("doctorName", "Specialist On Duty"),
        doctorTitle=req.doctorTitle or dept_meta.get("doctorTitle", "Consultant Physician"),
        roomNumber=req.roomNumber or dept_meta.get("roomNumber", "OPD Room"),
        floorLocation=req.floorLocation or dept_meta.get("floorLocation", "Main OPD Block"),
        isAmbiguous=False,
        assignedBy="staff-triage",
        routingReason=req.notes or f"Manually triaged and assigned by {staff.fullName} ({staff.role}).",
        confidence=1.0
    )

    session.staffCallActive = False
    session.flaggedForStaff = False
    session.fieldProvenance["departmentRouting"] = "staff-manual"
    if req.notes:
        session.physicianNotes = (session.physicianNotes or "") + f" [Staff Triage Routing Note: {req.notes}]"

    session_store.update_session(session_id, session)

    await staff_service.broadcast_event("department_assigned", {
        "sessionId": session.sessionId,
        "tokenNumber": session.tokenNumber,
        "department": session.departmentRouting.department,
        "doctorName": session.departmentRouting.doctorName,
        "roomNumber": session.departmentRouting.roomNumber,
        "assignedBy": staff.fullName
    })

    return {
        "status": "department_assigned",
        "departmentRouting": session.departmentRouting,
        "session": session
    }

# --- EMERGENCY CASUALTY & RED FLAG TRIAGE ENDPOINTS ---

@app.get("/api/emergency/queue")
async def get_emergency_queue():
    """
    Dedicated stream of active red-flagged patients for Emergency Physicians & Casualty Staff.
    Filters exclusively for triggered emergency red flags.
    """
    return session_store.get_emergency_queue()

@app.post("/api/emergency/session/{session_id}/action")
async def trigger_emergency_action(session_id: str, req: EmergencyActionRequest):
    """
    Executes rapid emergency actions (e.g. Bed assignment, Code Red dispatch, Stat Lab Orders).
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now_str = datetime.now().strftime("%H:%M:%S")
    action_entry = f"[{now_str}] {req.action} by {req.dispatchedBy}"
    if req.assignedBed:
        session.assignedBed = req.assignedBed
        action_entry += f" (Assigned to {req.assignedBed})"
    if req.notes:
        action_entry += f": {req.notes}"

    session.emergencyActionLog.append(action_entry)
    session.fieldProvenance["redFlag"] = "emergency-casualty"
    session_store.update_session(session_id, session)

    await staff_service.broadcast_event("emergency_action_triggered", {
        "sessionId": session.sessionId,
        "tokenNumber": session.tokenNumber,
        "patientName": session.patientName,
        "action": req.action,
        "assignedBed": session.assignedBed
    })

    return {
        "status": "action_executed",
        "action": req.action,
        "assignedBed": session.assignedBed,
        "emergencyActionLog": session.emergencyActionLog,
        "session": session
    }

# --- PHYSICIAN DASHBOARD ENDPOINTS ---

@app.get("/api/physician/queue")
async def get_physician_queue():
    """Returns patients ready for consultation, prioritized by triage severity."""
    queue = session_store.get_physician_queue()
    for s in queue:
        score = TriageService.evaluate_triage_acuity(s)
        if isinstance(s, dict):
            s["triageScore"] = score.model_dump()
        else:
            s.triageScore = score
    # Sort queue: ESI 1 first, then ESI 2, etc.
    def _get_esi(item):
        if isinstance(item, dict):
            return item.get("triageScore", {}).get("esiLevel", 5)
        return item.triageScore.esiLevel if getattr(item, "triageScore", None) else 5

    queue.sort(key=_get_esi)
    return queue

@app.get("/api/physician/session/{session_id}")
async def get_physician_session_detail(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.triageScore = TriageService.evaluate_triage_acuity(session)
    return session

@app.post("/api/physician/session/{session_id}/review")
async def review_clinical_note(session_id: str, req: PhysicianSectionReviewRequest):
    """
    Physician inline reviews each section with Accept / Amend / Reject controls.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.sectionReviews = req.sectionReviews
    session.physicianReviewStatus = req.overallStatus
    if req.physicianNotes:
        session.physicianNotes = req.physicianNotes

    if req.amendedData:
        if "chiefComplaint" in req.amendedData:
            session.chiefComplaint = req.amendedData["chiefComplaint"]
            session.fieldProvenance["chiefComplaint"] = "physician-amended"
        if "historyOfPresentIllness" in req.amendedData:
            session.historyOfPresentIllness = HistoryOfPresentIllness(**req.amendedData["historyOfPresentIllness"])
            session.fieldProvenance["historyOfPresentIllness"] = "physician-amended"
        if "pastMedicalHistory" in req.amendedData:
            session.pastMedicalHistory = req.amendedData["pastMedicalHistory"]
            session.fieldProvenance["pastMedicalHistory"] = "physician-amended"
        if "drugAllergyHistory" in req.amendedData:
            session.drugAllergyHistory = DrugAllergyHistory(**req.amendedData["drugAllergyHistory"])
            session.fieldProvenance["drugAllergyHistory"] = "physician-amended"
        if "reviewOfSystems" in req.amendedData:
            session.reviewOfSystems = req.amendedData["reviewOfSystems"]
            session.fieldProvenance["reviewOfSystems"] = "physician-amended"

    session.status = "in_physician_review"
    session.triageScore = TriageService.evaluate_triage_acuity(session)
    session_store.update_session(session_id, session)

    return {"status": "reviewed", "session": session}

@app.post("/api/physician/session/{session_id}/clinical-decision-support", response_model=CDSSResponse)
@app.post("/api/physician/session/{session_id}/cdss", response_model=CDSSResponse)
async def get_clinical_decision_support(session_id: str):
    """
    Generates evidence-based treatment options, differential diagnoses, critical points to notice,
    and recommended investigations to reduce physician stress and cognitive load during OPD review.
    All suggestions require explicit attending physician discretion and approval before prescribing.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    cdss_result = await llm_service.generate_clinical_decision_support(session.model_dump())
    return cdss_result

@app.post("/api/physician/session/{session_id}/save-record")
async def finalize_physician_record(session_id: str):
    """
    Doctor finalizes and commits the verified clinical record to the EHR.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "completed"
    session.physicianReviewStatus = "Accepted"
    session_store.update_session(session_id, session)

    return {
        "status": "saved",
        "sessionId": session.sessionId,
        "visitId": session.visitId,
        "tokenNumber": session.tokenNumber,
        "message": "Verified clinical note successfully committed to Hospital EHR and linked to ABHA PHR [SIMULATED]."
    }

# --- ADVANCED CLINICAL SAFETY, TRIAGE & INTEROPERABILITY ENDPOINTS ---

@app.get("/api/session/{session_id}/safety-check", response_model=SafetyCheckResponse)
async def get_session_safety_check(session_id: str):
    """
    Evaluates Drug-Drug, Herb-Drug, and Clinical Contraindications for a patient session.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return DDIService.evaluate_session_safety(session)

@app.post("/api/clinical/ddi-check")
async def standalone_ddi_check(payload: Dict[str, Any] = Body(default_factory=dict)):
    """
    Checks pairwise DDI for an arbitrary list of drug names.
    """
    drugs = payload.get("drugs", [])
    alerts = DDIService.check_drug_list(drugs)
    return {"alerts": alerts, "count": len(alerts)}

@app.get("/api/session/{session_id}/triage", response_model=TriageAcuityScore)
async def get_session_triage_score(session_id: str):
    """
    Calculates ESI Triage Level (1-5) and NEWS2 Acuity score.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    score = TriageService.evaluate_triage_acuity(session)
    session.triageScore = score
    session_store.update_session(session_id, session)
    return score

@app.post("/api/session/{session_id}/pain-map")
async def save_pain_assessment(session_id: str, pain: PainAssessment = Body(...)):
    """
    Saves interactive 2D anatomical pain map and VAS score to session.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.painAssessment = pain
    
    # Auto-enrich Chief Complaint / HPI if empty or generic
    pain_desc = f"{pain.painCharacter} pain in {pain.anatomicalRegion} (VAS {pain.painSeverityVAS}/10)"
    if pain.radiationPath:
        pain_desc += f", radiating to {pain.radiationPath}"
    
    if not session.chiefComplaint or session.chiefComplaint == "Initial intake in progress":
        session.chiefComplaint = pain_desc
        session.fieldProvenance["chiefComplaint"] = "body-map-selector"

    session.triageScore = TriageService.evaluate_triage_acuity(session)
    session_store.update_session(session_id, session)

    return {
        "status": "pain_assessment_saved",
        "painAssessment": session.painAssessment,
        "triageScore": session.triageScore,
        "session": session
    }

@app.get("/api/session/{session_id}/fhir")
async def export_fhir_bundle(session_id: str):
    """
    Exports the complete patient intake dossier as an HL7 FHIR R4 Bundle JSON.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return FHIRService.generate_fhir_bundle(session)

@app.post("/api/session/{session_id}/prescription", response_model=PrescriptionOrder)
async def generate_prescription(session_id: str, prescription_data: Dict[str, Any] = Body(default_factory=dict)):
    """
    Creates and finalizes an official OPD digital prescription with verification QR code.
    """
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    rx_id = f"RX-{datetime.now().strftime('%Y%m%d')}-{session.tokenNumber}"
    verification_url = f"https://hospital.medikiosk.in/verify/rx/{rx_id}"

    vitals_summary = "BP: Normal | PR: Normal"
    if session.vitals:
        v = session.vitals
        bp = getattr(v, "bloodPressure", None) or f"{getattr(v, 'bpSystolic', '--') or '--'}/{getattr(v, 'bpDiastolic', '--') or '--'} mmHg"
        pr = getattr(v, "pulseBpm", None) or getattr(v, "pulseRate", "--") or "--"
        temp = getattr(v, "temperatureF", None) or getattr(v, "temperatureC", "--") or "--"
        vitals_summary = f"BP: {bp} | PR: {pr} | Temp: {temp}"

    # Normalize medications
    meds: List[PrescriptionItem] = []
    raw_meds = prescription_data.get("medications", [])
    for m in raw_meds:
        if isinstance(m, dict):
            meds.append(PrescriptionItem(
                name=m.get("name", "Prescribed Tablet"),
                genericName=m.get("genericName"),
                dosage=m.get("dosage", "1 tablet"),
                frequency=m.get("frequency", "Twice daily"),
                timing=m.get("timing", "After food"),
                duration=m.get("duration", "5 days"),
                instructions=m.get("instructions", "As directed")
            ))

    order = PrescriptionOrder(
        prescriptionId=rx_id,
        sessionId=session.sessionId,
        patientName=session.patientName,
        patientAge=session.age,
        patientGender=session.gender,
        patientAbhaId=session.patientId if session.patientId.startswith("ABHA") else f"ABHA-91-{session.patientId[-6:]}",
        hospitalName=prescription_data.get("hospitalName", "Apollo / MediKiosk Smart Care Hospital"),
        doctorName=prescription_data.get("doctorName", (session.departmentRouting.doctorName if session.departmentRouting else "Dr. Subhash Chandra, MD")),
        doctorRegNo=prescription_data.get("doctorRegNo", "MCI-48921"),
        doctorDepartment=prescription_data.get("doctorDepartment", (session.departmentRouting.department if session.departmentRouting else "General Medicine")),
        date=datetime.now().strftime("%Y-%m-%d"),
        vitalsSummary=vitals_summary,
        diagnoses=prescription_data.get("diagnoses", [session.chiefComplaint] if session.chiefComplaint else ["Clinical OPD Review"]),
        icd10Codes=prescription_data.get("icd10Codes", ["R69 (General Symptoms)"]),
        medications=meds,
        investigationsAdvised=prescription_data.get("investigationsAdvised", ["Repeat Fasting Blood Sugar after 1 month"]),
        dietaryLifestyleAdvice=prescription_data.get("dietaryLifestyleAdvice", "Low salt, balanced diabetic diet. Regular 30 min daily walking."),
        followUpDays=int(prescription_data.get("followUpDays", 14)),
        qrVerificationUrl=verification_url
    )

    return order

@app.get("/api/clinical/drugs/suggest")
async def suggest_drugs(q: str = Query("", description="Query prefix or phonetic spelling")):
    """
    Returns fuzzy drug auto-suggestions matching Indian CDSCO brands and generics.
    """
    return DrugMatchingService.search_drugs(q)

# --- REAL-TIME WEBSOCKET FOR STAFF MONITORING ---

@app.websocket("/api/ws/staff")
async def websocket_staff_endpoint(websocket: WebSocket):
    await staff_service.connect_websocket(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        staff_service.disconnect_websocket(websocket)
    except Exception:
        staff_service.disconnect_websocket(websocket)
