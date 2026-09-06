from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field

# --- Consent & Registration Models ---
class ConsentDetails(BaseModel):
    recordVoice: bool = True
    storeDocuments: bool = True
    shareHospital: bool = True

class PatientRegistration(BaseModel):
    abhaId: Optional[str] = None
    fullName: str
    age: int
    gender: Literal["Male", "Female", "Other"]
    phone: Optional[str] = ""
    language: str = "en"
    ayushMode: bool = False
    homeopathyMode: bool = False
    medicalSystem: Literal["allopathy", "ayurveda", "homeopathy"] = "allopathy"
    consent: ConsentDetails = Field(default_factory=ConsentDetails)

# --- Conversation & Question Models ---
class QAPair(BaseModel):
    questionId: str
    field: str
    questionText: str
    patientAnswer: str
    mode: Literal["voice", "tap", "staff-manual"] = "voice"
    timestamp: str

class AdaptiveQuestionResponse(BaseModel):
    question: str
    field: str
    options: List[str]
    done: bool = False
    progressPercent: int = 15
    source: Literal["llm", "fallback", "staff-manual"] = "fallback"
    symptomCategory: Optional[str] = None
    systemSummary: Optional[str] = None

class PatientAnswerRequest(BaseModel):
    answer: str
    mode: Literal["voice", "tap", "staff-manual"] = "tap"
    ayushMode: bool = False
    homeopathyMode: bool = False
    medicalSystem: Optional[Literal["allopathy", "ayurveda", "homeopathy"]] = None
    field: Optional[str] = None
    questionText: Optional[str] = None

# --- Audio & Speech Models ---
class AudioTranscriptionResponse(BaseModel):
    transcript: str
    detectedLanguage: str = "en-IN"
    accent: Optional[str] = "Indian English"
    confidence: float = 0.95
    source: Literal["whisper", "gemini_audio", "browser_native", "simulated", "indic_conformer"] = "browser_native"
    normalizedMedicalTerms: List[str] = Field(default_factory=list)

# --- Department & Doctor Routing Models ---
class DepartmentRouting(BaseModel):
    department: str = "General Medicine"
    departmentCode: str = "GEN_MED"
    doctorName: str = "Dr. Subhash Chandra"
    doctorTitle: str = "Senior Consultant Physician"
    roomNumber: str = "Room 101"
    floorLocation: str = "Ground Floor (Main OPD Block)"
    isAmbiguous: bool = False
    assignedBy: Literal["ai-triage", "staff-triage", "emergency-protocol"] = "ai-triage"
    routingReason: str = "General clinical assessment and vitals evaluation."
    confidence: float = 0.95

# --- Red Flag Model ---
class RedFlag(BaseModel):
    triggered: bool = False
    reason: str = ""
    action: str = ""
    urgency: Literal["routine", "urgent", "emergency"] = "routine"
    category: str = "general"

# --- Document & OCR Models ---
class MedicationConfidence(BaseModel):
    medicine: float = 0.90
    strength: float = 0.90
    dosage: float = 0.85
    frequency: float = 0.85
    duration: float = 0.85
    timing: float = 0.80
    overall: float = 0.85

class ExtractedMedicationItem(BaseModel):
    id: str
    name: str
    strength: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    timing: Optional[str] = None
    instructions: Optional[str] = None
    source: Literal["handwritten-prescription", "printed-prescription", "digital-pdf", "medicine-packaging", "patient-voice", "fuzzy-nlem-matched", "staff-verified"] = "handwritten-prescription"
    confidence: MedicationConfidence = Field(default_factory=MedicationConfidence)
    status: Literal["reliable", "needs_clarification", "uncertain", "verified_by_patient", "escalated_to_staff"] = "reliable"
    unreliableFields: List[str] = Field(default_factory=list)
    cropUrl: Optional[str] = None
    # Formulary grounding: whether this reading corresponds to a real marketed
    # product, and the generic the DDI rules need in order to see it at all.
    verificationStatus: Literal["verified", "corrected", "unverified", "not_checked"] = "not_checked"
    matchedBrand: Optional[str] = None
    genericName: Optional[str] = None
    drugClass: Optional[str] = None
    strengthPlausible: Optional[bool] = None
    formularyCandidates: List[str] = Field(default_factory=list)
    verificationNotes: List[str] = Field(default_factory=list)

