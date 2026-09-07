import React, { useState, useEffect, useRef } from 'react';
import { 
 Mic, MicOff, Volume2, Sparkles, AlertTriangle, ShieldAlert,
 ArrowLeft, ArrowRight, CornerDownLeft, Loader2, 
 CheckCircle2, RefreshCw, HeartPulse, Globe, Languages,
 Activity, ShieldCheck, Stethoscope, BellRing, UserCheck,
 Scale, Ruler, Heart, Info, X, Thermometer, Flame, Wind,
 Brain, Bone, Check, HelpCircle, Eye, Gauge
} from 'lucide-react';
import { 
 LanguageCode, PatientSession, AdaptiveQuestion, 
 RedFlag, QAPair 
} from '../../types';
import { translations } from '../../utils/i18n';
import { VITALS_I18N } from '../../utils/clinicalQuestionsI18n';
import { AudioVisualizer } from '../../components/AudioVisualizer';
import { BodyMapSelector } from '../../components/BodyMapSelector';
import { playTextToSpeech, stopTextToSpeech } from '../../utils/sound';
import { ApiService } from '../../services/api';
import { KioskAccessibilitySettings } from '../../components/KioskAccessibilityToolbar';

interface StepConverseProps {
 session: PatientSession;
 currentLang: LanguageCode;
 onLanguageChange?: (lang: LanguageCode) => void;
 currentQuestion: AdaptiveQuestion;
 redFlag: RedFlag;
 onAnswerSubmit: (
 answer: string,
 mode: 'voice' | 'tap',
 ayushMode: boolean,
 field?: string,
 questionText?: string,
 clinicalText?: string
 ) => Promise<void>;
 onUndoAnswer: () => Promise<void>;
 onProceedToScan: () => void;
 isLoading: boolean;
 onToggleAyush: (active: boolean) => void;
 accessibilitySettings?: KioskAccessibilitySettings;
}

