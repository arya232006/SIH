import React, { useState, useEffect } from 'react';
import { 
 Volume2, Mic, MicOff, Send, HelpCircle, CheckCircle2, 
 AlertTriangle, ShieldCheck, Sparkles, ArrowRight, UserCheck, Stethoscope
} from 'lucide-react';
import { 
 ExtractedMedicationItem, MedicationClarificationPlan, 
 MedicationClarificationAnswerResponse, LanguageCode 
} from '../types';

interface MedicationClarifierProps {
 sessionId: string;
 documentId: string;
 documentImageUrl?: string;
 medicationItems?: ExtractedMedicationItem[];
 currentLang: LanguageCode;
 onMedicationsUpdated?: (updatedMeds: ExtractedMedicationItem[]) => void;
 onStatusChange?: (status: 'completed' | 'escalated_to_staff') => void;
}

export const MedicationClarifier: React.FC<MedicationClarifierProps> = ({
 sessionId,
 documentId,
 documentImageUrl,
 medicationItems = [],
 currentLang,
 onMedicationsUpdated,
 onStatusChange
}) => {
 const [plan, setPlan] = useState<MedicationClarificationPlan | null>(null);
 const [isLoading, setIsLoading] = useState<boolean>(false);
 const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
 const [isListening, setIsListening] = useState<boolean>(false);
 const [textAnswer, setTextAnswer] = useState<string>('');
 const [recentResolved, setRecentResolved] = useState<string[]>([]);
 const [allMeds, setAllMeds] = useState<ExtractedMedicationItem[]>(medicationItems);

 // Fetch or re-evaluate clarification plan
 const fetchPlan = async () => {
 try {
 setIsLoading(true);
 const res = await fetch(
 `http://127.0.0.1:8000/api/session/${sessionId}/document/${documentId}/medications/clarify/plan?language=${currentLang}`,
 { method: 'POST' }
 );
 if (res.ok) {
 const data: MedicationClarificationPlan = await res.json();
 setPlan(data);
 if (data.escalateToStaff && onStatusChange) {
 onStatusChange('escalated_to_staff');
 } else if (!data.shouldAskPatient && onStatusChange) {
 onStatusChange('completed');
 }
 }
 } catch (err) {
 console.error('[MedicationClarifier] fetchPlan error:', err);
 } finally {
 setIsLoading(false);
 }
 };

 useEffect(() => {
 fetchPlan();
 }, [sessionId, documentId, currentLang]);

 // Read aloud the question via Web Speech API (TTS)
 const speakQuestion = (text: string) => {
 if ('speechSynthesis' in window) {
 window.speechSynthesis.cancel();
 const utterance = new SpeechSynthesisUtterance(text);
 const langMap: Record<string, string> = {
 hi: 'hi-IN',
 bn: 'bn-IN',
 ta: 'ta-IN',
 te: 'te-IN',
 en: 'en-IN'
 };
 utterance.lang = langMap[currentLang] || 'en-IN';
 utterance.rate = 0.9;
 window.speechSynthesis.speak(utterance);
 }
 };

 // Web Speech API Microphone Recording (STT)
 const handleToggleVoice = () => {
 const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
 if (!SpeechRecognition) {
 alert('Speech recognition is not supported in this browser. Please type or tap the options below.');
 return;
 }

 if (isListening) {
 setIsListening(false);
 return;
 }

 try {
 const recognition = new SpeechRecognition();
 const langMap: Record<string, string> = {
 hi: 'hi-IN',
 bn: 'bn-IN',
 ta: 'ta-IN',
 te: 'te-IN',
 en: 'en-IN'
 };
 recognition.lang = langMap[currentLang] || 'en-IN';
 recognition.interimResults = false;
 recognition.maxAlternatives = 1;

 recognition.onstart = () => setIsListening(true);
 recognition.onend = () => setIsListening(false);
 recognition.onerror = () => setIsListening(false);

 recognition.onresult = (event: any) => {
 const transcript = event.results[0][0].transcript;
 if (transcript) {
 setTextAnswer(transcript);
 handleAnswerSubmit(transcript, 'voice');
 }
 };

 recognition.start();
 } catch (err) {
 console.error('[SpeechRecognition error]:', err);
 setIsListening(false);
 }
 };

 // Submit patient answer
 const handleAnswerSubmit = async (answer: string, mode: 'voice' | 'tap' | 'type' | 'dont_know') => {
 if (!answer.trim() || !plan?.targetMedicationId) return;
 try {
 setIsSubmitting(true);
 const res = await fetch(
 `http://127.0.0.1:8000/api/session/${sessionId}/document/${documentId}/medications/clarify/answer`,
 {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({
 docId: documentId,
 medicationId: plan.targetMedicationId,
 answer: answer,
 mode: mode,
 language: currentLang
 })
 }
 );

 if (res.ok) {
 const data: MedicationClarificationAnswerResponse = await res.json();
 setRecentResolved(data.resolvedFields);
 setAllMeds(data.allMedications);
 setPlan(data.nextPlan);
 setTextAnswer('');
 if (onMedicationsUpdated) {
 onMedicationsUpdated(data.allMedications);
 }
 if (data.nextPlan.escalateToStaff && onStatusChange) {
 onStatusChange('escalated_to_staff');
 } else if (!data.nextPlan.shouldAskPatient && onStatusChange) {
 onStatusChange('completed');
 }
 }
 } catch (err) {
 console.error('[MedicationClarifier] submitAnswer error:', err);
 } finally {
 setIsSubmitting(false);
 }
 };

 const handleEscalateManual = async () => {
 try {
 await fetch(`http://127.0.0.1:8000/api/session/${sessionId}/document/${documentId}/medications/escalate`, {
 method: 'POST'
 });
 if (onStatusChange) {
 onStatusChange('escalated_to_staff');
 }
 fetchPlan();
 } catch (e) {
 console.error(e);
 }
 };

 // If loading plan
 if (isLoading && !plan) {
 return (
 <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-center py-6">
 <div className="animate-spin w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full mx-auto mb-2" />
 <p className="text-xs text-slate-600 font-medium">Analyzing prescription handwriting confidence...</p>
 </div>
 );
 }

 // If >2 unclear medications -> Staff Escalation Banner
 if (plan?.escalateToStaff) {
 return (
 <div className="p-5 bg-gradient-to-br from-amber-50 to-orange-50 rounded-2xl border border-amber-300 space-y-3 shadow-sm">
 <div className="flex items-start space-x-3">
 <div className="w-10 h-10 rounded-xl bg-amber-600 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5">
 <ShieldCheck className="w-6 h-6" />
 </div>
 <div className="space-y-1">
 <h4 className="text-sm font-extrabold text-amber-950">
 🛡️ Prescription Escrowed to Hospital Staff Desk
 </h4>
 <p className="text-xs text-amber-900 leading-relaxed">
 {plan.reason || 'Multiple medications on this prescription are handwritten and unreadable. Our hospital pharmacy assistant will verify these medicines during your consultation.'}
 </p>
 <div className="flex items-center space-x-2 pt-1 text-[11px] font-bold text-amber-800">
 <span>Status: Flagged for Staff Review</span> • <span>No extra questions needed</span>
 </div>
 </div>
 </div>
 </div>
 );
 }

 // If 0 unclear medications or completed
 if (plan && !plan.shouldAskPatient) {
 return (
 <div className="p-4 bg-teal-50/80 rounded-2xl border border-teal-300 flex items-center justify-between text-teal-950 shadow-xs">
 <div className="flex items-center space-x-3">
 <div className="w-8 h-8 rounded-full bg-teal-600 text-white flex items-center justify-center shrink-0">
 <CheckCircle2 className="w-5 h-5" />
 </div>
 <div>
 <div className="text-xs font-bold text-teal-950">Prescription Medications Transcribed & Grounded</div>
 <div className="text-[11px] text-teal-800">
 Dosages, schedules, and duration guidelines formatted for physician review.
 </div>
 </div>
 </div>
 <span className="text-[10px] font-bold px-2.5 py-1 bg-teal-200/80 text-teal-900 rounded-full border border-teal-300">
 Ready for OPD Review
 </span>
 </div>
 );
 }

 // If 1-2 unclear medications -> Dynamic Minimal Question Panel
 return (
 <div className="bg-gradient-to-br from-indigo-50/90 via-blue-50/80 to-teal-50/90 rounded-2xl border-2 border-indigo-300 p-5 space-y-4 shadow-md">
 
 {/* Header with Target Medication & Optimization Indicator */}
 <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-200/80 pb-3">
 <div className="flex items-center space-x-2">
 <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-xs">
 <Sparkles className="w-4 h-4" />
 </div>
 <div>
 <h4 className="text-xs font-extrabold uppercase tracking-wider text-indigo-950">
 Dynamic Medication Clarifier • {plan?.targetMedicationName || 'Prescription Item'}
 </h4>
 <span className="text-[11px] text-indigo-800 font-medium">
 Asking only what cannot be clearly read from doctor's handwriting ({plan?.informationNeeded.join(', ')})
 </span>
 </div>
 </div>

 <div className="flex items-center space-x-2">
 <span className="text-[10px] font-bold bg-indigo-200/90 text-indigo-900 px-2.5 py-0.5 rounded-full border border-indigo-300">
 1 of {plan?.unclearMedicationCount || 1} Question
 </span>
 <button
 type="button"
 onClick={handleEscalateManual}
 className="text-[11px] text-slate-500 hover:text-indigo-900 underline font-medium"
 >
 Ask Staff Instead
 </button>
 </div>
 </div>

 {/* The Dynamic Plain-Language Question */}
 <div className="bg-white p-4 rounded-xl border border-indigo-200/90 shadow-xs space-y-3">
 <div className="flex items-start justify-between gap-2">
 <div className="space-y-1">
 <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 block">
 Patient Clarification:
 </span>
 <p className="text-base sm:text-lg font-extrabold text-slate-900 leading-snug">
 {plan?.question}
 </p>
 </div>
 {plan?.question && (
 <button
 type="button"
 onClick={() => speakQuestion(plan.question || '')}
 className="p-2 bg-indigo-100 hover:bg-indigo-200 text-indigo-800 rounded-xl transition-colors shrink-0"
 title="Read Question Aloud"
 >
 <Volume2 className="w-5 h-5" />
 </button>
 )}
 </div>

 {/* Quick Tap Option Buttons */}
 {plan?.options && plan.options.length > 0 && (
 <div className="pt-1">
 <span className="text-[11px] font-bold text-slate-500 block mb-2">
 Quick tap options (or speak/type below):
 </span>
 <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
 {plan.options.map((opt, idx) => (
 <button
 type="button"
 key={idx}
 disabled={isSubmitting}
 onClick={() => handleAnswerSubmit(opt, opt.toLowerCase().includes("don't know") ? 'dont_know' : 'tap')}
 className={`text-left p-3 rounded-xl border text-xs font-semibold transition-all flex items-center justify-between min-h-[44px] ${
 opt.toLowerCase().includes("don't know")
 ? 'border-slate-300 bg-slate-100/90 hover:bg-slate-200 text-slate-700'
 : 'border-indigo-200 bg-indigo-50/50 hover:bg-indigo-600 hover:text-white text-indigo-950 hover:border-indigo-600 shadow-2xs'
 }`}
 >
 <span>{opt}</span>
 <ArrowRight className="w-3.5 h-3.5 opacity-60 shrink-0 ml-1.5" />
 </button>
 ))}
 </div>
 </div>
 )}
 </div>

 {/* Voice & Typing Answer Bar */}
 <div className="flex items-center space-x-2">
 <button
 type="button"
 disabled={isSubmitting}
 onClick={handleToggleVoice}
 className={`px-4 py-3 rounded-xl font-bold text-xs flex items-center space-x-2 transition-all min-h-[46px] shadow-sm shrink-0 ${
 isListening
 ? 'bg-rose-600 text-white animate-pulse'
 : 'bg-indigo-700 hover:bg-indigo-800 text-white'
 }`}
 >
 {isListening ? (
 <>
 <MicOff className="w-4 h-4" />
 <span>Listening... Speak Now</span>
 </>
 ) : (
 <>
 <Mic className="w-4 h-4" />
 <span>Speak Answer</span>
 </>
 )}
 </button>

 <div className="relative flex-1">
 <input
 type="text"
 value={textAnswer}
 onChange={(e) => setTextAnswer(e.target.value)}
 onKeyDown={(e) => {
 if (e.key === 'Enter') handleAnswerSubmit(textAnswer, 'type');
 }}
 placeholder="Or type natural answer (e.g. '1 morning 1 night after food')..."
 className="w-full pl-3 pr-10 py-2.5 text-xs bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-hidden min-h-[46px]"
 />
 <button
 type="button"
 disabled={isSubmitting || !textAnswer.trim()}
 onClick={() => handleAnswerSubmit(textAnswer, 'type')}
 className="absolute right-2 top-2 p-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-30 text-white rounded-lg transition-colors"
 >
 <Send className="w-3.5 h-3.5" />
 </button>
 </div>
 </div>

 {/* Live Recent Resolution Feedback Banner */}
 {recentResolved.length > 0 && (
 <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center space-x-2 text-xs text-emerald-900">
 <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
 <span>
 Successfully extracted and resolved: <strong>{recentResolved.join(', ')}</strong> simultaneously!
 </span>
 </div>
 )}

 </div>
 );
};

