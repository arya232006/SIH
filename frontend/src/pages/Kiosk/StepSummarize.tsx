import React, { useState, useEffect } from 'react';
import { 
 CheckCircle2, Volume2, ShieldCheck, ArrowLeft, 
 Sparkles, ArrowRight, Building2, Network, 
 QrCode, Printer, Check, RotateCcw, AlertTriangle,
 Stethoscope, MapPin, User, BellRing, Activity, Pill,
 HeartPulse, FileText, AlertCircle, VolumeX
} from 'lucide-react';
import { LanguageCode, PatientSession, SafetyCheckResponse } from '../../types';
import { translations } from '../../utils/i18n';
import { playTextToSpeech } from '../../utils/sound';
import { SafetyAlertsBadge } from '../../components/SafetyAlertsBadge';
import { ApiService } from '../../services/api';
import { KioskAccessibilitySettings } from '../../components/KioskAccessibilityToolbar';

interface StepSummarizeProps {
 session: PatientSession;
 currentLang: LanguageCode;
 onConfirm: () => Promise<void>;
 onBackToScan: () => void;
 onRestart: () => void;
 isLoading: boolean;
 isConfirmed: boolean;
 accessibilitySettings?: KioskAccessibilitySettings;
}

export const StepSummarize: React.FC<StepSummarizeProps> = ({
 session,
 currentLang,
 onConfirm,
 onBackToScan,
 onRestart,
 isLoading,
 isConfirmed,
 accessibilitySettings,
}) => {
 const t = translations[currentLang] || translations.en;
 const routing = session.departmentRouting;

 const [safetyData, setSafetyData] = useState<SafetyCheckResponse | null>(null);
 const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);

 useEffect(() => {
 if (session.sessionId) {
 ApiService.getSafetyCheck(session.sessionId)
 .then(setSafetyData)
 .catch((e) => console.warn("Safety check in summary failed:", e));
 }
 }, [session.sessionId]);

 const handlePlaySummary = () => {
 setIsPlayingAudio(true);
 const rate = accessibilitySettings?.slowSpeech ? 0.75 : 0.95;
 const summaryText = currentLang === 'hi'
 ? `नमस्ते ${session.patientName} जी। आपकी मुख्य समस्या है: ${session.chiefComplaint || 'सामान्य जांच'}। आपका टोकन नंबर है ${session.tokenNumber}। आपको ${routing?.department || 'जनरल ओपीडी'} में डॉक्टर ${routing?.doctorName || ''} के पास ${routing?.roomNumber || 'कमरा नंबर 101'} पर जाना है।`
 : `Summary for ${session.patientName}. Chief concern: ${session.chiefComplaint || 'General OPD visit'}. Your token number is ${session.tokenNumber}. You are routed to ${routing?.department || 'General Medicine'}, Doctor ${routing?.doctorName || ''} at ${routing?.roomNumber || 'Room 101'}.`;
 playTextToSpeech(summaryText, currentLang, rate);
 setTimeout(() => setIsPlayingAudio(false), 4500);
 };

 const handlePlaySuccessAudio = () => {
 const rate = accessibilitySettings?.slowSpeech ? 0.75 : 0.95;
 const successText = currentLang === 'hi'
 ? `पंजीकरण पूरा हुआ! आपका टोकन नंबर ${session.tokenNumber} है। कृपया ${routing?.roomNumber || 'कमरा नंबर 101'} पर जाएं, जहां डॉक्टर ${routing?.doctorName || ''} आपसे मिलेंगे।`
 : `Intake complete! Your token number is ${session.tokenNumber}. Please proceed to ${routing?.roomNumber || 'Room 101'} for Doctor ${routing?.doctorName || ''}.`;
 playTextToSpeech(successText, currentLang, rate);
 };

 // If confirmed, show Success Screen with Spoken Directions
 if (isConfirmed) {
 return (
 <div className="max-w-3xl mx-auto bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden text-center p-8 sm:p-12 space-y-8 animate-in fade-in zoom-in-95 duration-300">
 
 {/* Success Icon Badge */}
 <div className="w-24 h-24 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/20">
 <CheckCircle2 className="w-14 h-14 stroke-[2.5]" />
 </div>

 <div className="space-y-2">
 <span className="text-xs font-black uppercase tracking-widest text-emerald-800 bg-emerald-100 px-4 py-1.5 rounded-full border border-emerald-300">
 ✓ INTAKE COMPLETE &amp; QUEUED
 </span>
 <h2 className="text-3xl sm:text-4xl font-black text-slate-900">
 {t.successTitle}
 </h2>
 <p className="text-slate-600 text-sm sm:text-base max-w-md mx-auto font-medium">
 {t.successSubtitle}
 </p>
 </div>

 {/* Token Card */}
 <div className="bg-slate-950 text-white rounded-3xl p-6 sm:p-8 max-w-md mx-auto shadow-2xl space-y-3 border-2 border-teal-500/30">
 <span className="text-xs uppercase font-extrabold text-teal-400 tracking-wider">
 {t.tokenNumberLabel}
 </span>
 <div className="text-6xl sm:text-7xl font-black font-mono text-white tracking-tight">
 {session.tokenNumber}
 </div>
 <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
 <span>Patient: <strong className="text-white">{session.patientName}</strong></span>
 <span>Visit ID: <strong className="text-white font-mono">{session.visitId}</strong></span>
 </div>
 </div>

 {/* Department & Doctor Routing Card */}
 {routing && (
 <div className="bg-gradient-to-br from-teal-50 to-emerald-50 border-2 border-teal-300 rounded-3xl p-6 max-w-lg mx-auto text-left shadow-md space-y-4">
 <div className="flex items-center justify-between">
 <div className="flex items-center space-x-3">
 <div className="p-3 bg-teal-700 text-white rounded-2xl shadow-md">
 <Stethoscope className="w-6 h-6" />
 </div>
 <div>
 <span className="text-[10px] font-black uppercase tracking-wider text-teal-900 bg-teal-200/80 px-2.5 py-0.5 rounded">
 ASSIGNED OPD CLINIC
 </span>
 <h3 className="text-xl font-black text-slate-900 leading-tight">
 {routing.department}
 </h3>
 </div>
 </div>

 <span className={`text-[10px] font-black uppercase px-3 py-1 rounded-full shadow-sm ${
 routing.assignedBy === 'staff-triage'
 ? 'bg-amber-500 text-slate-950 border border-amber-600'
 : 'bg-teal-700 text-white'
 }`}>
 {routing.assignedBy === 'staff-triage' ? 'Staff Triage' : 'AI Triaged'}
 </span>
 </div>

 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs pt-2 border-t border-teal-200">
 <div className="space-y-0.5">
 <span className="text-slate-600 font-bold flex items-center space-x-1">
 <User className="w-4 h-4 text-teal-700" />
 <span>Assigned Doctor:</span>
 </span>
 <strong className="text-slate-900 block font-extrabold text-base">
 {routing.doctorName}
 </strong>
 <span className="text-[11px] text-slate-600">
 {routing.doctorTitle || 'Consultant Specialist'}
 </span>
 </div>

 <div className="space-y-0.5">
 <span className="text-slate-600 font-bold flex items-center space-x-1">
 <MapPin className="w-4 h-4 text-rose-600" />
 <span>OPD Location &amp; Room:</span>
 </span>
 <strong className="text-emerald-900 block font-extrabold text-base">
 {routing.roomNumber}
 </strong>
 <span className="text-[11px] text-slate-600">
 {routing.floorLocation || 'Main OPD Block'}
 </span>
 </div>
 </div>

 {/* Spoken Directions Audio Trigger */}
 <div className="pt-1">
 <button
 type="button"
 onClick={handlePlaySuccessAudio}
 className="w-full py-2.5 bg-teal-100 hover:bg-teal-200 text-teal-950 font-bold text-xs rounded-xl flex items-center justify-center space-x-2 transition-colors cursor-pointer min-h-[44px]"
 >
 <Volume2 className="w-4 h-4 text-teal-800" />
 <span>Hear Spoken Room Directions</span>
 </button>
 </div>

 {routing.isAmbiguous && (
 <div className="bg-amber-100/90 border border-amber-300 text-amber-950 p-3 rounded-2xl text-xs flex items-center space-x-2">
 <BellRing className="w-5 h-5 text-amber-800 shrink-0" />
 <span>
 <strong>Nurse Assistance Active:</strong> Sister Priya Sharma has been notified to guide you directly to your consultation room.
 </span>
 </div>
 )}
 </div>
 )}

 {/* Interoperability Architecture Diagram */}
 <div className="bg-slate-50 border border-slate-200 rounded-3xl p-5 max-w-lg mx-auto text-left space-y-3">
 <div className="flex items-center space-x-2 text-slate-800 text-xs font-bold">
 <Network className="w-4 h-4 text-teal-600" />
 <span>Digital Health Interoperability Status</span>
 </div>

 <div className="grid grid-cols-3 gap-3 text-center text-xs">
 <div className="p-3 bg-white rounded-2xl border border-slate-200 shadow-xs">
 <div className="w-8 h-8 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center mx-auto mb-1.5">
 <QrCode className="w-4 h-4" />
 </div>
 <div className="font-bold text-slate-900">ABHA PHR</div>
 <span className="text-[10px] text-emerald-600 font-bold">Linked</span>
 </div>

 <div className="p-3 bg-white rounded-2xl border border-slate-200 shadow-xs">
 <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center mx-auto mb-1.5">
 <Building2 className="w-4 h-4" />
 </div>
 <div className="font-bold text-slate-900">Hospital EHR</div>
 <span className="text-[10px] text-emerald-600 font-bold">Queued</span>
 </div>

 <div className="p-3 bg-white rounded-2xl border border-slate-200 shadow-xs">
 <div className="w-8 h-8 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center mx-auto mb-1.5">
 <ShieldCheck className="w-4 h-4" />
 </div>
 <div className="font-bold text-slate-900">DPDP Consent</div>
 <span className="text-[10px] text-emerald-600 font-bold">Active</span>
 </div>
 </div>
 </div>

 {/* Action Controls */}
 <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
 <button
 type="button"
 onClick={() => window.print()}
 className="w-full sm:w-auto px-6 py-4 rounded-2xl border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold text-sm flex items-center justify-center space-x-2 min-h-[56px] cursor-pointer"
 >
 <Printer className="w-5 h-5" />
 <span>Print Token Slip</span>
 </button>

 <button
 type="button"
 onClick={onRestart}
 className="w-full sm:w-auto px-8 py-4 rounded-2xl bg-teal-700 hover:bg-teal-800 text-white font-black text-base shadow-lg transition-all flex items-center justify-center space-x-2 min-h-[56px] cursor-pointer"
 >
 <RotateCcw className="w-5 h-5" />
 <span>New Patient Intake</span>
 </button>
 </div>

 </div>
 );
 }

 const isLarge = Boolean(accessibilitySettings?.largeText);
 const isHighContrast = Boolean(accessibilitySettings?.highContrast);

 // Pre-confirmation Summary Review Screen
 return (
 <div className="max-w-4xl mx-auto space-y-6">
 
 {/* Header Banner */}
 <div className={`rounded-3xl p-6 sm:p-8 shadow-xl border ${
 isHighContrast 
 ? 'bg-slate-950 border-yellow-400 text-white' 
 : 'bg-white border-slate-200'
 }`}>
 <div className="flex items-center space-x-2 text-teal-700 text-xs font-bold uppercase tracking-wider mb-2">
 <Sparkles className="w-4 h-4" />
 <span>Step 4 of 4 • {t.step4Confirm || 'Review & Confirmation'}</span>
 </div>
 <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
 <div>
 <h2 className={`font-black ${isLarge ? 'text-3xl sm:text-4xl' : 'text-2xl sm:text-3xl'}`}>
 {t.summaryTitle}
 </h2>
 <p className="text-sm text-slate-600 mt-1">
 {t.summarySubtitle}
 </p>
 </div>
 <button
 type="button"
 onClick={handlePlaySummary}
 className={`inline-flex items-center space-x-2 px-5 py-3 rounded-2xl transition-all shrink-0 min-h-[52px] font-bold text-xs sm:text-sm cursor-pointer shadow-md ${
 isPlayingAudio 
 ? 'bg-teal-700 text-white ring-4 ring-teal-400 animate-pulse' 
 : 'bg-teal-100 hover:bg-teal-200 text-teal-900'
 }`}
 >
 <Volume2 className="w-5 h-5" />
 <span>{t.playAudio}</span>
 </button>
 </div>
 </div>

 {/* Structured Visual Section Review Cards */}
 <div className={`rounded-3xl p-6 sm:p-8 shadow-xl border space-y-6 ${
 isHighContrast 
 ? 'bg-slate-950 border-yellow-400 text-white' 
 : 'bg-white border-slate-200'
 }`}>
 
 {/* Section 1: Patient Identity Card */}
 <div className="bg-slate-50 rounded-2xl p-4 sm:p-5 border border-slate-200 space-y-3">
 <div className="flex items-center space-x-2 font-black text-xs uppercase tracking-wider text-teal-800 ">
 <User className="w-4 h-4" />
 <span>1. Patient Profile &amp; Registration</span>
 </div>
 <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
 <div>
 <span className="text-slate-500 block">Name:</span>
 <strong className="text-slate-900 text-sm font-black">{session.patientName}</strong>
 </div>
 <div>
 <span className="text-slate-500 block">Age &amp; Gender:</span>
 <strong className="text-slate-900 font-bold">{session.age} Yrs / {session.gender}</strong>
 </div>
 <div>
 <span className="text-slate-500 block">ABHA ID:</span>
 <strong className="font-mono text-slate-900 font-bold">{session.patientId}</strong>
 </div>
 <div>
 <span className="text-slate-500 block">Preferred Language:</span>
 <strong className="uppercase text-teal-700 font-extrabold">{session.language}</strong>
 </div>
 </div>
 </div>

 {/* Nurse Clinical Synthesis Box */}
 {session.nurseSummary && (
 <div className="p-4 bg-teal-50 border border-teal-200 rounded-2xl text-xs space-y-2">
 <div className="flex items-center space-x-1.5 text-teal-900 font-bold">
 <Sparkles className="w-4 h-4 text-teal-700" />
 <span className="uppercase tracking-wider">Clinical Triage Intake Report:</span>
 </div>
 <p className="text-slate-800 leading-relaxed font-medium">
 {session.nurseSummary}
 </p>
 </div>
 )}

 {/* Safety Alerts */}
 {safetyData && (
 <SafetyAlertsBadge safetyData={safetyData} />
 )}

 {/* Section 2: Chief Concern & Symptoms */}
 <div className="bg-slate-50 rounded-2xl p-4 sm:p-5 border border-slate-200 space-y-3">
 <div className="flex items-center space-x-2 font-black text-xs uppercase tracking-wider text-teal-800 ">
 <HeartPulse className="w-4 h-4" />
 <span>2. Chief Complaint &amp; Symptom Exploration</span>
 </div>
 
 <div className="p-3.5 bg-white rounded-xl border border-slate-200 ">
 <span className="text-[11px] text-slate-500 font-semibold block">Primary Concern:</span>
 <p className="text-base sm:text-lg font-black text-slate-900 mt-0.5">
 {session.chiefComplaint || 'General OPD consultation requested.'}
 </p>
 </div>

 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
 <div className="p-3 bg-white rounded-xl border border-slate-200 ">
 <span className="text-slate-500 font-semibold block">Onset &amp; Timing:</span>
 <span className="text-slate-900 font-bold">{session.historyOfPresentIllness.onset || 'Acute onset'}</span>
 </div>
 <div className="p-3 bg-white rounded-xl border border-slate-200 ">
 <span className="text-slate-500 font-semibold block">Pain Character &amp; Severity:</span>
 <span className="text-slate-900 font-bold">{session.historyOfPresentIllness.character || 'Moderate intensity'}</span>
 </div>
 {session.historyOfPresentIllness.radiation && (
 <div className="p-3 bg-white rounded-xl border border-slate-200 sm:col-span-2">
 <span className="text-slate-500 font-semibold block">Site &amp; Radiation:</span>
 <span className="text-slate-900 font-bold">{session.historyOfPresentIllness.radiation}</span>
 </div>
 )}
 </div>
 </div>

 {/* Section 3: Baseline Vitals & Body Pain Map */}
 {session.painAssessment && (
 <div className="bg-slate-50 rounded-2xl p-4 sm:p-5 border border-slate-200 space-y-3">
 <div className="flex items-center space-x-2 font-black text-xs uppercase tracking-wider text-teal-800 ">
 <Activity className="w-4 h-4" />
 <span>3. Baseline Vitals &amp; Pain Localization</span>
 </div>
 <div className="p-3.5 bg-white rounded-xl border border-slate-200 text-xs space-y-1">
 <span className="text-[11px] text-slate-500 font-semibold block">Pain Assessment Map:</span>
 <p className="font-bold text-slate-900 ">
 {session.painAssessment.side} {session.painAssessment.anatomicalRegion} • {session.painAssessment.painCharacter} • VAS Severity {session.painAssessment.painSeverityVAS}/10
 {session.painAssessment.radiationPath && ` • Radiation: ${session.painAssessment.radiationPath}`}
 </p>
 </div>
 </div>
 )}

 {/* Section 4: Medications & Allergies */}
 <div className="bg-slate-50 rounded-2xl p-4 sm:p-5 border border-slate-200 space-y-3">
 <div className="flex items-center space-x-2 font-black text-xs uppercase tracking-wider text-teal-800 ">
 <Pill className="w-4 h-4" />
 <span>4. Current Medications &amp; Allergies</span>
 </div>
 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
 <div className="p-3.5 bg-white rounded-xl border border-slate-200 space-y-1">
 <span className="text-slate-500 font-semibold block">Known Drug Allergies:</span>
 <strong className="text-slate-900 block font-bold">{session.drugAllergyHistory.allergies || 'No known allergies'}</strong>
 </div>
 <div className="p-3.5 bg-white rounded-xl border border-slate-200 space-y-1">
 <span className="text-slate-500 font-semibold block">Daily / Regular Medicines:</span>
 <span className="text-slate-900 font-medium">
 {session.drugAllergyHistory.currentMedications.join(', ') || 'None reported'}
 </span>
 </div>
 </div>
 </div>

 {/* Section 5: Attached Documents Summary */}
 <div className="bg-slate-50 rounded-2xl p-4 sm:p-5 border border-slate-200 space-y-3">
 <div className="flex items-center justify-between">
 <div className="flex items-center space-x-2 font-black text-xs uppercase tracking-wider text-teal-800 ">
 <FileText className="w-4 h-4" />
 <span>5. Attached Documents &amp; Lab Reports ({session.priorInvestigations.length})</span>
 </div>
 </div>

 {session.priorInvestigations.length > 0 ? (
 <div className="space-y-2">
 {session.priorInvestigations.map((doc, idx) => (
 <div key={idx} className="p-3 bg-white rounded-xl border border-slate-200 flex items-center justify-between text-xs">
 <div>
 <span className="font-bold text-slate-900 ">{doc.document}</span>
 <span className="text-slate-500 ml-2">({doc.timestamp})</span>
 </div>
 <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
 Digitized ({Math.round(doc.confidence * 100)}% Conf)
 </span>
 </div>
 ))}
 </div>
 ) : (
 <p className="text-xs text-slate-500 italic">No previous documents attached.</p>
 )}
 </div>

 </div>

 {/* Confirmation Button Bar */}
 <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
 <button
 type="button"
 onClick={onBackToScan}
 className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 text-sm font-bold text-slate-700 hover:text-slate-900 px-6 py-4 rounded-2xl border border-slate-300 bg-white hover:bg-slate-50 min-h-[56px] cursor-pointer"
 >
 <ArrowLeft className="w-4 h-4" />
 <span>{t.fixBtn}</span>
 </button>

 <button
 type="button"
 disabled={isLoading}
 onClick={onConfirm}
 className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 text-lg font-black text-white px-10 py-4 rounded-2xl bg-gradient-to-r from-teal-700 to-teal-800 hover:from-teal-800 hover:to-teal-900 shadow-xl shadow-teal-700/30 transition-all min-h-[64px] cursor-pointer active:scale-95"
 >
 {isLoading ? (
 <span>Routing to OPD Doctor...</span>
 ) : (
 <>
 <Check className="w-6 h-6" />
 <span>{t.confirmSendBtn}</span>
 </>
 )}
 </button>
 </div>

 </div>
 );
};
