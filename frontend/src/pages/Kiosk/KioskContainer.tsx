import React, { useState, useEffect } from 'react';
import { 
 LanguageCode, PatientRegistration, PatientSession, 
 AdaptiveQuestion, RedFlag, ConnectivityStatus 
} from '../../types';
import { ApiService } from '../../services/api';
import { StepIdentify } from './StepIdentify';
import { StepConverse } from './StepConverse';
import { StepScan } from './StepScan';
import { StepSummarize } from './StepSummarize';
import { translations } from '../../utils/i18n';
import { KioskAccessibilityToolbar, KioskAccessibilitySettings } from '../../components/KioskAccessibilityToolbar';
import { 
 AlertCircle, WifiOff, User, MessageSquare, 
 FileText, CheckCircle2, Volume2 
} from 'lucide-react';

interface KioskContainerProps {
 currentLang: LanguageCode;
 onLanguageChange: (lang: LanguageCode) => void;
 connectivity: ConnectivityStatus;
 onUpdateConnectivity: (status: ConnectivityStatus) => void;
}

import { translateAdaptiveQuestion } from '../../utils/clinicalQuestionsI18n';
import { stopTextToSpeech } from '../../utils/sound';

const INITIAL_QUESTION: AdaptiveQuestion = {
 question: "What is your main health problem or chief complaint today?",
 field: "chief_complaint",
 options: [
 "Severe chest pain / tightness",
 "High fever with chills and cough",
 "Severe stomach ache / acidity",
 "Joint pain & stiffness in knees"
 ],
 done: false,
 progressPercent: 20,
 source: "fallback"
};

const INITIAL_RED_FLAG: RedFlag = {
 triggered: false,
 reason: "",
 action: "",
 urgency: "routine"
};

