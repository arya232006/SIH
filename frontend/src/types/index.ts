export type ConnectivityStatus = 'online' | 'degraded' | 'offline';

export type LanguageCode = 'en' | 'hi' | 'bn' | 'ta' | 'te';

export interface ConsentDetails {
  recordVoice: boolean;
  storeDocuments: boolean;
  shareHospital: boolean;
}

export interface PatientRegistration {
  abhaId?: string;
  fullName: string;
  age: number;
  gender: 'Male' | 'Female' | 'Other';
  phone?: string;
  language: LanguageCode;
  ayushMode: boolean;
  homeopathyMode?: boolean;
  medicalSystem?: 'allopathy' | 'ayurveda' | 'homeopathy';
  consent: ConsentDetails;
}

export interface QAPair {
  questionId: string;
  field: string;
  questionText: string;
  patientAnswer: string;
  mode: 'voice' | 'tap' | 'staff-manual';
  timestamp: string;
}

export interface AdaptiveQuestion {
  question: string;
  field: string;
  options: string[];
  done: boolean;
  progressPercent: number;
  source?: 'llm' | 'fallback' | 'staff-manual';
  symptomCategory?: string;
  systemSummary?: string;
}

export interface AudioTranscriptionResponse {
  transcript: string;
  /** English rendering used by the clinical rules when speech was not English. */
  clinicalText?: string;
  error?: string;
  detectedLanguage: string;
  accent?: string;
  confidence: number;
  source: 'openai' | 'openai_whisper' | 'whisper' | 'gemini_audio' | 'browser_native' | 'simulated' | 'indic_conformer' | 'transcription_failed';
  normalizedMedicalTerms: string[];
}

export interface DepartmentRouting {
  department: string;
  departmentCode?: string;
  doctorName: string;
  doctorTitle?: string;
  roomNumber: string;
  floorLocation?: string;
  isAmbiguous: boolean;
  assignedBy: 'ai-triage' | 'staff-triage' | 'emergency-protocol';
  routingReason: string;
  confidence?: number;
}

export interface RedFlag {
  triggered: boolean;
  reason: string;
  action: string;
  urgency?: 'routine' | 'urgent' | 'emergency';
}

export interface InvestigationItem {
  test: string;
  value: string;
  unit: string;
  ref_range?: string;
  flag?: 'NORMAL' | 'HIGH' | 'LOW';
}

export interface MedicationItem {
  name: string;
  dosage: string;
  frequency: string;
  duration?: string;
  timing?: string;
  instructions?: string;
}

export interface MedicationConfidence {
  medicine: number;
  strength: number;
  dosage: number;
  frequency: number;
  duration: number;
  timing: number;
  overall: number;
}

export interface ExtractedMedicationItem {
  id: string;
  name: string;
  strength?: string;
  dosage?: string;
  frequency?: string;
  duration?: string;
  timing?: string;
  instructions?: string;
  source?: 'handwritten-prescription' | 'printed-prescription' | 'digital-pdf' | 'medicine-packaging' | 'patient-voice' | 'fuzzy-nlem-matched' | 'staff-verified';
  confidence: MedicationConfidence;
  status: 'reliable' | 'needs_clarification' | 'uncertain' | 'verified_by_patient' | 'escalated_to_staff';
  unreliableFields: string[];
  cropUrl?: string;
}

export interface MedicationClarificationPlan {
  shouldAskPatient: boolean;
  question?: string | null;
  language: string;
  targetMedicationId?: string;
  targetMedicationName?: string;
  informationNeeded: string[];
  options: string[];
  reason?: string;
  stopAfterAnswer: boolean;
  cropUrl?: string;
  escalateToStaff: boolean;
  unclearMedicationCount: number;
  totalMedicationCount: number;
  resolvedCount: number;
}

export interface MedicationClarificationAnswerRequest {
  docId: string;
  medicationId: string;
  answer: string;
  mode: 'voice' | 'tap' | 'type' | 'dont_know';
  language?: string;
}

export interface MedicationClarificationAnswerResponse {
  updatedMedication: ExtractedMedicationItem;
  resolvedFields: string[];
  nextPlan: MedicationClarificationPlan;
  allMedications: ExtractedMedicationItem[];
}

export interface ExtractedDocumentData {
  laboratory?: string;
  doctor_name?: string;
  clinic?: string;
  test_date?: string;
  rx_date?: string;
  diagnoses?: string[];
  medications?: MedicationItem[];
  investigations?: InvestigationItem[];
  clinical_impression?: string;
  advice?: string;
  [key: string]: any;
}

export interface ConfidenceBreakdown {
  imageQualityScore: number;
  lexiconGroundingScore: number;
  fieldCompletenessScore: number;
  crossCheckAgreementScore: number;
  reasons: string[];
}

export interface CrossCheckDiscrepancy {
  field: string;
  label: string;
  pass1Value: string;
  pass2Value: string;
  suggestedValue: string;
  confidenceDiff: number;
  explanation: string;
}

