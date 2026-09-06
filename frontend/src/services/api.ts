import {
  PatientRegistration, PatientSession, AdaptiveQuestion,
  RedFlag, PriorInvestigation, ConnectivityStatus, StaffAccount,
  AudioTranscriptionResponse, CDSSResponse,
  DoctorAccount, DoctorDutyStatus, DutyState
} from '../types';

const API_BASE = '/api';
const STAFF_TOKEN_KEY = 'medikiosk_staff_token';
const STAFF_ACCOUNT_KEY = 'medikiosk_staff_account';
const DOCTOR_TOKEN_KEY = 'medikiosk_doctor_token';
const DOCTOR_ACCOUNT_KEY = 'medikiosk_doctor_account';

export class ApiService {
  private static connectivityFailures = 0;

  // --- Staff Token Storage Helpers ---
  static setStaffAuth(token: string, staff: StaffAccount) {
    localStorage.setItem(STAFF_TOKEN_KEY, token);
    localStorage.setItem(STAFF_ACCOUNT_KEY, JSON.stringify(staff));
  }

  static getStaffToken(): string | null {
    return localStorage.getItem(STAFF_TOKEN_KEY);
  }

  static getStaffAccount(): StaffAccount | null {
    const raw = localStorage.getItem(STAFF_ACCOUNT_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  static clearStaffAuth() {
    localStorage.removeItem(STAFF_TOKEN_KEY);
    localStorage.removeItem(STAFF_ACCOUNT_KEY);
  }

  // --- Doctor Token Storage Helpers ---
  static setDoctorAuth(token: string, doctor: DoctorAccount) {
    localStorage.setItem(DOCTOR_TOKEN_KEY, token);
    localStorage.setItem(DOCTOR_ACCOUNT_KEY, JSON.stringify(doctor));
  }

  static getDoctorToken(): string | null {
    return localStorage.getItem(DOCTOR_TOKEN_KEY);
  }

  static getDoctorAccount(): DoctorAccount | null {
    const raw = localStorage.getItem(DOCTOR_ACCOUNT_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  static clearDoctorAuth() {
    localStorage.removeItem(DOCTOR_TOKEN_KEY);
    localStorage.removeItem(DOCTOR_ACCOUNT_KEY);
  }

  /** Authorization header for the signed-in doctor, if any. */
  private static doctorHeaders(withJson = false): Record<string, string> {
    const headers: Record<string, string> = {};
    if (withJson) headers['Content-Type'] = 'application/json';
    const token = this.getDoctorToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  }

  private static async handleResponse<T>(res: Response): Promise<T> {
    if (!res.ok) {
      this.connectivityFailures++;
      const errText = await res.text();
      let parsedMsg = `API Error [${res.status}]: ${errText}`;
      try {
        const jsonErr = JSON.parse(errText);
        if (jsonErr.detail) parsedMsg = jsonErr.detail;
      } catch {}
      const error: any = new Error(parsedMsg);
      error.status = res.status;
      error.raw = errText;
      throw error;
    }
    this.connectivityFailures = 0;
    return res.json();
  }

  // --- Session & Intake ---
  static async startSession(registration: PatientRegistration): Promise<PatientSession> {
    const res = await fetch(`${API_BASE}/session/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(registration)
    });
    return this.handleResponse<PatientSession>(res);
  }

  static async getSession(sessionId: string): Promise<PatientSession> {
    const res = await fetch(`${API_BASE}/session/${sessionId}`);
    return this.handleResponse<PatientSession>(res);
  }

  static async submitAnswer(
    sessionId: string,
    answer: string,
    mode: 'voice' | 'tap' | 'staff-manual' = 'tap',
    ayushMode: boolean = false,
    field?: string,
    questionText?: string
  ): Promise<{ adaptive: AdaptiveQuestion; redFlag: RedFlag; session: PatientSession }> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer, mode, ayushMode, field, questionText })
    });
    return this.handleResponse(res);
  }

  static async undoAnswer(sessionId: string): Promise<{ adaptive: AdaptiveQuestion; session: PatientSession }> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/back`, {
      method: 'POST'
    });
    return this.handleResponse(res);
  }

  static async transcribeAudio(
    sessionId: string,
    audioBlob: Blob,
    languageHint: string = 'en-IN',
    accentHint?: string
  ): Promise<AudioTranscriptionResponse> {
    const formData = new FormData();
    formData.append('file', audioBlob, 'voice_recording.webm');
    const query = new URLSearchParams({ languageHint });
    if (accentHint) query.append('accentHint', accentHint);
    
    const res = await fetch(`${API_BASE}/session/${sessionId}/audio-transcribe?${query.toString()}`, {
      method: 'POST',
      body: formData
    });
    return this.handleResponse<AudioTranscriptionResponse>(res);
  }

  // --- Documents & OCR ---
  static async uploadDocument(sessionId: string, file: File): Promise<PriorInvestigation> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/session/${sessionId}/document/upload`, {
      method: 'POST',
      body: formData
    });
    return this.handleResponse<PriorInvestigation>(res);
  }

  static async loadSampleDocument(sessionId: string, sampleId: string): Promise<PriorInvestigation> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/document/sample/${sampleId}`, {
      method: 'POST'
    });
    return this.handleResponse<PriorInvestigation>(res);
  }

  static async correctDocument(sessionId: string, documentId: string, extracted: any): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/document/manual-correct`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ documentId, extracted })
    });
    return this.handleResponse(res);
  }

  static async deleteDocument(sessionId: string, documentId: string): Promise<PatientSession> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/document/${documentId}`, {
      method: 'DELETE'
    });
    return this.handleResponse<PatientSession>(res);
  }