export const KioskContainer: React.FC<KioskContainerProps> = ({
 currentLang,
 onLanguageChange,
 connectivity,
 onUpdateConnectivity,
}) => {
 const t = translations[currentLang] || translations.en;

 const [currentStep, setCurrentStep] = useState<number>(1);
 const [session, setSession] = useState<PatientSession | null>(null);
 const [isLoading, setIsLoading] = useState<boolean>(false);
 const [isConfirmed, setIsConfirmed] = useState<boolean>(false);
 const [errorMessage, setErrorMessage] = useState<string | null>(null);

 // Kiosk Accessibility & Low-Literacy Settings State
 const [accessibilitySettings, setAccessibilitySettings] = useState<KioskAccessibilitySettings>({
 guidedMode: true,
 assistedMode: false,
 readAloud: true,
 largeText: false,
 highContrast: false,
 slowSpeech: false,
 });

 // Active Adaptive Question (initialized in active language)
 const [currentQuestion, setCurrentQuestion] = useState<AdaptiveQuestion>(() =>
 translateAdaptiveQuestion(INITIAL_QUESTION, currentLang)
 );
 const [redFlag, setRedFlag] = useState<RedFlag>(INITIAL_RED_FLAG);

 // When current language changes mid-flow, immediately translate the active question into the selected language
 useEffect(() => {
 setCurrentQuestion((prev) => translateAdaptiveQuestion(prev, currentLang));
 }, [currentLang]);

 // Check connectivity heartbeat
 useEffect(() => {
 if (session) {
 const activeId = session.sessionId || session.patientId;
 ApiService.updateConnectivity(activeId, connectivity).catch(() => {
 if (connectivity === 'online') {
 onUpdateConnectivity('degraded');
 }
 });
 }
 }, [connectivity, session]);

 // Step 1 Complete -> Initialize Session
 const handleStartSession = async (reg: PatientRegistration) => {
 setIsLoading(true);
 setErrorMessage(null);
 try {
 const newSession = await ApiService.startSession(reg);
 setSession(newSession);
 // Guarantee clean question & red flag state for new patient intake in selected language
 const initialTranslated = translateAdaptiveQuestion(INITIAL_QUESTION, currentLang);
 setCurrentQuestion(initialTranslated);
 setRedFlag(INITIAL_RED_FLAG);
 setIsConfirmed(false);
 setCurrentStep(2);
 } catch (err: any) {
 console.error("Start session failed:", err);
 setErrorMessage("Could not connect to FastAPI server. Please ensure backend is running.");
 onUpdateConnectivity('offline');
 } finally {
 setIsLoading(false);
 }
 };

 // Step 2: Submit Answer -> Get next adaptive question
 const handleAnswerSubmit = async (
 answer: string,
 mode: 'voice' | 'tap',
 ayushMode: boolean,
 field?: string,
 questionText?: string,
 clinicalText?: string
 ) => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 const activeField = field || currentQuestion.field || 'chief_complaint';
 const activeQuestionText = questionText || currentQuestion.question;

 setIsLoading(true);
 setErrorMessage(null);
 try {
 const res = await ApiService.submitAnswer(
 activeId,
 answer,
 mode,
 ayushMode,
 activeField,
 activeQuestionText,
 clinicalText
 );
 setSession(res.session);
 setRedFlag(res.redFlag);
 const translatedAdaptive = translateAdaptiveQuestion(res.adaptive, currentLang);
 setCurrentQuestion(translatedAdaptive);

 if (res.adaptive.done) {
 setTimeout(() => setCurrentStep(3), 1500);
 }
 } catch (err: any) {
 console.error("Submit answer error:", err);
 setErrorMessage("Backend communication interrupted. Staff alert sent.");
 onUpdateConnectivity('degraded');
 } finally {
 setIsLoading(false);
 }
 };

 // Step 2: Undo Answer
 const handleUndoAnswer = async () => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 setIsLoading(true);
 try {
 const res = await ApiService.undoAnswer(activeId);
 setSession(res.session);
 setCurrentQuestion(res.adaptive);
 } catch (err) {
 console.error("Undo error:", err);
 } finally {
 setIsLoading(false);
 }
 };

 // Toggle AYUSH mode live
 const handleToggleAyush = (active: boolean) => {
 if (session) {
 setSession({ ...session, ayushMode: active });
 }
 };

 // Step 3: Upload Real Document
 const handleUploadFile = async (file: File) => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 setIsLoading(true);
 try {
 const doc = await ApiService.uploadDocument(activeId, file);
 setSession({
 ...session,
 priorInvestigations: [...session.priorInvestigations, doc],
 });
 } catch (err) {
 console.error("Upload error:", err);
 setErrorMessage("Document upload failed. Try sample document demo mode.");
 } finally {
 setIsLoading(false);
 }
 };

 // Step 3: Load Sample Demo Document
 const handleLoadSample = async (sampleId: string) => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 setIsLoading(true);
 try {
 const doc = await ApiService.loadSampleDocument(activeId, sampleId);
 setSession({
 ...session,
 priorInvestigations: [...session.priorInvestigations, doc],
 });
 } catch (err) {
 console.error("Sample doc load error:", err);
 } finally {
 setIsLoading(false);
 }
 };

 // Step 3: Correct Extracted Fields
 const handleCorrectDoc = async (docId: string, extracted: any) => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 try {
 const res = await ApiService.correctDocument(activeId, docId, extracted);
 if (res.session) {
 setSession(res.session);
 } else {
 const updatedDocs = session.priorInvestigations.map((d) =>
 d.id === docId ? { ...d, extracted, confidence: 1.0, status: 'success' as const, extractionSource: 'manual_correction' as const } : d
 );
 setSession({ ...session, priorInvestigations: updatedDocs });
 }
 } catch (err) {
 console.error("Correction error:", err);
 }
 };

 // Step 3: Delete Erroneous Document
 const handleDeleteDoc = async (docId: string) => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 setIsLoading(true);
 try {
 const updatedSession = await ApiService.deleteDocument(activeId, docId);
 setSession(updatedSession);
 } catch (err) {
 console.error("Delete document error:", err);
 setErrorMessage("Could not remove document.");
 } finally {
 setIsLoading(false);
 }
 };

 // Step 3: Replace / Re-Scan Document
 const handleReplaceDoc = async (docId: string, file: File) => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 setIsLoading(true);
 try {
 const newDoc = await ApiService.replaceDocument(activeId, docId, file);
 const updatedDocs = session.priorInvestigations.map((d) =>
 d.id === docId ? newDoc : d
 );
 setSession({
 ...session,
 priorInvestigations: updatedDocs,
 });
 } catch (err) {
 console.error("Replace document error:", err);
 setErrorMessage("Could not replace document.");
 } finally {
 setIsLoading(false);
 }
 };

 // Step 4: Confirm Intake Summary
 const handleConfirmSummary = async () => {
 if (!session) return;
 const activeId = session.sessionId || session.patientId;
 setIsLoading(true);
 try {
 await ApiService.confirmSession(activeId);
 setIsConfirmed(true);
 } catch (err) {
 console.error("Confirm error:", err);
 setErrorMessage("Could not route to physician queue.");
 } finally {
 setIsLoading(false);
 }
 };

 const handleRestart = () => {
 setSession(null);
 setCurrentStep(1);
 setIsConfirmed(false);
 setCurrentQuestion(INITIAL_QUESTION);
 setRedFlag(INITIAL_RED_FLAG);
 setErrorMessage(null);
 };

 const isHighContrast = accessibilitySettings.highContrast;

 return (
 <div className={`min-h-[calc(100vh-4rem)] py-6 sm:py-8 px-4 sm:px-6 lg:px-8 transition-colors ${
 isHighContrast ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-900'
 }`}>
 
 {/* Accessibility & Low-Literacy Assistance Toolbar */}
 <div className="max-w-4xl mx-auto">
 <KioskAccessibilityToolbar
 currentLang={currentLang}
 settings={accessibilitySettings}
 onUpdateSettings={(newSettings) =>
 setAccessibilitySettings((prev) => ({ ...prev, ...newSettings }))
 }
 sessionId={session?.sessionId || session?.patientId}
 />
 </div>

 {/* Offline Alert Banner */}
 {connectivity === 'offline' && (
 <div className="max-w-4xl mx-auto mb-6 bg-amber-500 text-slate-950 p-4 rounded-2xl shadow-lg flex items-center justify-between border-2 border-amber-600">
 <div className="flex items-center space-x-3">
 <WifiOff className="w-6 h-6 animate-bounce" />
 <div>
 <span className="font-bold text-sm">Kiosk Connectivity Degraded / Offline</span>
 <p className="text-xs text-slate-900">Hospital Staff Operator has been alerted and can take over manual entry if required.</p>
 </div>
 </div>
 <button
 onClick={() => onUpdateConnectivity('online')}
 className="px-3 py-1.5 bg-slate-900 text-white rounded-lg text-xs font-bold cursor-pointer"
 >
 Simulate Reconnect
 </button>
 </div>
 )}

 {errorMessage && (
 <div className="max-w-3xl mx-auto mb-4 p-3.5 bg-rose-100 border border-rose-300 text-rose-900 rounded-2xl text-xs font-semibold flex items-center space-x-2">
 <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
 <span>{errorMessage}</span>
 </div>
 )}

 {/* Visual 4-Step Progress Indicator (When not on success screen) */}
 {!isConfirmed && (
 <div className="max-w-3xl mx-auto mb-8">
 <div className="grid grid-cols-4 gap-2 mb-3">
 {[
 { step: 1, label: t.step1Identify || 'Patient', icon: User },
 { step: 2, label: t.step2Symptoms || 'Symptoms', icon: MessageSquare },
 { step: 3, label: t.step3Documents || 'Documents', icon: FileText },
 { step: 4, label: t.step4Confirm || 'Confirm', icon: CheckCircle2 },
 ].map(({ step, label, icon: Icon }) => {
 const isPast = currentStep > step;
 const isCurrent = currentStep === step;
 return (
 <div
 key={step}
 className={`p-2.5 sm:p-3 rounded-2xl border-2 flex items-center justify-center space-x-2 transition-all min-h-[48px] ${
 isCurrent
 ? 'bg-teal-700 text-white border-teal-700 shadow-md ring-2 ring-teal-500/30 font-black'
 : isPast
 ? 'bg-teal-50 text-teal-900 border-teal-300 font-bold'
 : isHighContrast
 ? 'bg-slate-900 text-slate-500 border-slate-800'
 : 'bg-white text-slate-400 border-slate-200'
 }`}
 >
 <Icon className={`w-4 h-4 shrink-0 ${
 isCurrent ? 'text-white' : isPast ? 'text-teal-700 ' : 'text-slate-400'
 }`} />
 <span className="text-xs truncate hidden sm:inline">{step}. {label}</span>
 <span className="text-xs font-bold sm:hidden">{step}</span>
 </div>
 );
 })}
 </div>
 <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
 <div
 className="bg-teal-600 h-full rounded-full transition-all duration-300"
 style={{ width: `${(currentStep / 4) * 100}%` }}
 />
 </div>
 </div>
 )}

 {/* Step Renderers with Accessibility Settings Prop */}
 {currentStep === 1 && (
 <StepIdentify
 currentLang={currentLang}
 onLanguageChange={onLanguageChange}
 onComplete={handleStartSession}
 isLoading={isLoading}
 accessibilitySettings={accessibilitySettings}
 />
 )}

 {currentStep === 2 && session && (
 <StepConverse
 session={session}
 currentLang={currentLang}
 onLanguageChange={onLanguageChange}
 currentQuestion={currentQuestion}
 redFlag={redFlag}
 onAnswerSubmit={handleAnswerSubmit}
 onUndoAnswer={handleUndoAnswer}
 onProceedToScan={() => setCurrentStep(3)}
 isLoading={isLoading}
 onToggleAyush={handleToggleAyush}
 accessibilitySettings={accessibilitySettings}
 />
 )}

 {currentStep === 3 && session && (
 <StepScan
 session={session}
 currentLang={currentLang}
 onUploadFile={handleUploadFile}
 onLoadSample={handleLoadSample}
 onCorrectDoc={handleCorrectDoc}
 onDeleteDoc={handleDeleteDoc}
 onReplaceDoc={handleReplaceDoc}
 onProceedToSummary={() => setCurrentStep(4)}
 onBackToConverse={() => setCurrentStep(2)}
 isLoading={isLoading}
 accessibilitySettings={accessibilitySettings}
 />
 )}

 {currentStep === 4 && session && (
 <StepSummarize
 session={session}
 currentLang={currentLang}
 onConfirm={handleConfirmSummary}
 onBackToScan={() => setCurrentStep(3)}
 onRestart={handleRestart}
 isLoading={isLoading}
 isConfirmed={isConfirmed}
 accessibilitySettings={accessibilitySettings}
 />
 )}

 </div>
 );
};