export const StepConverse: React.FC<StepConverseProps> = ({
 session,
 currentLang,
 onLanguageChange,
 currentQuestion,
 redFlag,
 onAnswerSubmit,
 onUndoAnswer,
 onProceedToScan,
 isLoading,
 onToggleAyush,
 accessibilitySettings,
}) => {
 const t = translations[currentLang] || translations.en;
 const vitalsText = VITALS_I18N[currentLang] || VITALS_I18N.en;

 const [textInput, setTextInput] = useState<string>('');
 const [isRecording, setIsRecording] = useState<boolean>(false);
 const [isProcessingAudio, setIsProcessingAudio] = useState<boolean>(false);
 const [isSpeakingPrompt, setIsSpeakingPrompt] = useState<boolean>(false);
 const [interimTranscript, setInterimTranscript] = useState<string>('');
 const [pendingVoiceAnswer, setPendingVoiceAnswer] = useState<string | null>(null);
 // English rendering of the pending answer. The clinical rules match English
 // keywords, so speech in another language needs this to raise a red flag.
 const [pendingVoiceClinical, setPendingVoiceClinical] = useState<string | undefined>(undefined);
 const [detectedAccent, setDetectedAccent] = useState<string>('Indian English / Multilingual');
 const [normalizedTerms, setNormalizedTerms] = useState<string[]>([]);
 const [isCallingStaff, setIsCallingStaff] = useState<boolean>(false);
 const [staffCalledNotice, setStaffCalledNotice] = useState<boolean>(false);

 // Vitals Quick Numeric Entry State
 const [numWeight, setNumWeight] = useState<string>('65');
 const [numHeight, setNumHeight] = useState<string>('168');
 const [numSystolic, setNumSystolic] = useState<string>('120');
 const [numDiastolic, setNumDiastolic] = useState<string>('80');

 // Non-Disclosure Reconsideration & Reason Modal State
 const [showNonDisclosureModal, setShowNonDisclosureModal] = useState<boolean>(false);
 const [nonDisclosureStage, setNonDisclosureStage] = useState<'alert' | 'reason'>('alert');
 const [selectedReason, setSelectedReason] = useState<string>('');
 const [customReasonText, setCustomReasonText] = useState<string>('');
 const [pendingOptionText, setPendingOptionText] = useState<string>('');
 
 // Interactive Body Pain Map State
 const [showBodyMapModal, setShowBodyMapModal] = useState<boolean>(false);
 
 // Selected Accent / Dialect for Voice Input
 const [selectedAccent, setSelectedAccent] = useState<string>(() => {
 const defaultAccents: Record<LanguageCode, string> = {
 en: 'en-IN',
 hi: 'hi-IN',
 bn: 'bn-IN',
 ta: 'ta-IN',
 te: 'te-IN',
 };
 return defaultAccents[currentLang] || 'en-IN';
 });

 const isVitalsTurn = 
 (currentQuestion.field || '').toLowerCase().includes('vitals') ||
 (currentQuestion.field || '').toLowerCase().includes('weight') ||
 (currentQuestion.field || '').toLowerCase().includes('height') ||
 (currentQuestion.field || '').toLowerCase().includes('blood_pressure') ||
 (currentQuestion.field || '').toLowerCase().includes('bp');

 const isNonDisclosureOption = (opt: string) => {
 const lower = opt.toLowerCase();
 return lower.includes('prefer not') || lower.includes('skip') || lower.includes('decline') || 
 lower.includes('छोड़ें') || lower.includes('एড়িয়ে') || lower.includes('தவிர்க்க') || lower.includes('వదిలివేయండి');
 };

 // Helper to map option text to semantic icons
 const getSemanticOptionIcon = (optionText: string) => {
 const lower = optionText.toLowerCase();
 if (isNonDisclosureOption(optionText)) {
 return <HelpCircle className="w-5 h-5 text-amber-500 shrink-0" />;
 }
 if (lower.includes('chest') || lower.includes('heart') || lower.includes('सीने') || lower.includes('বুকে') || lower.includes('நெஞ்சு') || lower.includes('ఛాతీ')) {
 return <HeartPulse className="w-5 h-5 text-rose-500 shrink-0" />;
 }
 if (lower.includes('fever') || lower.includes('temp') || lower.includes('chills') || lower.includes('बुखार') || lower.includes('জ্বর') || lower.includes('காய்ச்சல்') || lower.includes('జ్వరం')) {
 return <Thermometer className="w-5 h-5 text-amber-600 shrink-0" />;
 }
 if (lower.includes('stomach') || lower.includes('acid') || lower.includes('gas') || lower.includes('पेट') || lower.includes('পেট') || lower.includes('வயிறு') || lower.includes('కడుపు') || lower.includes('burning')) {
 return <Flame className="w-5 h-5 text-orange-500 shrink-0" />;
 }
 if (lower.includes('head') || lower.includes('dizzy') || lower.includes('सिर') || lower.includes('মাথা') || lower.includes('தலை') || lower.includes('తల')) {
 return <Brain className="w-5 h-5 text-indigo-500 shrink-0" />;
 }
 if (lower.includes('breath') || lower.includes('cough') || lower.includes('कफ') || lower.includes('सांस') || lower.includes('কাশি') || lower.includes('இருமல்') || lower.includes('దగ్గు') || lower.includes('wind')) {
 return <Wind className="w-5 h-5 text-sky-500 shrink-0" />;
 }
 if (lower.includes('knee') || lower.includes('joint') || lower.includes('back') || lower.includes('leg') || lower.includes('घुटने') || lower.includes('दर्द') || lower.includes('হাঁটু') || lower.includes('முழங்கால்') || lower.includes('మోకాలు')) {
 return <Activity className="w-5 h-5 text-teal-600 shrink-0" />;
 }
 if (lower.includes('yes') || lower.includes('हाँ') || lower.includes('হ্যাঁ') || lower.includes('ஆம்') || lower.includes('అవును')) {
 return <Check className="w-5 h-5 text-emerald-600 shrink-0" />;
 }
 if (lower.includes('no') || lower.includes('नहीं') || lower.includes('না') || lower.includes('இல்லை') || lower.includes('కాదు')) {
 return <X className="w-5 h-5 text-slate-400 shrink-0" />;
 }
 return <Sparkles className="w-5 h-5 text-teal-600 shrink-0" />;
 };

 const handleCallStaffNurse = async () => {
 try {
 setIsCallingStaff(true);
 await ApiService.callStaff(session.sessionId, 'Patient requested assistance at Kiosk #1');
 setStaffCalledNotice(true);
 } catch (err) {
 console.error('Failed to call staff:', err);
 setStaffCalledNotice(true);
 } finally {
 setIsCallingStaff(false);
 }
 };

 const mediaRecorderRef = useRef<MediaRecorder | null>(null);
 const audioChunksRef = useRef<Blob[]>([]);
 const simulatedTimerRef = useRef<any>(null);

 // Sync selected accent with parent language changes
 useEffect(() => {
 const defaultAccents: Record<LanguageCode, string> = {
 en: 'en-IN',
 hi: 'hi-IN',
 bn: 'bn-IN',
 ta: 'ta-IN',
 te: 'te-IN',
 };
 setSelectedAccent(defaultAccents[currentLang] || 'en-IN');
 }, [currentLang]);

 // Clean inputs & trigger TTS when prompt changes
 useEffect(() => {
 setTextInput('');
 setInterimTranscript('');
 setPendingVoiceAnswer(null);
 setNormalizedTerms([]);
 setStaffCalledNotice(false);
 setShowNonDisclosureModal(false);

 // Auto-TTS if readAloud is active
 if (accessibilitySettings?.readAloud && currentQuestion?.question) {
 const rate = accessibilitySettings.slowSpeech ? 0.75 : 0.95;
 setIsSpeakingPrompt(true);
 playTextToSpeech(currentQuestion.question, currentLang, rate);
 setTimeout(() => setIsSpeakingPrompt(false), 3500);
 }
 }, [currentQuestion.question, currentLang]);

 // Auto-speak question when prompt audio button clicked
 const handlePlayQuestion = () => {
 setIsSpeakingPrompt(true);
 const rate = accessibilitySettings?.slowSpeech ? 0.75 : 0.95;
 playTextToSpeech(currentQuestion.question, currentLang, rate);
 setTimeout(() => setIsSpeakingPrompt(false), 3500);
 };

 // Toggle voice recording
 const handleToggleVoice = async () => {
 if (isRecording) {
 stopRecordingSession();
 } else {
 startRecordingSession();
 }
 };

 const startRecordingSession = async () => {
 try {
 audioChunksRef.current = [];
 const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
 const mediaRecorder = new MediaRecorder(stream);
 mediaRecorderRef.current = mediaRecorder;

 mediaRecorder.ondataavailable = (event) => {
 if (event.data.size > 0) {
 audioChunksRef.current.push(event.data);
 }
 };

 mediaRecorder.onstop = async () => {
 const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
 await handleProcessAudioBlob(audioBlob);
 stream.getTracks().forEach((track) => track.stop());
 };

 mediaRecorder.start();
 setIsRecording(true);
 } catch (err) {
 console.warn("Microphone hardware access unavailable, using simulated voice fallback.", err);
 setIsRecording(true);
 triggerSimulatedVoiceFallback();
 }
 };

 const stopRecordingSession = () => {
 setIsRecording(false);
 if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
 mediaRecorderRef.current.stop();
 }
 if (simulatedTimerRef.current) {
 clearTimeout(simulatedTimerRef.current);
 }
 };

 const handleProcessAudioBlob = async (audioBlob: Blob) => {
 setIsProcessingAudio(true);
 try {
 const activeId = session.sessionId || session.patientId;
 const res = await ApiService.transcribeAudio(activeId, audioBlob, selectedAccent);
 if (res.transcript) {
 setDetectedAccent(res.accent || 'Indian English / Hinglish');
 setNormalizedTerms(res.normalizedMedicalTerms || []);
 
 // In Guided/Assisted Mode: show verification preview box so user can confirm or retry
 if (accessibilitySettings?.guidedMode || accessibilitySettings?.assistedMode) {
 setPendingVoiceAnswer(res.transcript);
 setPendingVoiceClinical(res.clinicalText);
 setInterimTranscript(res.transcript);
 
 // Audio confirmation
 const confirmPrompt = currentLang === 'hi'
 ? `आपने कहा: "${res.transcript}"। पुष्टि के लिए हरा बटन दबाएं।`
 : `You said: "${res.transcript}". Press Confirm or Speak Again.`;
 playTextToSpeech(confirmPrompt, currentLang, accessibilitySettings?.slowSpeech ? 0.75 : 0.95);
 } else {
 onAnswerSubmit(
 res.transcript,
 'voice',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question,
 res.clinicalText
 );
 }
 }
 } catch (err) {
 console.warn("Backend audio transcribe failed, using local transcript.", err);
 } finally {
 setIsProcessingAudio(false);
 }
 };

 const triggerSimulatedVoiceFallback = () => {
 const chosenOption =
 currentQuestion.options && currentQuestion.options.length > 0
 ? currentQuestion.options[0]
 : "Mild symptoms for 2 days";

 simulatedTimerRef.current = setTimeout(() => {
 setIsRecording(false);
 if (accessibilitySettings?.guidedMode || accessibilitySettings?.assistedMode) {
 setPendingVoiceAnswer(chosenOption);
 setInterimTranscript(chosenOption);
 } else {
 setInterimTranscript(chosenOption);
 onAnswerSubmit(
 chosenOption,
 'voice',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question
 );
 }
 }, 1800);
 };

 const handleConfirmPendingVoiceAnswer = () => {
 if (!pendingVoiceAnswer) return;
 const answer = pendingVoiceAnswer;
 const clinical = pendingVoiceClinical;
 setPendingVoiceAnswer(null);
 setPendingVoiceClinical(undefined);
 onAnswerSubmit(
 answer,
 'voice',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question,
 clinical
 );
 };

 const handleRetryVoiceAnswer = () => {
 setPendingVoiceAnswer(null);
 setInterimTranscript('');
 startRecordingSession();
 };

 const handleChipSelect = (optionText: string) => {
 if (isLoading) return;

 // Check if patient selected non-disclosure option
 if (isNonDisclosureOption(optionText)) {
 setPendingOptionText(optionText);
 setNonDisclosureStage('alert');
 setShowNonDisclosureModal(true);
 return;
 }

 onAnswerSubmit(
 optionText,
 'tap',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question
 );
 };

 const handleConfirmNonDisclosure = () => {
 const reason = customReasonText.trim() || selectedReason || vitalsText.reasonOptions[0];
 const finalAnswer = `Prefer not to disclose (${reason})`;
 setShowNonDisclosureModal(false);
 onAnswerSubmit(
 finalAnswer,
 'tap',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question
 );
 setSelectedReason('');
 setCustomReasonText('');
 };

 const handleCustomNumericVitalsSubmit = () => {
 const customAnswer = `Height: ${numHeight} cm, Weight: ${numWeight} kg, Blood Pressure: ${numSystolic}/${numDiastolic} mmHg`;
 onAnswerSubmit(
 customAnswer,
 'tap',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question
 );
 };

 const handleTextSubmit = (e: React.FormEvent) => {
 e.preventDefault();
 if (!textInput.trim() || isLoading) return;

 if (isNonDisclosureOption(textInput.trim())) {
 setPendingOptionText(textInput.trim());
 setNonDisclosureStage('alert');
 setShowNonDisclosureModal(true);
 return;
 }

 onAnswerSubmit(
 textInput.trim(),
 'tap',
 session.ayushMode,
 currentQuestion.field,
 currentQuestion.question
 );
 setTextInput('');
 };

 const handleSaveBodyPain = async (painData: any) => {
 try {
 await ApiService.savePainAssessment(session.sessionId, painData);
 const painAnswer = `${painData.painCharacter} pain in ${painData.anatomicalRegion} (${painData.side || 'Bilateral'}) with severity VAS ${painData.painSeverityVAS}/10${painData.radiationPath ? `, radiating to ${painData.radiationPath}` : ''}`;
 onAnswerSubmit(
 painAnswer,
 'tap',
 session.ayushMode,
 currentQuestion.field || 'chiefComplaint',
 currentQuestion.question
 );
 } catch (err) {
 console.error("Save pain map error:", err);
 }
 };

 // Determine specialty category label
 const isHomeopathy = Boolean(session.homeopathyMode || session.medicalSystem === 'homeopathy');
 const isAyurveda = Boolean(session.ayushMode || session.medicalSystem === 'ayurveda');

 const symptomCategoryLabel = currentQuestion.symptomCategory || 
 (isHomeopathy ? 'AYUSH Homeopathy' : isAyurveda ? 'AYUSH Ayurveda' : 'Clinical Specialty Triage');

 const isLarge = Boolean(accessibilitySettings?.largeText);
 const isHighContrast = Boolean(accessibilitySettings?.highContrast);
 const isGuided = Boolean(accessibilitySettings?.guidedMode);

 return (
 <div className="max-w-4xl mx-auto space-y-6">
 
 {/* 1. Red Flag Emergency Alert Banner */}
 {redFlag.triggered && (
 <div className="bg-rose-600 text-white rounded-3xl p-6 shadow-2xl border-2 border-rose-300 animate-pulse space-y-4">
 <div className="flex items-start space-x-4">
 <div className="p-3.5 bg-white/20 rounded-2xl shrink-0">
 <AlertTriangle className="w-10 h-10 text-white stroke-[2.5]" />
 </div>
 <div className="space-y-1">
 <div className="flex items-center space-x-2">
 <span className="text-xs font-black uppercase tracking-wider bg-white text-rose-700 px-2.5 py-0.5 rounded shadow-sm">
 PRIORITY EMERGENCY RED FLAG DETECTED
 </span>
 <span className="text-xs font-mono text-rose-100">
 Acuity: {redFlag.urgency?.toUpperCase() || 'EMERGENCY'}
 </span>
 </div>
 <h2 className="text-xl sm:text-2xl font-black tracking-tight">
 {redFlag.reason || "Acute clinical warning signs observed during pre-consultation."}
 </h2>
 <p className="text-xs sm:text-sm text-rose-100 font-medium leading-relaxed">
 Action Required: {redFlag.action || "Patient is being prioritized for casualty medical officer evaluation."}
 </p>
 </div>
 </div>

 <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-rose-400/40">
 <div className="flex items-center space-x-2 text-xs font-semibold text-rose-100">
 <ShieldAlert className="w-4 h-4 text-white" />
 <span>Routine OPD intake paused. Emergency protocol activated.</span>
 </div>
 <button
 type="button"
 onClick={() => window.location.href = '/emergency'}
 className="px-5 py-3 bg-white text-rose-700 hover:bg-rose-50 text-xs font-black rounded-xl shadow-lg flex items-center space-x-1.5 transition-all cursor-pointer min-h-[48px]"
 >
 <span>Transfer to Casualty Desk</span>
 <ArrowRight className="w-4 h-4" />
 </button>
 </div>
 </div>
 )}

 {/* Main Conversation Container */}
 <div className={`rounded-3xl shadow-xl border overflow-hidden transition-all ${
 isHighContrast 
 ? 'bg-slate-950 border-yellow-400 text-white' 
 : 'bg-white border-slate-200'
 }`}>
 
 {/* Top Bar: Progress & Status */}
 <div className={`px-6 py-4 flex flex-wrap items-center justify-between gap-3 ${
 isHighContrast ? 'bg-slate-900 border-b border-yellow-400 text-yellow-300' : 'bg-slate-900 text-white'
 }`}>
 <div className="flex items-center space-x-3">
 <div className="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center text-white font-bold text-sm shadow-sm">
 Q
 </div>
 <div>
 <div className="flex items-center space-x-2">
 <span className="bg-teal-900/80 border border-teal-400 text-teal-300 text-[10px] font-bold px-2 py-0.5 rounded-full">
 {symptomCategoryLabel}
 </span>
 {isHomeopathy && (
 <span className="bg-cyan-900/80 border border-cyan-400 text-cyan-300 text-[10px] font-bold px-2 py-0.5 rounded-full">
 💧 Homeopathy Active
 </span>
 )}
 {isAyurveda && !isHomeopathy && (
 <span className="bg-emerald-900/80 border border-emerald-400 text-emerald-300 text-[10px] font-bold px-2 py-0.5 rounded-full">
 🌿 Ayurveda Active
 </span>
 )}
 {isVitalsTurn && (
 <span className="bg-blue-900/80 border border-blue-400 text-blue-300 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
 <Activity className="w-3 h-3" />
 Mandatory OPD Vitals
 </span>
 )}
 </div>
 <h1 className="text-base font-extrabold text-white">
 Conversational Symptom Exploration
 </h1>
 </div>
 </div>

 <div className="flex items-center space-x-2">
 <button
 type="button"
 onClick={handleCallStaffNurse}
 disabled={isCallingStaff || staffCalledNotice}
 className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 shadow-sm min-h-[40px] cursor-pointer ${
 staffCalledNotice
 ? 'bg-emerald-600 text-white'
 : 'bg-amber-500 hover:bg-amber-600 text-slate-950 hover:text-white'
 }`}
 >
 <BellRing className="w-3.5 h-3.5" />
 <span>{staffCalledNotice ? 'Nurse Notified' : 'Need Help? Call Staff'}</span>
 </button>
 </div>
 </div>

 {/* Question Area */}
 <div className="p-6 sm:p-8 space-y-6">

 {/* In-Step Language Switcher Bar */}
 <div className={`flex flex-wrap items-center justify-between gap-2 p-3 rounded-2xl border ${
 isHighContrast ? 'bg-slate-900 border-slate-700' : 'bg-slate-100/90 border-slate-200'
 }`}>
 <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-700 ">
 <Globe className="w-4 h-4 text-teal-600" />
 <span>Switch Language:</span>
 </div>
 <div className="flex flex-wrap items-center gap-1.5">
 {[
 { code: 'en', label: 'English' },
 { code: 'hi', label: 'हिंदी (Hindi)' },
 { code: 'bn', label: 'বাংলা (Bengali)' },
 { code: 'ta', label: 'தமிழ் (Tamil)' },
 { code: 'te', label: 'తెలుగు (Telugu)' },
 ].map((lang) => (
 <button
 key={lang.code}
 type="button"
 onClick={() => onLanguageChange && onLanguageChange(lang.code as LanguageCode)}
 className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all min-h-[38px] cursor-pointer ${
 currentLang === lang.code
 ? 'bg-teal-700 text-white shadow-sm ring-2 ring-teal-500/50'
 : 'bg-white text-slate-700 hover:bg-slate-200 border border-slate-300/80'
 }`}
 >
 {lang.label}
 </button>
 ))}
 </div>
 </div>
 
 {/* Active Question Prompt Card */}
 <div className={`p-5 sm:p-6 rounded-3xl border-2 space-y-4 ${
 isHighContrast
 ? 'bg-slate-900 border-yellow-400 text-yellow-300'
 : 'bg-gradient-to-r from-teal-50/70 to-slate-50 border-teal-200'
 }`}>
 <div className="flex items-start justify-between gap-4">
 <div className="space-y-1">
 <span className="text-[11px] font-black uppercase tracking-wider text-teal-800 ">
 CLINICAL INTAKE QUESTION
 </span>
 <h2 className={`font-black leading-snug ${
 isHighContrast ? 'text-yellow-300' : 'text-slate-900'
 } ${isLarge ? 'text-2xl sm:text-3xl' : 'text-xl sm:text-2xl'}`}>
 {currentQuestion.question}
 </h2>
 </div>

 {/* Large Audio Readout Button */}
 <button
 type="button"
 onClick={handlePlayQuestion}
 title="Read question aloud (Text-to-Speech)"
 className={`p-3.5 rounded-2xl border transition-all shrink-0 shadow-md min-h-[56px] min-w-[56px] flex items-center justify-center cursor-pointer ${
 isSpeakingPrompt 
 ? 'bg-teal-700 text-white ring-4 ring-teal-400 animate-pulse' 
 : 'bg-white hover:bg-teal-50 text-teal-800 border-slate-200 hover:border-teal-300'
 }`}
 >
 <Volume2 className="w-7 h-7" />
 </button>
 </div>

 {/* Visual Progress bar */}
 <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
 <div
 className="bg-teal-600 h-full rounded-full transition-all duration-500"
 style={{ width: `${currentQuestion.progressPercent}%` }}
 />
 </div>
 </div>

 {/* Vitals Specific Common 3-in-1 Numeric Quick-Entry Pad */}
 {isVitalsTurn && (
 <div className="p-5 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-3xl space-y-4 shadow-sm">
 <div className="flex items-center justify-between">
 <div className="flex items-center space-x-2 text-xs font-black text-blue-900 uppercase tracking-wider">
 <Activity className="w-4 h-4 text-blue-700" />
 <span>Interactive Baseline OPD Vitals Entry (3-in-1)</span>
 </div>
 <span className="text-[10px] font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
 Mandatory Baseline
 </span>
 </div>

 <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
 {/* 1. Height */}
 <div className="bg-white p-3.5 rounded-2xl border border-blue-200 shadow-sm space-y-1.5">
 <label className="text-xs font-bold text-slate-700 flex items-center justify-between">
 <span className="flex items-center gap-1">
 <Ruler className="w-4 h-4 text-blue-600" />
 Height:
 </span>
 <span className="text-slate-400 font-mono">cm</span>
 </label>
 <input
 type="number"
 value={numHeight}
 onChange={(e) => setNumHeight(e.target.value)}
 className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-base font-bold text-slate-900 focus:ring-2 focus:ring-blue-500 focus:bg-white focus:outline-none min-h-[48px]"
 placeholder="168"
 />
 </div>

 {/* 2. Weight */}
 <div className="bg-white p-3.5 rounded-2xl border border-blue-200 shadow-sm space-y-1.5">
 <label className="text-xs font-bold text-slate-700 flex items-center justify-between">
 <span className="flex items-center gap-1">
 <Scale className="w-4 h-4 text-blue-600" />
 Weight:
 </span>
 <span className="text-slate-400 font-mono">kg</span>
 </label>
 <input
 type="number"
 value={numWeight}
 onChange={(e) => setNumWeight(e.target.value)}
 className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-base font-bold text-slate-900 focus:ring-2 focus:ring-blue-500 focus:bg-white focus:outline-none min-h-[48px]"
 placeholder="65"
 />
 </div>

 {/* 3. Blood Pressure */}
 <div className="bg-white p-3.5 rounded-2xl border border-blue-200 shadow-sm space-y-1.5">
 <label className="text-xs font-bold text-slate-700 flex items-center justify-between">
 <span className="flex items-center gap-1">
 <HeartPulse className="w-4 h-4 text-rose-600" />
 Blood Pressure:
 </span>
 <span className="text-slate-400 font-mono">mmHg</span>
 </label>
 <div className="flex items-center space-x-1.5">
 <input
 type="number"
 value={numSystolic}
 onChange={(e) => setNumSystolic(e.target.value)}
 className="w-1/2 bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-base font-bold text-slate-900 focus:ring-2 focus:ring-rose-500 focus:bg-white focus:outline-none text-center min-h-[48px]"
 placeholder="120"
 title="Systolic"
 />
 <span className="text-slate-400 font-bold">/</span>
 <input
 type="number"
 value={numDiastolic}
 onChange={(e) => setNumDiastolic(e.target.value)}
 className="w-1/2 bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-base font-bold text-slate-900 focus:ring-2 focus:ring-rose-500 focus:bg-white focus:outline-none text-center min-h-[48px]"
 placeholder="80"
 title="Diastolic"
 />
 </div>
 </div>
 </div>

 <button
 type="button"
 onClick={handleCustomNumericVitalsSubmit}
 className="w-full py-4 bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white text-sm font-black rounded-2xl shadow-md hover:shadow-lg transition-all flex items-center justify-center space-x-2 min-h-[56px] cursor-pointer"
 >
 <span>Submit Baseline Vitals: {numHeight} cm • {numWeight} kg • {numSystolic}/{numDiastolic} mmHg</span>
 <CheckCircle2 className="w-5 h-5" />
 </button>
 </div>
 )}

 {/* Multilingual Voice Input Card with Accent Selection */}
 <div className={`border-2 rounded-3xl p-5 sm:p-6 space-y-4 ${
 isHighContrast ? 'bg-slate-900 border-slate-700' : 'bg-slate-50/80 border-slate-200'
 }`}>
 
 {/* Accent & Dialect Selector Bar */}
 <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 pb-3">
 <div className="flex items-center space-x-2 text-xs font-bold text-slate-700 ">
 <Languages className="w-4 h-4 text-teal-700" />
 <span>Spoken Language & Regional Accent:</span>
 </div>

 <div className="relative">
 <select
 value={selectedAccent}
 onChange={(e) => setSelectedAccent(e.target.value)}
 aria-label="Spoken Accent & Dialect"
 className="bg-white text-xs font-bold text-slate-900 pl-3 pr-8 py-2 rounded-xl border border-slate-300 hover:border-teal-600 focus:outline-none cursor-pointer shadow-sm min-h-[40px]"
 >
 <option value="en-IN">Indian English (en-IN)</option>
 <option value="hi-IN">Hindi / Hinglish (hi-IN)</option>
 <option value="bn-IN">Bengali / Benglish (bn-IN)</option>
 <option value="ta-IN">Tamil / Tanglish (ta-IN)</option>
 <option value="te-IN">Telugu (te-IN)</option>
 <option value="mr-IN">Marathi (mr-IN)</option>
 <option value="gu-IN">Gujarati (gu-IN)</option>
 </select>
 </div>
 </div>

 {/* Microphone Button & Visualizer */}
 <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
 <div className="flex items-center space-x-4">
 <button
 type="button"
 onClick={handleToggleVoice}
 disabled={isLoading || isProcessingAudio}
 className={`w-20 h-20 rounded-3xl flex items-center justify-center shadow-xl transition-all min-h-[80px] min-w-[80px] cursor-pointer ${
 isRecording
 ? 'bg-rose-600 hover:bg-rose-700 text-white ring-8 ring-rose-200 animate-pulse'
 : 'bg-gradient-to-br from-teal-600 to-teal-800 hover:from-teal-700 hover:to-teal-900 text-white shadow-teal-700/40 active:scale-95'
 }`}
 >
 {isRecording ? <MicOff className="w-10 h-10" /> : <Mic className="w-10 h-10" />}
 </button>

 <div className="space-y-1 text-left">
 <div className="text-base font-extrabold text-slate-900 ">
 {isRecording
 ? 'Listening to your voice... (Tap mic to stop)'
 : isProcessingAudio
 ? 'Analyzing spoken clinical answer...'
 : 'Tap Mic to Speak in Any Indian Language'}
 </div>
 <p className="text-xs text-slate-500 ">
 Auto-normalizes colloquial words (e.g. "jalan/gas", "seene me dard", "bukhar 3 din se").
 </p>
 </div>
 </div>

 {/* Audio Waves Visualizer */}
 {isRecording && (
 <div className="flex items-center justify-center">
 <AudioVisualizer isListening={isRecording} />
 </div>
 )}
 </div>

 {/* Voice Confirmation Preview Box (Guided Mode / Low-Literacy Helper) */}
 {pendingVoiceAnswer && (
 <div className="p-4 bg-teal-50 border-2 border-teal-500 rounded-2xl text-xs space-y-3 animate-in fade-in zoom-in-95">
 <div className="flex items-center justify-between">
 <span className="text-[11px] font-black uppercase text-teal-900 tracking-wider flex items-center gap-1.5">
 <CheckCircle2 className="w-4 h-4 text-teal-600" />
 Recognized Voice Speech:
 </span>
 <button
 type="button"
 onClick={() => playTextToSpeech(pendingVoiceAnswer, currentLang)}
 className="text-teal-800 hover:text-teal-950 font-bold flex items-center gap-1"
 >
 <Volume2 className="w-3.5 h-3.5" />
 <span>Listen</span>
 </button>
 </div>

 <div className="p-3 bg-white rounded-xl border border-teal-200 font-bold text-slate-900 text-sm">
 "{pendingVoiceAnswer}"
 </div>

 <div className="flex items-center gap-2 pt-1">
 <button
 type="button"
 onClick={handleConfirmPendingVoiceAnswer}
 className="flex-1 py-3 bg-teal-700 hover:bg-teal-800 text-white font-black text-xs rounded-xl shadow-md flex items-center justify-center space-x-1.5 min-h-[48px] cursor-pointer"
 >
 <Check className="w-4 h-4" />
 <span>{t.confirmVoice || 'Confirm & Proceed'}</span>
 </button>
 <button
 type="button"
 onClick={handleRetryVoiceAnswer}
 className="px-4 py-3 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold text-xs rounded-xl flex items-center justify-center space-x-1 min-h-[48px] cursor-pointer"
 >
 <RefreshCw className="w-3.5 h-3.5" />
 <span>{t.speakAgain || 'Speak Again'}</span>
 </button>
 </div>
 </div>
 )}

 {/* Live Interim Transcript (when not in pending state) */}
 {!pendingVoiceAnswer && interimTranscript && (
 <div className="p-3 bg-white rounded-xl border border-teal-200 text-xs space-y-1">
 <span className="text-[10px] font-bold uppercase text-teal-800 tracking-wider block">
 Detected Speech:
 </span>
 <p className="text-slate-900 font-medium italic">"{interimTranscript}"</p>
 </div>
 )}

 {normalizedTerms.length > 0 && (
 <div className="flex flex-wrap items-center gap-1.5 pt-1">
 <span className="text-[11px] font-bold text-slate-500">Clinical Concepts:</span>
 {normalizedTerms.map((term, i) => (
 <span key={i} className="px-2.5 py-1 bg-teal-100 border border-teal-300 text-teal-900 text-[11px] font-bold rounded-lg">
 {term}
 </span>
 ))}
 </div>
 )}

 </div>

 {/* Interactive Anatomical Body Map Trigger Bar */}
 <div className={`p-4 rounded-3xl border-2 flex items-center justify-between flex-wrap gap-3 ${
 isHighContrast
 ? 'bg-slate-900 border-teal-400'
 : 'bg-gradient-to-r from-teal-50 to-indigo-50 border-teal-200 shadow-sm'
 }`}>
 <div className="flex items-center space-x-3">
 <div className="w-10 h-10 rounded-2xl bg-teal-600 text-white flex items-center justify-center shadow-md shrink-0">
 <Activity className="w-5 h-5" />
 </div>
 <div>
 <span className="text-sm font-extrabold text-slate-900 block">
 {t.bodyMapTitle || 'Interactive Anatomical Pain Map'}
 </span>
 <span className="text-xs text-slate-500 ">
 {t.bodyMapDesc || 'Touch on body to pinpoint where it hurts and rate pain (1 to 10).'}
 </span>
 </div>
 </div>

 <button
 type="button"
 onClick={() => setShowBodyMapModal(true)}
 className="px-5 py-3 bg-teal-700 hover:bg-teal-800 text-white text-xs sm:text-sm font-black rounded-2xl shadow-md transition-all flex items-center space-x-2 min-h-[48px] cursor-pointer"
 >
 <span>📌 {t.openBodyMap || 'Open Body Map'}</span>
 </button>
 </div>

 {/* Visual Semantic Choice Cards */}
 <div className="space-y-3">
 <div className="flex items-center justify-between">
 <label className="block text-xs font-black uppercase tracking-wider text-slate-500 ">
 {t.touchOptionPrompt || 'Or Tap The Most Relevant Answer Below:'}
 </label>
 <span className="text-xs text-slate-400 font-semibold">{currentQuestion.options.length} options</span>
 </div>

 <div className={`grid gap-3.5 ${isGuided ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2'}`}>
 {currentQuestion.options.map((opt, idx) => {
 const isSkip = isNonDisclosureOption(opt);
 const semanticIcon = getSemanticOptionIcon(opt);
 
 return (
 <button
 type="button"
 key={idx}
 onClick={() => handleChipSelect(opt)}
 disabled={isLoading}
 className={`p-4 sm:p-5 rounded-2xl border-2 text-left transition-all shadow-sm hover:shadow-md active:scale-[0.99] disabled:opacity-50 min-h-[64px] flex items-center justify-between group cursor-pointer ${
 isSkip
 ? isHighContrast
 ? 'border-yellow-500 bg-yellow-950/40 text-yellow-300 hover:bg-yellow-950/80'
 : 'border-amber-300 hover:border-amber-500 bg-amber-50/60 hover:bg-amber-100/80 text-amber-950'
 : isHighContrast
 ? 'border-slate-700 hover:border-yellow-400 bg-slate-900 hover:bg-slate-800 text-white'
 : 'border-slate-200 hover:border-teal-600 bg-white hover:bg-teal-50/80 text-slate-900'
 }`}
 >
 <div className="flex items-center space-x-3.5 pr-2">
 <div className="p-2.5 rounded-xl bg-slate-100 group-hover:bg-teal-100 transition-colors shrink-0">
 {semanticIcon}
 </div>
 <span className={`font-extrabold leading-snug ${isLarge ? 'text-base sm:text-lg' : 'text-sm sm:text-base'}`}>
 {opt}
 </span>
 </div>

 <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all shrink-0 ml-2 ${
 isSkip
 ? 'bg-amber-200 text-amber-900 group-hover:bg-amber-500 group-hover:text-white'
 : 'bg-slate-100 group-hover:bg-teal-600 text-slate-400 group-hover:text-white shadow-xs'
 }`}>
 {isSkip ? '?' : '✓'}
 </span>
 </button>
 );
 })}
 </div>
 </div>

 {/* Text Input Fallback */}
 <form onSubmit={handleTextSubmit} className="flex space-x-2 pt-2">
 <input
 type="text"
 value={textInput}
 onChange={(e) => setTextInput(e.target.value)}
 placeholder="Or type your medical answer here..."
 disabled={isLoading}
 className="flex-1 px-4 py-3.5 border border-slate-300 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-slate-50 focus:bg-white min-h-[48px]"
 />
 <button
 type="submit"
 disabled={!textInput.trim() || isLoading}
 className="px-6 py-3.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-2xl text-sm font-bold flex items-center space-x-1.5 transition-colors min-h-[48px] cursor-pointer"
 >
 <span>Submit</span>
 <CornerDownLeft className="w-4 h-4" />
 </button>
 </form>

 </div>

 {/* Conversation Transcript Footer & Undo Turn */}
 <div className="bg-slate-50 border-t border-slate-200 px-6 py-4 flex flex-wrap items-center justify-between gap-3 text-xs">
 <div className="flex items-center space-x-2 text-slate-600 ">
 <span className="font-bold">Recorded History Turns:</span>
 <span className="px-2.5 py-1 bg-slate-200 rounded-lg font-mono font-bold text-slate-900 ">
 {session.conversationTurns.length} turns
 </span>
 </div>

 <div className="flex items-center space-x-3">
 {session.conversationTurns.length > 0 && (
 <button
 type="button"
 onClick={onUndoAnswer}
 disabled={isLoading}
 className="text-slate-600 hover:text-slate-900 font-bold flex items-center space-x-1.5 min-h-[40px] px-3 rounded-lg hover:bg-slate-200/60 transition-colors"
 >
 <ArrowLeft className="w-4 h-4" />
 <span>Undo Last Answer</span>
 </button>
 )}

 <button
 type="button"
 onClick={onProceedToScan}
 className="px-5 py-2.5 bg-teal-700 hover:bg-teal-800 text-white font-extrabold rounded-xl flex items-center space-x-2 shadow-sm transition-all min-h-[44px] cursor-pointer"
 >
 <span>Next: Documents / Records</span>
 <ArrowRight className="w-4 h-4" />
 </button>
 </div>
 </div>

 </div>

 {/* 3. Non-Disclosure Reconsideration & Reason Modal */}
 {showNonDisclosureModal && (
 <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4">
 <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl border-2 border-amber-400 space-y-5 animate-in fade-in zoom-in duration-150">
 
 {/* Header */}
 <div className="flex items-start justify-between gap-4">
 <div className="flex items-center space-x-3">
 <div className="p-3 bg-amber-100 text-amber-800 rounded-2xl">
 <ShieldCheck className="w-6 h-6" />
 </div>
 <div>
 <span className="text-[10px] font-black uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
 PATIENT PRIVACY & SAFETY
 </span>
 <h3 className="text-lg font-black text-slate-900">
 {vitalsText.alertTitle}
 </h3>
 </div>
 </div>
 <button
 type="button"
 onClick={() => setShowNonDisclosureModal(false)}
 className="text-slate-400 hover:text-slate-700 p-1"
 >
 <X className="w-5 h-5" />
 </button>
 </div>

 {nonDisclosureStage === 'alert' ? (
 /* Stage 1: Clinical Importance Reconsideration Alert */
 <div className="space-y-4">
 <div className="p-4 bg-amber-50/80 rounded-2xl border border-amber-200 text-xs text-amber-950 font-medium leading-relaxed">
 <p>{vitalsText.alertMessage}</p>
 </div>

 <div className="pt-2 flex flex-col sm:flex-row items-center gap-3">
 <button
 type="button"
 onClick={() => setShowNonDisclosureModal(false)}
 className="w-full sm:w-1/2 py-3.5 bg-teal-700 hover:bg-teal-800 text-white text-xs font-bold rounded-xl shadow-md transition-all min-h-[48px]"
 >
 {vitalsText.reconsiderButtonText}
 </button>

 <button
 type="button"
 onClick={() => setNonDisclosureStage('reason')}
 className="w-full sm:w-1/2 py-3.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl border border-slate-300 transition-all min-h-[48px]"
 >
 {vitalsText.confirmSkipButtonText}
 </button>
 </div>
 </div>
 ) : (
 /* Stage 2: Optional Non-Disclosure Reason */
 <div className="space-y-4">
 <div className="space-y-2">
 <label className="text-xs font-bold text-slate-800 block">
 {vitalsText.reasonQuestion}
 </label>
 
 <div className="space-y-2">
 {vitalsText.reasonOptions.map((reasonOpt: string, ri: number) => (
 <label
 key={ri}
 className={`flex items-center space-x-3 p-3.5 rounded-xl border text-xs font-medium cursor-pointer transition-all min-h-[48px] ${
 selectedReason === reasonOpt
 ? 'bg-teal-50 border-teal-600 text-teal-950 font-bold'
 : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
 }`}
 >
 <input
 type="radio"
 name="nonDisclosureReason"
 value={reasonOpt}
 checked={selectedReason === reasonOpt}
 onChange={(e) => setSelectedReason(e.target.value)}
 className="text-teal-600 focus:ring-teal-500 w-4 h-4"
 />
 <span>{reasonOpt}</span>
 </label>
 ))}
 </div>
 </div>

 <div>
 <input
 type="text"
 value={customReasonText}
 onChange={(e) => setCustomReasonText(e.target.value)}
 placeholder="Or type other reason (optional)..."
 className="w-full bg-slate-50 border border-slate-300 rounded-xl p-3 text-xs text-slate-900 focus:ring-2 focus:ring-teal-500 focus:outline-none min-h-[44px]"
 />
 </div>

 <div className="pt-2 flex items-center justify-between gap-3">
 <button
 type="button"
 onClick={() => setNonDisclosureStage('alert')}
 className="py-3 px-4 text-xs font-bold text-slate-600 hover:text-slate-900 min-h-[44px]"
 >
 Back
 </button>
 <button
 type="button"
 onClick={handleConfirmNonDisclosure}
 className="py-3 px-6 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl shadow transition-all min-h-[44px]"
 >
 Proceed without Vitals
 </button>
 </div>
 </div>
 )}

 </div>
 </div>
 )}

 {/* Interactive Anatomical Body Pain Map Modal */}
 {showBodyMapModal && (
 <BodyMapSelector
 initialPain={session.painAssessment}
 onSavePain={handleSaveBodyPain}
 onClose={() => setShowBodyMapModal(false)}
 currentLang={currentLang}
 />
 )}

 </div>
 );
};