export interface PriorInvestigation {
  id: string;
  document: string;
  documentType: 'lab_report' | 'printed_prescription' | 'handwritten_prescription' | 'other';
  extracted: ExtractedDocumentData;
  medicationItems?: ExtractedMedicationItem[];
  flag?: string | null;
  confidence: number;
  confidenceBreakdown?: ConfidenceBreakdown;
  crossCheckPassCount?: number;
  crossCheckStatus?: 'single_pass' | 'dual_pass_verified' | 'discrepancy_flagged' | 'low_quality_alert';
  crossCheckDiscrepancies?: CrossCheckDiscrepancy[];
  qualityAssessment?: 'excellent' | 'good' | 'moderate' | 'poor_handwriting' | 'blurry_or_damaged';
  isSample: boolean;
  timestamp: string;
  imageUrl?: string;
  status: 'success' | 'needs_review' | 'failed';
  extractionSource?: 'vision_llm' | 'local_ocr_fallback' | 'sample_curated' | 'manual_correction' | 'extraction_failed';
  clarificationStatus?: 'not_needed' | 'in_progress' | 'completed' | 'escalated_to_staff';
}

export interface AyurvedicCaseDetails {
  doshaLakshana?: string;
  agniPariksha?: string;
  kosthaMala?: string;
  amaLakshana?: string;
  prakritiDeha?: string;
  aharaViharaHetu?: string;
  nidraManasika?: string;
  ayurvedicMedicationsPathya?: string;
}

export interface AllopathicCaseDetails {
  anatomicalSite?: string;
  socratesChronology?: string;
  painCharacterSeverity?: string;
  radiationDermatome?: string;
  aggravatingRelieving?: string;
  autonomicAssociated?: string;
  comorbidityRiskStratification?: string;
  activePharmacotherapyReconciliation?: string;
  allergyAdverseAlert?: string;
}

export interface HistoryOfPresentIllness {
  onset: string;
  site: string;
  character: string;
  radiation: string;
  aggravating: string;
  relieving: string;
  associatedSymptoms: string[];
  symptomCategory?: string;
  clinicalRedFlagsChecked?: string[];
  ayushDetails?: Record<string, string>;
  ayurvedicDetails?: Record<string, string>;
  homeopathicDetails?: Record<string, string>;
  allopathicDetails?: Record<string, string>;
}

export interface DrugAllergyHistory {
  currentMedications: string[];
  allergies: string;
}

export interface PersonalHistory {
  diet: string;
  smoking: string;
  alcohol: string;
}

export type ProvenanceType = 
  | 'patient-conversation' 
  | 'attendant-conversation' 
  | 'staff-manual' 
  | 'document-extraction' 
  | 'document-extraction-fallback' 
  | 'manual-correction' 
  | 'physician-amended';

export interface PatientVitals {
  weightKg?: string | null;
  heightCm?: string | null;
  bmi?: string | null;
  bloodPressure?: string | null;
  pulseBpm?: string | null;
  temperatureF?: string | null;
  disclosureStatus?: 'disclosed' | 'partially_disclosed' | 'declined';
  nonDisclosureReason?: string | null;
  disclosureAlertAcknowledged?: boolean;
}

export interface PatientSession {
  sessionId: string;
  patientId: string;
  visitId: string;
  tokenNumber: string;
  patientName: string;
  age: number;
  gender: string;
  language: LanguageCode;
  ayushMode: boolean;
  homeopathyMode?: boolean;
  medicalSystem?: 'allopathy' | 'ayurveda' | 'homeopathy';
  connectivityStatus: ConnectivityStatus;
  flaggedForStaff: boolean;
  chiefComplaint: string;
  historyOfPresentIllness: HistoryOfPresentIllness;
  pastMedicalHistory: string[];
  drugAllergyHistory: DrugAllergyHistory;
  familyHistory: string[];
  personalHistory: PersonalHistory;
  reviewOfSystems: string;
  vitals?: PatientVitals;
  nurseSummary?: string;
  pertinentPositives?: string[];
  pertinentNegatives?: string[];
  triageAcuity?: 'Routine' | 'Semi-urgent' | 'Priority Emergency';
  nurseRecommendations?: string[];
  departmentRouting?: DepartmentRouting;
  staffCallActive?: boolean;
  staffCallReason?: string | null;
  priorInvestigations: PriorInvestigation[];
  redFlag: RedFlag;
  assignedBed?: string | null;
  emergencyActionLog?: string[];
  fieldProvenance: Record<string, ProvenanceType>;
  enteredByStaffId?: string | null;
  physicianReviewStatus: 'Pending confirmation' | 'Accepted' | 'Amended' | 'Rejected';
  physicianNotes?: string;
  sectionReviews: Record<string, 'accepted' | 'amended' | 'rejected'>;
  conversationTurns: QAPair[];
  painAssessment?: PainAssessment;
  triageScore?: TriageAcuityScore;
  createdAt: string;
  updatedAt: string;
  status: 'in_progress' | 'scanned' | 'confirmed' | 'in_physician_review' | 'completed';
  version: number;
}

export interface PainAssessment {
  anatomicalRegion: string;
  side?: string;
  painSeverityVAS: number;
  painCharacter: string;
  radiationPath?: string;
  aggravatingFactors?: string;
  relievingFactors?: string;
  bodyCoordinates?: Record<string, number>;
}

