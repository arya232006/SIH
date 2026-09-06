import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom';
import { 
  LanguageCode, ConnectivityStatus, StaffAccount 
} from './types';
import { ApiService } from './services/api';
import { KioskContainer } from './pages/Kiosk/KioskContainer';
import { PhysicianQueue } from './pages/Physician/PhysicianQueue';
import { ClinicalReview } from './pages/Physician/ClinicalReview';
import { RequireDoctor } from './pages/Physician/RequireDoctor';
import { EmergencyDashboard } from './pages/Emergency/EmergencyDashboard';
import { StaffLogin } from './pages/Staff/StaffLogin';
import { StaffMonitor } from './pages/Staff/StaffMonitor';
import { StaffTakeover } from './pages/Staff/StaffTakeover';
import { 
  Stethoscope, UserCheck, ShieldCheck, Heart, 
  Wifi, WifiOff, Globe, Sparkles, ArrowRight, Activity, 
  FileText, CheckCircle2, ChevronDown, Siren, AlertTriangle 
} from 'lucide-react';

// Landing Page Component
const LandingPage: React.FC = () => {
  return (
    <div className="max-w-6xl mx-auto px-4 py-12 sm:py-16 space-y-12">
      
      {/* Hero Section */}
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <div className="inline-flex items-center space-x-2 bg-teal-50 border border-teal-200 text-teal-800 px-3.5 py-1.5 rounded-full text-xs font-bold shadow-sm">
          <Sparkles className="w-4 h-4 text-teal-600" />
          <span>AI Clinical History Platform for Indian Hospital OPDs</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight">
          Smarter Pre-Consultation History.<br />
          <span className="text-teal-700">Faster Care. Zero Paper Burden.</span>
        </h1>
        <p className="text-base text-slate-600 max-w-2xl mx-auto leading-relaxed">
          MediKiosk captures conversational patient symptoms via multilingual voice & touch, extracts past prescriptions with Vision-OCR, detects critical triage red flags, and delivers structured clinical summaries directly to the physician's OPD dashboard.
        </p>

        {/* Persona Action Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-8 text-left">
          
          {/* Patient Kiosk Flow */}
          <Link
            to="/kiosk"
            className="p-5 rounded-2xl bg-white border-2 border-teal-600 shadow-xl hover:shadow-2xl hover:-translate-y-1 transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="w-10 h-10 rounded-xl bg-teal-600 text-white flex items-center justify-center shadow-md">
                <Heart className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900 group-hover:text-teal-700 transition-colors">
                Patient Intake Kiosk
              </h3>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Simulate patient intake with ABHA ID, conversational voice/touch questioning, AYUSH toggle, and document scan.
              </p>
            </div>
            <div className="mt-4 flex items-center text-xs font-bold text-teal-700">
              <span>Start Intake</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Physician Dashboard Flow */}
          <Link
            to="/physician"
            className="p-5 rounded-2xl bg-white border-2 border-blue-600 shadow-xl hover:shadow-2xl hover:-translate-y-1 transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-md">
                <Stethoscope className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                Physician OPD Dashboard
              </h3>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Triage queue with SOCRATES HPI notes, AI Clinical Decision Support (CDSS), and 1-click EHR commit.
              </p>
            </div>
            <div className="mt-4 flex items-center text-xs font-bold text-blue-700">
              <span>Open Doctor Queue</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Emergency & Casualty Red-Flag Flow */}
          <Link
            to="/emergency"
            className="p-5 rounded-2xl bg-slate-900 border-2 border-rose-600 shadow-xl hover:shadow-2xl hover:-translate-y-1 transition-all group flex flex-col justify-between text-white"
          >
            <div className="space-y-2.5">
              <div className="w-10 h-10 rounded-xl bg-rose-600 text-white flex items-center justify-center shadow-md animate-pulse">
                <Siren className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white group-hover:text-rose-400 transition-colors">
                Casualty Emergency Desk
              </h3>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                Dedicated real-time monitoring for critical red flag arrivals, trauma bay bed allocation, and stat resuscitation orders.
              </p>
            </div>
            <div className="mt-4 flex items-center text-xs font-bold text-rose-400">
              <span>Open Emergency Desk</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Staff Floor Operator Flow */}
          <Link
            to="/staff"
            className="p-5 rounded-2xl bg-white border-2 border-amber-500 shadow-xl hover:shadow-2xl hover:-translate-y-1 transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center shadow-md">
                <UserCheck className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-slate-900 group-hover:text-amber-700 transition-colors">
                Staff Intervention Portal
              </h3>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                Monitor live floor kiosks, receive offline alerts, manage triage nurse dispatch, and conduct manual takeover.
              </p>
            </div>
            <div className="mt-4 flex items-center text-xs font-bold text-amber-700">
              <span>Open Staff Portal</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

        </div>
      </div>

      {/* Feature Highlights Grid */}
      <div className="bg-white rounded-3xl p-8 shadow-md border border-slate-200 grid grid-cols-1 md:grid-cols-4 gap-6 text-xs">
        <div className="space-y-2">
          <div className="flex items-center space-x-2 font-bold text-slate-900 text-sm">
            <Globe className="w-4 h-4 text-teal-600" />
            <span>5 Indian Languages</span>
          </div>
          <p className="text-slate-500 leading-relaxed">
            English, Hindi, Bengali, Tamil, Telugu with touch-first options and voice capture simulation.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center space-x-2 font-bold text-slate-900 text-sm">
            <ShieldCheck className="w-4 h-4 text-rose-600" />
            <span>Deterministic Red Flags</span>
          </div>
          <p className="text-slate-500 leading-relaxed">
            Rule-based triage catches Acute Coronary Syndrome, Stroke, and severe hemorrhage independently of LLMs.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center space-x-2 font-bold text-slate-900 text-sm">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>Vision OCR Pipeline</span>
          </div>
          <p className="text-slate-500 leading-relaxed">
            Extracts lab biomarkers (with high/low flags) and prescriptions with fallback and patient correction.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center space-x-2 font-bold text-slate-900 text-sm">
            <Activity className="w-4 h-4 text-amber-600" />
            <span>Staff Failover & Sync</span>
          </div>
          <p className="text-slate-500 leading-relaxed">
            Resilient offline failover allowing nurses to enter manual intake with explicit provenance audit tags.
          </p>
        </div>
      </div>

    </div>
  );
};