class MedicationClarificationPlan(BaseModel):
    shouldAskPatient: bool = False
    question: Optional[str] = None
    language: str = "en"
    targetMedicationId: Optional[str] = None
    targetMedicationName: Optional[str] = None
    informationNeeded: List[str] = Field(default_factory=list)
    options: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    stopAfterAnswer: bool = False
    cropUrl: Optional[str] = None
    escalateToStaff: bool = False
    unclearMedicationCount: int = 0
    totalMedicationCount: int = 0
    resolvedCount: int = 0

class MedicationClarificationAnswerRequest(BaseModel):
    docId: str
    medicationId: str
    answer: str
    mode: Literal["voice", "tap", "type", "dont_know"] = "voice"
    language: str = "en"

class MedicationClarificationAnswerResponse(BaseModel):
    updatedMedication: ExtractedMedicationItem
    resolvedFields: List[str] = Field(default_factory=list)
    nextPlan: MedicationClarificationPlan
    allMedications: List[ExtractedMedicationItem] = Field(default_factory=list)

class ConfidenceBreakdown(BaseModel):
    imageQualityScore: float = 0.90
    lexiconGroundingScore: float = 0.90
    fieldCompletenessScore: float = 0.85
    crossCheckAgreementScore: float = 0.90
    reasons: List[str] = Field(default_factory=list)

class CrossCheckDiscrepancy(BaseModel):
    field: str
    label: str
    pass1Value: str
    pass2Value: str
    suggestedValue: str
    confidenceDiff: float = 0.0
    explanation: str = ""

class PriorInvestigation(BaseModel):
    id: str
    document: str
    documentType: Literal["lab_report", "printed_prescription", "handwritten_prescription", "other"]
    extracted: Dict[str, Any] = Field(default_factory=dict)
    medicationItems: Optional[List[ExtractedMedicationItem]] = None
    flag: Optional[str] = None
    confidence: float = 0.95
    confidenceBreakdown: Optional[ConfidenceBreakdown] = None
    crossCheckPassCount: int = 1
    crossCheckStatus: Literal["single_pass", "dual_pass_verified", "discrepancy_flagged", "low_quality_alert"] = "single_pass"
    crossCheckDiscrepancies: List[CrossCheckDiscrepancy] = Field(default_factory=list)
    qualityAssessment: Literal["excellent", "good", "moderate", "poor_handwriting", "blurry_or_damaged"] = "good"
    isSample: bool = False
    timestamp: str
    imageUrl: Optional[str] = None
    status: Literal["success", "needs_review", "failed"] = "success"
    # "extraction_failed" is distinct from a low-confidence read: nothing was
    # extracted at all, and the caller must not treat the payload as content.
    extractionSource: Literal["vision_llm", "local_ocr_fallback", "sample_curated", "manual_correction", "extraction_failed"] = "sample_curated"
    clarificationStatus: Literal["not_needed", "in_progress", "completed", "escalated_to_staff"] = "not_needed"

class DocumentManualCorrectionRequest(BaseModel):
    documentId: str
    extracted: Dict[str, Any]

# --- Clinical Sub-Structures ---
class HomeopathicCaseDetails(BaseModel):
    thermalState: Optional[str] = None # Chilly vs Hot patient
    thirst: Optional[str] = None # Thirsty vs Thirstless, quantity & frequency
    sideAffinity: Optional[str] = None # Right-sided vs Left-sided
    modalitiesAggravation: Optional[str] = None # Factors that worsen symptoms (<)
    modalitiesAmelioration: Optional[str] = None # Factors that relieve symptoms (>)
    mindGenerals: Optional[str] = None # Restlessness, irritability, weepiness, fear
    physicalGenerals: Optional[str] = None # Perspiration, appetite, sleep
    miasmaticTendency: Optional[str] = None # Psora / Sycosis / Syphilis / Tubercular