  static async replaceDocument(sessionId: string, documentId: string, file: File): Promise<PriorInvestigation> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/session/${sessionId}/document/${documentId}/replace`, {
      method: 'POST',
      body: formData
    });
    return this.handleResponse<PriorInvestigation>(res);
  }

  // --- Summary & Confirm ---
  static async confirmSession(sessionId: string): Promise<{
    status: string;
    sessionId: string;
    tokenNumber: string;
    visitId: string;
    message: string;
  }> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/confirm`, {
      method: 'POST'
    });
    return this.handleResponse(res);
  }

  // --- Connectivity ---
  static async updateConnectivity(
    sessionId: string,
    status: ConnectivityStatus,
    failCount: number = 0
  ): Promise<{ status: ConnectivityStatus; flaggedForStaff: boolean; version?: number }> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/connectivity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status,
        failCount,
        clientTimestamp: new Date().toISOString()
      })
    });
    return this.handleResponse(res);
  }

  // --- Staff Portal (Authenticated) ---
  static async staffLogin(username: string, password: string): Promise<{ token: string; staff: StaffAccount }> {
    const res = await fetch(`${API_BASE}/staff/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await this.handleResponse<{ token: string; staff: StaffAccount }>(res);
    this.setStaffAuth(data.token, data.staff);
    return data;
  }

  static async getStaffSessions(): Promise<any[]> {
    const token = this.getStaffToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/staff/sessions`, { headers });
    return this.handleResponse<any[]>(res);
  }

  static async staffTakeover(sessionId: string, payload: any): Promise<any> {
    const token = this.getStaffToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/staff/session/${sessionId}/takeover`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  static async staffHandback(sessionId: string): Promise<any> {
    const token = this.getStaffToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/staff/session/${sessionId}/handback`, {
      method: 'POST',
      headers
    });
    return this.handleResponse(res);
  }

  // --- Staff Assistance Call & Department Assignment ---
  static async callStaff(sessionId: string, reason?: string, kioskId?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/call-staff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason, kioskId })
    });
    return this.handleResponse(res);
  }

  static async fetchDepartments(): Promise<Record<string, any>> {
    const res = await fetch(`${API_BASE}/departments`);
    return this.handleResponse<Record<string, any>>(res);
  }

  static async assignDepartment(
    sessionId: string,
    payload: {
      department: string;
      doctorName?: string;
      doctorTitle?: string;
      roomNumber?: string;
      floorLocation?: string;
      notes?: string;
    }
  ): Promise<any> {
    const token = this.getStaffToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/staff/session/${sessionId}/assign-department`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  // --- Emergency Casualty Dashboard ---
  static async getEmergencyQueue(): Promise<PatientSession[]> {
    const res = await fetch(`${API_BASE}/emergency/queue`, { headers: this.doctorHeaders() });
    return this.handleResponse<PatientSession[]>(res);
  }

  static async triggerEmergencyAction(
    sessionId: string,
    action: string,
    assignedBed?: string,
    notes?: string,
    dispatchedBy: string = "Emergency Triage Officer"
  ): Promise<any> {
    const res = await fetch(`${API_BASE}/emergency/session/${sessionId}/action`, {
      method: 'POST',
      headers: this.doctorHeaders(true),
      body: JSON.stringify({ action, assignedBed, notes, dispatchedBy })
    });
    return this.handleResponse(res);
  }

  // --- Doctor Portal (Authenticated) ---
  static async doctorLogin(
    username: string,
    password: string
  ): Promise<{ token: string; doctor: DoctorAccount; duty: DoctorDutyStatus }> {
    const res = await fetch(`${API_BASE}/doctor/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await this.handleResponse<{
      token: string; doctor: DoctorAccount; duty: DoctorDutyStatus;
    }>(res);
    this.setDoctorAuth(data.token, data.doctor);
    return data;
  }

  static async doctorLogout(): Promise<void> {
    try {
      await fetch(`${API_BASE}/doctor/logout`, {
        method: 'POST',
        headers: this.doctorHeaders()
      });
    } catch {
      // Clearing local credentials matters more than the server round-trip.
    }
    this.clearDoctorAuth();
  }

  static async getDoctorProfile(): Promise<{ doctor: DoctorAccount; duty: DoctorDutyStatus }> {
    const res = await fetch(`${API_BASE}/doctor/me`, { headers: this.doctorHeaders() });
    return this.handleResponse(res);
  }

  static async setDoctorDuty(dutyState: DutyState, note = ''): Promise<{ duty: DoctorDutyStatus }> {
    const res = await fetch(`${API_BASE}/doctor/duty`, {
      method: 'POST',
      headers: this.doctorHeaders(true),
      body: JSON.stringify({ dutyState, note })
    });
    return this.handleResponse(res);
  }

  static async getDoctorRoster(): Promise<{ doctor: DoctorAccount; duty: DoctorDutyStatus }[]> {
    const res = await fetch(`${API_BASE}/doctor/roster`, { headers: this.doctorHeaders() });
    return this.handleResponse(res);
  }

  static async getAvailableDoctors(params: {
    department?: string; privilege?: string; includeInterrupted?: boolean;
  } = {}): Promise<DoctorAccount[]> {
    const query = new URLSearchParams();
    if (params.department) query.set('department', params.department);
    if (params.privilege) query.set('privilege', params.privilege);
    if (params.includeInterrupted) query.set('includeInterrupted', 'true');
    const res = await fetch(`${API_BASE}/doctor/available?${query.toString()}`, {
      headers: this.doctorHeaders()
    });
    return this.handleResponse<DoctorAccount[]>(res);
  }

  // --- Physician Dashboard (Authenticated as the signed-in doctor) ---
  static async getPhysicianQueue(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/physician/queue`, { headers: this.doctorHeaders() });
    return this.handleResponse<any[]>(res);
  }

  static async getPhysicianSession(sessionId: string): Promise<PatientSession> {
    const res = await fetch(`${API_BASE}/physician/session/${sessionId}`, {
      headers: this.doctorHeaders()
    });
    return this.handleResponse<PatientSession>(res);
  }

  static async reviewSection(sessionId: string, payload: any): Promise<any> {
    const res = await fetch(`${API_BASE}/physician/session/${sessionId}/review`, {
      method: 'POST',
      headers: this.doctorHeaders(true),
      body: JSON.stringify(payload)
    });
    return this.handleResponse(res);
  }

  static async getClinicalDecisionSupport(sessionId: string): Promise<CDSSResponse> {
    const res = await fetch(`${API_BASE}/physician/session/${sessionId}/clinical-decision-support`, {
      method: 'POST',
      headers: this.doctorHeaders()
    });
    return this.handleResponse<CDSSResponse>(res);
  }

  static async savePhysicianRecord(sessionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/physician/session/${sessionId}/save-record`, {
      method: 'POST',
      headers: this.doctorHeaders()
    });
    return this.handleResponse(res);
  }

  // --- Advanced Clinical & Interoperability APIs ---
  static async getSafetyCheck(sessionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/safety-check`);
    return this.handleResponse(res);
  }

  static async checkStandaloneDDI(drugs: string[]): Promise<any> {
    const res = await fetch(`${API_BASE}/clinical/ddi-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drugs })
    });
    return this.handleResponse(res);
  }

  static async savePainAssessment(sessionId: string, pain: any): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/pain-map`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pain)
    });
    return this.handleResponse(res);
  }

  static async getTriageScore(sessionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/triage`);
    return this.handleResponse(res);
  }

  static async exportFHIRBundle(sessionId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/fhir`);
    return this.handleResponse(res);
  }

  static async generatePrescription(sessionId: string, prescriptionData: any): Promise<any> {
    const res = await fetch(`${API_BASE}/session/${sessionId}/prescription`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(prescriptionData)
    });
    return this.handleResponse(res);
  }

  static async suggestDrugs(query: string): Promise<any[]> {
    const res = await fetch(`${API_BASE}/clinical/drugs/suggest?q=${encodeURIComponent(query)}`);
    return this.handleResponse<any[]>(res);
  }
}