// Staff Root Component Handling Auth
const StaffRoot: React.FC = () => {
  const [authenticatedStaff, setAuthenticatedStaff] = useState<StaffAccount | null>(() => {
    return ApiService.getStaffAccount();
  });

  const handleLogout = () => {
    ApiService.clearStaffAuth();
    setAuthenticatedStaff(null);
  };

  if (!authenticatedStaff) {
    return <StaffLogin onLoginSuccess={setAuthenticatedStaff} />;
  }

  return <StaffMonitor staff={authenticatedStaff} onLogout={handleLogout} />;
};

// Staff Takeover Route Wrapper
const StaffTakeoverWrapper: React.FC = () => {
  const staff = ApiService.getStaffAccount() || {
    staffId: 'STAFF-OPD-101',
    fullName: 'Sister Priya Sharma',
    role: 'OPD Triage Staff Nurse',
    department: 'OPD Triage',
    username: 'nurse_priya'
  };

  return <StaffTakeover staff={staff} />;
};

export const App: React.FC = () => {
  const [currentLang, setCurrentLang] = useState<LanguageCode>('en');
  const [connectivity, setConnectivity] = useState<ConnectivityStatus>('online');
  const [emergencyCount, setEmergencyCount] = useState<number>(0);

  // Poll emergency red flag count for live navbar badge. The queue carries
  // patient names and complaints, so it is doctor-authenticated -- only poll
  // once someone is signed in, and drop the badge when they sign out.
  useEffect(() => {
    const checkEmergencyQueue = async () => {
      if (!ApiService.getDoctorToken()) {
        setEmergencyCount(0);
        return;
      }
      try {
        const queue = await ApiService.getEmergencyQueue();
        setEmergencyCount(queue.length);
      } catch (err) {
        // quiet fallback
      }
    };
    checkEmergencyQueue();
    const timer = setInterval(checkEmergencyQueue, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
        
        {/* Top Hospital Navigation Bar */}
        <header className="bg-slate-900 text-white sticky top-0 z-40 shadow-md">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center shadow group-hover:scale-105 transition-transform">
                <Heart className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="font-extrabold text-base sm:text-lg tracking-tight text-white flex items-center">
                  Medi<span className="text-teal-400">Kiosk</span>
                </span>
                <span className="text-[10px] text-slate-400 block -mt-1 font-mono">OPD AI Intake Platform</span>
              </div>
            </Link>

            {/* Persona Quick Links */}
            <nav className="hidden md:flex items-center space-x-1">
              <Link
                to="/kiosk"
                className="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-200 hover:text-white hover:bg-slate-800 transition-colors flex items-center space-x-1"
              >
                <Heart className="w-3.5 h-3.5 text-teal-400" />
                <span>Patient Kiosk</span>
              </Link>
              <Link
                to="/physician"
                className="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-200 hover:text-white hover:bg-slate-800 transition-colors flex items-center space-x-1"
              >
                <Stethoscope className="w-3.5 h-3.5 text-blue-400" />
                <span>Doctor Queue</span>
              </Link>

              {/* Dedicated Emergency Casualty Desk Link */}
              <Link
                to="/emergency"
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 border shadow-sm ${
                  emergencyCount > 0
                    ? 'bg-rose-950/80 border-rose-500 text-rose-300 hover:bg-rose-900 ring-2 ring-rose-500/30 animate-pulse'
                    : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800'
                }`}
              >
                <Siren className={`w-3.5 h-3.5 ${emergencyCount > 0 ? 'text-rose-400 animate-spin' : 'text-slate-400'}`} />
                <span>Emergency Desk</span>
                {emergencyCount > 0 && (
                  <span className="ml-1 px-1.5 py-0.2 bg-rose-600 text-white rounded-full text-[10px] font-black">
                    {emergencyCount}
                  </span>
                )}
              </Link>

              <Link
                to="/staff"
                className="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-200 hover:text-white hover:bg-slate-800 transition-colors flex items-center space-x-1"
              >
                <UserCheck className="w-3.5 h-3.5 text-amber-400" />
                <span>Staff Portal</span>
              </Link>
            </nav>

            {/* Global Controls: Language & Connectivity Simulator */}
            <div className="flex items-center space-x-3">
              
              {/* Language Selector */}
              <div className="relative flex items-center">
                <Globe className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
                <select
                  value={currentLang}
                  onChange={(e) => setCurrentLang(e.target.value as LanguageCode)}
                  aria-label="Select Interface Language"
                  className="bg-slate-800 text-xs font-bold text-slate-200 pl-8 pr-6 py-1.5 rounded-lg border border-slate-700 hover:border-slate-600 focus:outline-none cursor-pointer appearance-none"
                >
                  <option value="en">English (EN)</option>
                  <option value="hi">हिंदी (Hindi)</option>
                  <option value="bn">বাংলা (Bengali)</option>
                  <option value="ta">தமிழ் (Tamil)</option>
                  <option value="te">తెలుగు (Telugu)</option>
                </select>
                <ChevronDown className="w-3 h-3 text-slate-400 absolute right-2 pointer-events-none" />
              </div>

              {/* Network Connectivity Simulator Toggle */}
              <button
                type="button"
                onClick={() => {
                  const next: Record<ConnectivityStatus, ConnectivityStatus> = {
                    online: 'degraded',
                    degraded: 'offline',
                    offline: 'online'
                  };
                  setConnectivity(next[connectivity]);
                }}
                title="Click to simulate network degradation / offline drop"
                className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors ${
                  connectivity === 'online'
                    ? 'bg-teal-950/60 border-teal-600/50 text-teal-300'
                    : connectivity === 'degraded'
                    ? 'bg-amber-950/60 border-amber-500/50 text-amber-300 animate-pulse'
                    : 'bg-rose-950/60 border-rose-500/50 text-rose-300 animate-bounce'
                }`}
              >
                {connectivity === 'online' ? (
                  <Wifi className="w-3 h-3 text-teal-400" />
                ) : (
                  <WifiOff className="w-3 h-3 text-rose-400" />
                )}
                <span className="capitalize hidden sm:inline">{connectivity}</span>
              </button>

            </div>

          </div>
        </header>

        {/* Main Routed Content */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            
            {/* Patient Kiosk Flow */}
            <Route
              path="/kiosk"
              element={
                <KioskContainer
                  currentLang={currentLang}
                  onLanguageChange={setCurrentLang}
                  connectivity={connectivity}
                  onUpdateConnectivity={setConnectivity}
                />
              }
            />

            {/* Physician OPD Flow (requires a signed-in doctor) */}
            <Route
              path="/physician"
              element={<RequireDoctor><PhysicianQueue /></RequireDoctor>}
            />
            <Route
              path="/physician/session/:sessionId"
              element={<RequireDoctor><ClinicalReview /></RequireDoctor>}
            />

            {/* Dedicated Emergency & Casualty Red-Flag Flow (requires a signed-in doctor) */}
            <Route
              path="/emergency"
              element={<RequireDoctor><EmergencyDashboard /></RequireDoctor>}
            />

            {/* Staff Intervention Flow */}
            <Route path="/staff" element={<StaffRoot />} />
            <Route path="/staff/login" element={<StaffLogin onLoginSuccess={() => {}} />} />
            <Route path="/staff/takeover/:sessionId" element={<StaffTakeoverWrapper />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500 space-y-1">
          <p className="font-semibold text-slate-700">
            MediKiosk — AI-Powered Multilingual Clinical History Platform for Indian Hospital OPDs
          </p>
          <p className="text-[11px] text-slate-400">
            Compliant with ABDM / ABHA Health Data Standards • Dual Allopathic & AYUSH Ontologies • Deterministic Triage Safety
          </p>
        </footer>

      </div>
    </BrowserRouter>
  );
};
export default App;
