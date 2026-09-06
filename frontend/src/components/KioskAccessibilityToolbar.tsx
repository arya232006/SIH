import React, { useState } from 'react';
import { 
 Volume2, VolumeX, Type, Eye, Users, 
 HelpCircle, BellRing, Sparkles, Check, CheckCircle2,
 AlertTriangle, X, ShieldAlert, HeartHandshake, Gauge
} from 'lucide-react';
import { LanguageCode } from '../types';
import { translations } from '../utils/i18n';
import { playStaffAssistanceAudio, playTextToSpeech } from '../utils/sound';
import { ApiService } from '../services/api';

export interface KioskAccessibilitySettings {
 guidedMode: boolean;
 assistedMode: boolean;
 readAloud: boolean;
 largeText: boolean;
 highContrast: boolean;
 slowSpeech: boolean;
}

interface KioskAccessibilityToolbarProps {
 currentLang: LanguageCode;
 settings: KioskAccessibilitySettings;
 onUpdateSettings: (newSettings: Partial<KioskAccessibilitySettings>) => void;
 sessionId?: string;
}

export const KioskAccessibilityToolbar: React.FC<KioskAccessibilityToolbarProps> = ({
 currentLang,
 settings,
 onUpdateSettings,
 sessionId,
}) => {
 const t = translations[currentLang] || translations.en;

 const [isCallingStaff, setIsCallingStaff] = useState<boolean>(false);
 const [showHelpModal, setShowHelpModal] = useState<boolean>(false);
 const [staffNotified, setStaffNotified] = useState<boolean>(false);

 const handleCallStaff = async () => {
 setIsCallingStaff(true);
 setShowHelpModal(true);
 setStaffNotified(true);
 
 // 1. Play comforting voice assistance in patient language
 const rate = settings.slowSpeech ? 0.75 : 0.95;
 playStaffAssistanceAudio(currentLang, rate);

 // 2. Call backend if session exists
 if (sessionId) {
 try {
 await ApiService.callStaff(sessionId, 'Patient requested physical assistance at Kiosk');
 } catch (e) {
 console.warn('Call staff endpoint notification notice:', e);
 }
 }
 setIsCallingStaff(false);
 };

 return (
 <>
 {/* Top Accessibility & Mode Selection Bar */}
 <div className={`p-3 rounded-2xl mb-6 shadow-sm border transition-all ${
 settings.highContrast 
 ? 'bg-slate-900 border-yellow-400 text-white shadow-md' 
 : 'bg-white border-slate-200 text-slate-800'
 }`}>
 <div className="flex flex-wrap items-center justify-between gap-2.5">
 
 {/* Left: Mode Badges & Toggles */}
 <div className="flex flex-wrap items-center gap-2">
 
 {/* Guided Mode (Easy) Toggle */}
 <button
 type="button"
 onClick={() => onUpdateSettings({ guidedMode: !settings.guidedMode })}
 className={`px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 min-h-[44px] cursor-pointer ${
 settings.guidedMode
 ? 'bg-teal-700 text-white shadow-sm ring-2 ring-teal-500/40'
 : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
 }`}
 >
 <Sparkles className="w-4 h-4 text-amber-300" />
 <span>{settings.guidedMode ? t.guidedMode : t.normalMode}</span>
 {settings.guidedMode && <Check className="w-3.5 h-3.5 text-white ml-0.5" />}
 </button>

 {/* Assisted Mode (Caregiver / Family) Toggle */}
 <button
 type="button"
 onClick={() => onUpdateSettings({ assistedMode: !settings.assistedMode })}
 className={`px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 min-h-[44px] cursor-pointer ${
 settings.assistedMode
 ? 'bg-indigo-700 text-white shadow-sm ring-2 ring-indigo-500/40'
 : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
 }`}
 >
 <Users className="w-4 h-4" />
 <span>{t.assistedMode}</span>
 {settings.assistedMode && <Check className="w-3.5 h-3.5 text-white ml-0.5" />}
 </button>

 {/* Read Aloud (Auto-TTS) Toggle */}
 <button
 type="button"
 onClick={() => onUpdateSettings({ readAloud: !settings.readAloud })}
 className={`px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 min-h-[44px] cursor-pointer ${
 settings.readAloud
 ? 'bg-blue-600 text-white shadow-sm ring-2 ring-blue-400/40'
 : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
 }`}
 >
 <Volume2 className="w-4 h-4" />
 <span>{t.readAloud}</span>
 <span className={`w-2 h-2 rounded-full ${settings.readAloud ? 'bg-emerald-300 animate-pulse' : 'bg-slate-300'}`} />
 </button>

 {/* Large Text Toggle */}
 <button
 type="button"
 onClick={() => onUpdateSettings({ largeText: !settings.largeText })}
 className={`px-2.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1 min-h-[44px] cursor-pointer ${
 settings.largeText
 ? 'bg-emerald-700 text-white ring-2 ring-emerald-400'
 : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
 }`}
 >
 <Type className="w-4 h-4" />
 <span>{t.largeText}</span>
 </button>

 {/* High Contrast Toggle */}
 <button
 type="button"
 onClick={() => onUpdateSettings({ highContrast: !settings.highContrast })}
 className={`px-2.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1 min-h-[44px] cursor-pointer ${
 settings.highContrast
 ? 'bg-yellow-400 text-slate-950 font-black ring-2 ring-yellow-300'
 : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
 }`}
 >
 <Eye className="w-4 h-4" />
 <span>{t.highContrast}</span>
 </button>

 {/* Slow Speech Toggle */}
 <button
 type="button"
 onClick={() => onUpdateSettings({ slowSpeech: !settings.slowSpeech })}
 className={`px-2.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1 min-h-[44px] cursor-pointer ${
 settings.slowSpeech
 ? 'bg-amber-600 text-white ring-2 ring-amber-400'
 : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
 }`}
 >
 <Gauge className="w-4 h-4" />
 <span>{t.slowSpeech}</span>
 </button>
 </div>

 {/* Right: Persistent Need Help? Button */}
 <button
 type="button"
 onClick={handleCallStaff}
 className="px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-slate-950 hover:text-white font-extrabold text-xs sm:text-sm rounded-xl shadow-md transition-all flex items-center space-x-2 min-h-[48px] cursor-pointer border-2 border-amber-300 active:scale-95"
 >
 <BellRing className="w-4 h-4 animate-bounce shrink-0" />
 <span>{t.needHelpBtn}</span>
 </button>

 </div>

 {/* Caregiver helper banner if Assisted Mode is enabled */}
 {settings.assistedMode && (
 <div className="mt-2.5 p-2.5 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center space-x-2 text-indigo-900 text-xs">
 <HeartHandshake className="w-4 h-4 text-indigo-700 shrink-0" />
 <span className="font-semibold">{t.assistedModeHelper}</span>
 </div>
 )}
 </div>

 {/* Staff Assistance Modal */}
 {showHelpModal && (
 <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-4">
 <div className="bg-white max-w-md w-full rounded-3xl p-6 sm:p-8 text-center space-y-5 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
 <div className="w-20 h-20 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-amber-500/20">
 <BellRing className="w-10 h-10 animate-pulse" />
 </div>

 <div className="space-y-2">
 <span className="text-xs font-black uppercase tracking-wider bg-amber-100 text-amber-900 px-3 py-1 rounded-full border border-amber-300">
 STAFF ASSISTANCE REQUESTED
 </span>
 <h3 className="text-xl sm:text-2xl font-black text-slate-900">
 {t.helpRequested}
 </h3>
 <p className="text-slate-600 text-xs sm:text-sm leading-relaxed">
 Please remain at the kiosk. A triage nurse or floor operator is on the way to help you complete your intake.
 </p>
 </div>

 <div className="pt-2">
 <button
 type="button"
 onClick={() => setShowHelpModal(false)}
 className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-xl transition-all cursor-pointer min-h-[48px]"
 >
 {t.closeModal}
 </button>
 </div>
 </div>
 </div>
 )}
 </>
 );
};