class AyurvedicCaseDetails(BaseModel):
    doshaLakshana: Optional[str] = None # Vataja / Pittaja / Kaphaja / Dwandwaja
    agniPariksha: Optional[str] = None # Mandagni / Tikshnagni / Vishamagni / Samagni
    kosthaMala: Optional[str] = None # Krura Kostha / Mrudu Kostha / Madhyama Kostha
    amaLakshana: Optional[str] = None # Sama (Toxic/Coated) vs Nirama state
    prakritiDeha: Optional[str] = None # Constitutional Prakriti & Thermal Guna
    aharaViharaHetu: Optional[str] = None # Diet habits, Rasa cravings, Dinacharya
    nidraManasika: Optional[str] = None # Sleep quality, Rajas/Tamas, Vega-dharana
    ayurvedicMedicationsPathya: Optional[str] = None # Current Kwatha/Churna/Bhasma & Pathya compliance

class AllopathicCaseDetails(BaseModel):
    anatomicalSite: Optional[str] = None # Precordium, Epigastrium, Right Lower Quadrant, etc.
    socratesChronology: Optional[str] = None # Acute sudden, subacute, progressive
    painCharacterSeverity: Optional[str] = None # Crushing pressure, stabbing, burning, colicky
    radiationDermatome: Optional[str] = None # Left arm, jaw, scapula, flank, dermatomal
    aggravatingRelieving: Optional[str] = None # Exertion, meals, posture, antacids, rest
    autonomicAssociated: Optional[str] = None # Diaphoresis, dyspnea, nausea, palpitations
    comorbidityRiskStratification: Optional[str] = None # HTN, T2DM, CAD, Dyslipidemia, Smoking
    activePharmacotherapyReconciliation: Optional[str] = None # Reconciled daily prescription drugs
    allergyAdverseAlert: Optional[str] = None # Documented drug allergy contraindications

class HistoryOfPresentIllness(BaseModel):
    onset: str = ""
    site: str = ""
    character: str = ""
    radiation: str = ""
    aggravating: str = ""
    relieving: str = ""
    associatedSymptoms: List[str] = Field(default_factory=list)
    symptomCategory: Optional[str] = None
    clinicalRedFlagsChecked: Optional[List[str]] = Field(default_factory=list)
    ayushDetails: Optional[Dict[str, str]] = None
    ayurvedicDetails: Optional[Dict[str, str]] = None
    homeopathicDetails: Optional[Dict[str, str]] = None
    allopathicDetails: Optional[Dict[str, str]] = None

class DrugAllergyHistory(BaseModel):
    currentMedications: List[str] = Field(default_factory=list)
    allergies: str = "No known drug allergies (NKDA)"

class PersonalHistory(BaseModel):
    diet: str = "Mixed"
    smoking: str = "Non-smoker"
    alcohol: str = "Non-drinker"

# --- Main Patient Session Model ---
class PatientVitals(BaseModel):
    weightKg: Optional[str] = None
    heightCm: Optional[str] = None
    bmi: Optional[str] = None
    bloodPressure: Optional[str] = None
    pulseBpm: Optional[str] = None
    temperatureF: Optional[str] = None
    disclosureStatus: Literal["disclosed", "partially_disclosed", "declined"] = "disclosed"
    nonDisclosureReason: Optional[str] = None
    disclosureAlertAcknowledged: bool = False