export interface DrugInteractionAlert {
  medication1: string;
  medication2: string;
  severity: 'high' | 'moderate' | 'minor' | 'herb_drug';
  interactionType: 'drug_drug' | 'herb_drug' | 'contraindication' | 'dosage_alert';
  mechanism: string;
  clinicalRecommendation: string;
}

export interface SafetyCheckResponse {
  sessionId: string;
  hasHighRiskAlerts: boolean;
  alerts: DrugInteractionAlert[];
  allergyWarnings: string[];
  contraindications: string[];
  herbDrugInteractions: DrugInteractionAlert[];
  ayurvedicPathyaApathya?: string[];
}

export interface TriageAcuityScore {
  esiLevel: number;
  esiCategory: 'Resuscitation' | 'Emergent' | 'Urgent' | 'Less Urgent' | 'Non-Urgent';
  news2Score: number;
  news2Risk: 'Low' | 'Medium' | 'High' | 'Critical';
  clinicalPriority: 'Immediate' | 'High Priority' | 'Routine' | 'Fast Track';
  rationale: string;
  suggestedTargetTimeMinutes: number;
}

export interface PrescriptionItem {
  name: string;
  genericName?: string;
  dosage: string;
  frequency: string;
  timing?: string;
  duration: string;
  instructions?: string;
}

export interface PrescriptionOrder {
  prescriptionId: string;
  sessionId: string;
  patientName: string;
  patientAge: number;
  patientGender: string;
  patientAbhaId?: string;
  hospitalName: string;
  doctorName: string;
  doctorRegNo: string;
  doctorDepartment: string;
  date: string;
  vitalsSummary?: string;
  diagnoses: string[];
  icd10Codes: string[];
  medications: PrescriptionItem[];
  investigationsAdvised: string[];
  dietaryLifestyleAdvice?: string;
  followUpDays: number;
  qrVerificationUrl: string;
}

export interface StaffAccount {
  staffId: string;
  username: string;
  fullName: string;
  role: string;
  department: string;
}

// Duty state is richer than free/busy: emergency dispatch needs to know whether
// a doctor can be interrupted, not merely whether they are idle.
export type DutyState = 'available' | 'on_rounds' | 'in_procedure' | 'off_duty';

export interface DoctorAccount {
  doctorId: string;
  username: string;
  fullName: string;
  title: string;
  department: string;
  departmentCode: string;
  registrationNumber: string;
  privileges: string[];
  roomNumber: string;
  floorLocation: string;
}

export interface DoctorDutyStatus {
  doctorId: string;
  dutyState: DutyState;
  onShift: boolean;
  shiftStart: string;
  shiftEnd: string;
  onCall: boolean;
  interruptible: boolean;
  activeCaseCount: number;
  acuityLoad: number;
}

// --- Emergency dispatch ---
// A case is offered to one doctor at a time with a deadline to respond. It is
// not theirs until they accept; a decline or a silence rolls it onward, and the
// ladder of who was asked and why is kept on the record.
export interface DispatchDeadline {
  label: string;
  targetMinutes: number;
  anchor: 'arrival' | 'onset';
  elapsedMinutes: number;
  remainingMinutes: number;
  breached: boolean;
  basis: string;
}

export interface DispatchOffer {
  doctorId: string;
  doctorName: string;
  offeredAt: string;
  respondBySeconds: number;
  status: 'pending' | 'accepted' | 'declined' | 'expired';
  declineReason?: string | null;
  respondedAt?: string | null;
  reasoning: string[];
}

export interface DispatchRecord {
  sessionId: string;
  condition: string;
  requiredPrivilege: string;
  acuityWeight: number;
  deadline?: DispatchDeadline | null;
  status: 'pending' | 'accepted' | 'escalated';
  currentOffer?: DispatchOffer | null;
  history: DispatchOffer[];
  declinedDoctorIds: string[];
  acceptedByDoctorId?: string | null;
  acceptedByName?: string | null;
  acceptedAt?: string | null;
  escalation: string[];
  rationale: string;
}

export interface DispatchInboxItem {
  record: DispatchRecord;
  patient: {
    sessionId: string;
    patientName: string;
    tokenNumber: string;
    age?: number | null;
    gender?: string | null;
    chiefComplaint: string;
    redFlagReason: string;
  };
}

export interface DifferentialDiagnosis {
  condition: string;
  icd10?: string;
  probability: 'High' | 'Moderate' | 'Consider / Low';
  rationale: string;
}

export interface SuggestedDrug {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  rationale: string;
  potency?: string | null;
  repetition?: string | null;
  contraindicationWarning?: string | null;
}

export interface CDSSResponse {
  differentialDiagnoses: DifferentialDiagnosis[];
  suggestedTreatments: SuggestedDrug[];
  keyPointsToNotice: string[];
  recommendedInvestigations: string[];
  clinicalRationale: string;
  source: 'openai' | 'gemini' | 'groq' | 'openrouter' | 'guideline_rules';
  disclaimer: string;
}