class PatientSession(BaseModel):
    sessionId: str
    patientId: str
    visitId: str
    tokenNumber: str
    patientName: str
    age: int
    gender: str
    language: str = "en"
    ayushMode: bool = False
    homeopathyMode: bool = False
    medicalSystem: Literal["allopathy", "ayurveda", "homeopathy"] = "allopathy"
    connectivityStatus: Literal["online", "degraded", "offline"] = "online"
    flaggedForStaff: bool = False
    chiefComplaint: str = ""
    historyOfPresentIllness: HistoryOfPresentIllness = Field(default_factory=HistoryOfPresentIllness)
    pastMedicalHistory: List[str] = Field(default_factory=list)
    drugAllergyHistory: DrugAllergyHistory = Field(default_factory=DrugAllergyHistory)
    familyHistory: List[str] = Field(default_factory=list)
    personalHistory: PersonalHistory = Field(default_factory=PersonalHistory)
    reviewOfSystems: str = ""
    vitals: Optional[PatientVitals] = Field(default_factory=PatientVitals)
    documents: List[PriorInvestigation] = Field(default_factory=list)
    priorInvestigations: List[PriorInvestigation] = Field(default_factory=list)
    conversationTurns: List[QAPair] = Field(default_factory=list)
    fieldProvenance: Dict[str, str] = Field(default_factory=dict)
    enteredByStaffId: Optional[str] = None
    nurseSummary: Optional[str] = ""
    pertinentPositives: List[str] = Field(default_factory=list)
    pertinentNegatives: List[str] = Field(default_factory=list)
    triageAcuity: Literal["Routine", "Semi-urgent", "Priority Emergency"] = "Routine"
    nurseRecommendations: List[str] = Field(default_factory=list)
    departmentRouting: Optional[DepartmentRouting] = None
    assignedBed: Optional[str] = None
    emergencyActionLog: List[str] = Field(default_factory=list)
    physicianReviewStatus: Literal["Pending confirmation", "Pending", "Accepted", "Amended", "Rejected"] = "Pending confirmation"
    physicianNotes: Optional[str] = ""
    sectionReviews: Dict[str, Literal["accepted", "amended", "rejected"]] = Field(default_factory=dict)
    redFlag: RedFlag = Field(default_factory=RedFlag)
    painAssessment: Optional["PainAssessment"] = None
    triageScore: Optional["TriageAcuityScore"] = None
    staffCallActive: bool = False
    staffCallReason: Optional[str] = None
    timestamp: Optional[str] = ""
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    status: Literal["in_progress", "scanned", "confirmed", "in_physician_review", "completed"] = "in_progress"
    version: int = 1

# --- Pain Assessment & Body Map Models ---
class PainAssessment(BaseModel):
    anatomicalRegion: str = "Lower Back"
    side: Optional[str] = "Bilateral"
    painSeverityVAS: int = Field(default=5, ge=1, le=10)
    painCharacter: str = "Dull / Aching"
    radiationPath: Optional[str] = None
    aggravatingFactors: Optional[str] = None
    relievingFactors: Optional[str] = None
    bodyCoordinates: Optional[Dict[str, float]] = None

# --- Drug Interaction (DDI) & Safety Models ---
class DrugInteractionAlert(BaseModel):
    medication1: str
    medication2: str
    severity: Literal["high", "moderate", "minor", "herb_drug"] = "moderate"
    interactionType: Literal["drug_drug", "herb_drug", "contraindication", "dosage_alert"] = "drug_drug"
    mechanism: str
    clinicalRecommendation: str

class SafetyCheckResponse(BaseModel):
    sessionId: str
    hasHighRiskAlerts: bool = False
    alerts: List[DrugInteractionAlert] = Field(default_factory=list)
    allergyWarnings: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    herbDrugInteractions: List[DrugInteractionAlert] = Field(default_factory=list)
    ayurvedicPathyaApathya: Optional[List[str]] = Field(default_factory=list)

# --- ESI Triage & NEWS2 Acuity Models ---
class TriageAcuityScore(BaseModel):
    esiLevel: int = Field(default=3, ge=1, le=5)
    esiCategory: Literal["Resuscitation", "Emergent", "Urgent", "Less Urgent", "Non-Urgent"] = "Urgent"
    news2Score: int = 0
    news2Risk: Literal["Low", "Medium", "High", "Critical"] = "Low"
    clinicalPriority: Literal["Immediate", "High Priority", "Routine", "Fast Track"] = "Routine"
    rationale: str = ""
    suggestedTargetTimeMinutes: int = 30

# --- Prescription & OPD Referral Models ---
class PrescriptionItem(BaseModel):
    name: str
    genericName: Optional[str] = None
    dosage: str = "1 tablet"
    frequency: str = "Twice daily"
    timing: Optional[str] = "After meals"
    duration: str = "5 days"
    instructions: Optional[str] = "Take with water"

class PrescriptionGenerateRequest(BaseModel):
    hospitalName: Optional[str] = "Apollo / MediKiosk Smart Care Hospital"
    doctorName: Optional[str] = None
    doctorRegNo: Optional[str] = "MCI-48921"
    doctorDepartment: Optional[str] = None
    diagnoses: Optional[List[str]] = Field(default_factory=list)
    icd10Codes: Optional[List[str]] = Field(default_factory=list)
    medications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    investigationsAdvised: Optional[List[str]] = Field(default_factory=list)
    dietaryLifestyleAdvice: Optional[str] = None
    followUpDays: Optional[int] = 14

class PrescriptionOrder(BaseModel):
    prescriptionId: str
    sessionId: str
    patientName: str
    patientAge: int
    patientGender: str
    patientAbhaId: Optional[str] = None
    hospitalName: str = "AIIMS / MediKiosk Smart Care Hospital"
    doctorName: str = "Dr. Subhash Chandra, MD"
    doctorRegNo: str = "MCI-48921"
    doctorDepartment: str = "General Medicine & Endocrinology"
    date: str
    vitalsSummary: Optional[str] = None
    diagnoses: List[str] = Field(default_factory=list)
    icd10Codes: List[str] = Field(default_factory=list)
    medications: List[PrescriptionItem] = Field(default_factory=list)
    investigationsAdvised: List[str] = Field(default_factory=list)
    dietaryLifestyleAdvice: Optional[str] = None
    followUpDays: int = 14
    qrVerificationUrl: str = ""

# --- HL7 FHIR R4 Bundle Models ---
class FHIRBundleResponse(BaseModel):
    resourceType: str = "Bundle"
    id: str
    type: str = "document"
    timestamp: str
    entry: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0

# --- Emergency Dashboard Models ---
class EmergencyActionRequest(BaseModel):
    action: str
    assignedBed: Optional[str] = None
    notes: Optional[str] = None
    dispatchedBy: Optional[str] = "Emergency Triage Officer"

# --- Staff & User Models ---
class StaffAccount(BaseModel):
    staffId: str
    username: str
    fullName: str
    role: str
    department: str

class StaffLoginRequest(BaseModel):
    username: str
    password: str

class StaffCallRequest(BaseModel):
    reason: Optional[str] = "Patient requested triage assistance / Ambiguous symptoms"
    kioskId: Optional[str] = "KIOSK-01"

class DepartmentAssignmentRequest(BaseModel):
    department: str
    doctorName: Optional[str] = None
    doctorTitle: Optional[str] = None
    roomNumber: Optional[str] = None
    floorLocation: Optional[str] = None
    notes: Optional[str] = None
    staffId: Optional[str] = None

class StaffTakeoverRequest(BaseModel):
    staffId: str
    chiefComplaint: Optional[str] = None
    historyOfPresentIllness: Optional[HistoryOfPresentIllness] = None
    pastMedicalHistory: Optional[List[str]] = None
    drugAllergyHistory: Optional[DrugAllergyHistory] = None
    familyHistory: Optional[List[str]] = None
    personalHistory: Optional[PersonalHistory] = None
    reviewOfSystems: Optional[str] = None
    manualNotes: Optional[str] = ""
    expectedVersion: Optional[int] = None
    forceOverride: bool = False

class ConnectivityUpdateRequest(BaseModel):
    status: Literal["online", "degraded", "offline"]
    failCount: int = 0
    clientTimestamp: str

# --- Doctor Identity, Privileges & Duty Models ---
# Duty state is deliberately richer than free/busy: emergency dispatch needs to
# know whether a doctor can be interrupted, not merely whether they are idle.
DutyState = Literal["available", "on_rounds", "in_procedure", "off_duty"]

class DoctorAccount(BaseModel):
    doctorId: str
    username: str
    fullName: str
    title: str
    department: str
    departmentCode: str
    registrationNumber: str          # NMC / state medical council registration
    privileges: List[str] = Field(default_factory=list)
    roomNumber: str = ""
    floorLocation: str = ""

class DoctorDutyStatus(BaseModel):
    doctorId: str
    dutyState: DutyState = "off_duty"
    onShift: bool = False
    shiftStart: str = ""             # "HH:MM" local hospital time
    shiftEnd: str = ""
    onCall: bool = False
    interruptible: bool = True       # False while in_procedure
    activeCaseCount: int = 0
    acuityLoad: float = 0.0          # cumulative acuity-weighted load this shift

class DoctorLoginRequest(BaseModel):
    username: str
    password: str

class DoctorLoginResponse(BaseModel):
    token: str
    doctor: DoctorAccount
    duty: DoctorDutyStatus

class DoctorDutyUpdateRequest(BaseModel):
    dutyState: DutyState
    note: Optional[str] = ""

# --- Emergency Dispatch Models ---
# Emergency assignment is not "find a free doctor". It is meeting a clinical
# deadline using a scarce, non-interchangeable, reusable resource, deciding now
# without knowing what arrives next.
class DispatchDeadline(BaseModel):
    label: str                       # e.g. "Door-to-balloon"
    targetMinutes: int
    anchor: Literal["arrival", "onset"] = "arrival"
    elapsedMinutes: int = 0          # already spent before dispatch
    remainingMinutes: int = 0
    breached: bool = False
    basis: str = ""                  # how elapsed time was established

class DispatchCandidate(BaseModel):
    doctorId: str
    fullName: str
    title: str
    department: str
    roomNumber: str
    dutyState: str
    feasible: bool
    exclusionReason: Optional[str] = None
    travelMinutes: int = 0
    projectedMinutesToDoctor: int = 0
    meetsDeadline: bool = False
    activeCaseCount: int = 0
    acuityLoad: float = 0.0
    scarcityPenalty: float = 0.0
    score: float = 0.0               # lower is better
    reasoning: List[str] = Field(default_factory=list)

class DispatchProposal(BaseModel):
    sessionId: str
    condition: str
    requiredPrivilege: str
    preferredDepartment: str
    acuityWeight: float
    deadline: DispatchDeadline
    proposed: Optional[DispatchCandidate] = None
    alternatives: List[DispatchCandidate] = Field(default_factory=list)
    excluded: List[DispatchCandidate] = Field(default_factory=list)
    escalation: List[str] = Field(default_factory=list)
    rationale: str = ""
    generatedAt: str = ""

# Assignment is automatic; accountability comes from the receiving doctor
# accepting, not from a third party approving. A decline reassigns immediately
# and its reason is kept -- it is ground truth the roster does not have.
class DispatchOffer(BaseModel):
    doctorId: str
    doctorName: str
    offeredAt: str
    respondBySeconds: int
    status: Literal["pending", "accepted", "declined", "expired"] = "pending"
    declineReason: Optional[str] = None
    respondedAt: Optional[str] = None
    reasoning: List[str] = Field(default_factory=list)

class DispatchRecord(BaseModel):
    sessionId: str
    condition: str
    requiredPrivilege: str
    acuityWeight: float = 3.0
    deadline: Optional[DispatchDeadline] = None
    status: Literal["pending", "accepted", "escalated"] = "pending"
    currentOffer: Optional[DispatchOffer] = None
    history: List[DispatchOffer] = Field(default_factory=list)
    declinedDoctorIds: List[str] = Field(default_factory=list)
    acceptedByDoctorId: Optional[str] = None
    acceptedByName: Optional[str] = None
    acceptedAt: Optional[str] = None
    escalation: List[str] = Field(default_factory=list)
    rationale: str = ""

class DispatchDeclineRequest(BaseModel):
    reason: str

# --- Physician Review Models ---
class PhysicianSectionReviewRequest(BaseModel):
    sectionReviews: Dict[str, Literal["accepted", "amended", "rejected"]]
    amendedData: Optional[Dict[str, Any]] = None
    physicianNotes: Optional[str] = ""
    overallStatus: Literal["Accepted", "Amended", "Rejected"] = "Accepted"

# --- Clinical Decision Support System (CDSS) Models ---
class DifferentialDiagnosis(BaseModel):
    condition: str
    icd10: Optional[str] = None
    probability: Literal["High", "Moderate", "Consider / Low"] = "Moderate"
    rationale: str

class SuggestedDrug(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    rationale: str
    potency: Optional[str] = None
    repetition: Optional[str] = None
    contraindicationWarning: Optional[str] = None

class CDSSResponse(BaseModel):
    differentialDiagnoses: List[DifferentialDiagnosis] = Field(default_factory=list)
    suggestedTreatments: List[SuggestedDrug] = Field(default_factory=list)
    keyPointsToNotice: List[str] = Field(default_factory=list)
    recommendedInvestigations: List[str] = Field(default_factory=list)
    clinicalRationale: str = ""
    source: Literal["gemini", "groq", "openrouter", "guideline_rules"] = "guideline_rules"
    disclaimer: str = "AI Clinical Decision Support for doctor guidance only. Prescriptions and diagnoses are subject to attending physician's clinical discretion."

# Rebuild models with forward references
PatientSession.model_rebuild()


