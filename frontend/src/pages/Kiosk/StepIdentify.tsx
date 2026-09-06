import React, { useState, useEffect } from 'react';
import { 
  Globe, Volume2, ShieldCheck, User, UserCheck, Sparkles, 
  CheckCircle2, ArrowRight, HeartPulse, Stethoscope, Droplets, Leaf,
  QrCode, Camera, Plus, Minus, Check, X, ShieldAlert, AlertCircle
} from 'lucide-react';
import { LanguageCode, PatientRegistration, ConsentDetails } from '../../types';
import { translations } from '../../utils/i18n';
import { playConsentAudio, playTextToSpeech, stopTextToSpeech } from '../../utils/sound';
import { KioskAccessibilitySettings } from '../../components/KioskAccessibilityToolbar';

interface StepIdentifyProps {
  currentLang: LanguageCode;
  onLanguageChange: (lang: LanguageCode) => void;
  onComplete: (data: PatientRegistration) => void;
  isLoading: boolean;
  accessibilitySettings?: KioskAccessibilitySettings;
}

export const StepIdentify: React.FC<StepIdentifyProps> = ({
  currentLang,
  onLanguageChange,
  onComplete,
  isLoading,
  accessibilitySettings,
}) => {
  const t = translations[currentLang] || translations.en;

  const [hasAbha, setHasAbha] = useState<boolean>(true);
  const [abhaId, setAbhaId] = useState<string>('91-4521-8890-1204');
  const [fullName, setFullName] = useState<string>('Ramesh Chandra Sharma');
  const [age, setAge] = useState<number>(52);
  const [gender, setGender] = useState<'Male' | 'Female' | 'Other'>('Male');
  const [medicalSystem, setMedicalSystem] = useState<'allopathy' | 'ayurveda' | 'homeopathy'>('allopathy');

  const [showQrModal, setShowQrModal] = useState<boolean>(false);
  const [isScanningQr, setIsScanningQr] = useState<boolean>(false);

  const [consent, setConsent] = useState<ConsentDetails>({
    recordVoice: true,
    storeDocuments: true,
    shareHospital: true,
  });

  const languages: { code: LanguageCode; label: string; native: string }[] = [
    { code: 'en', label: 'English', native: 'English' },
    { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
    { code: 'bn', label: 'Bengali', native: 'বাংলা' },
    { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
    { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  ];

  // Read aloud on mount if readAloud is enabled
  useEffect(() => {
    return () => { stopTextToSpeech(); };
  }, []);

  useEffect(() => {
    if (accessibilitySettings?.readAloud) {
      const prompt = `${t.identifyTitle}. ${t.selectLanguage}.`;
      const rate = accessibilitySettings.slowSpeech ? 0.75 : 0.95;
      playTextToSpeech(prompt, currentLang, rate);
    }
  }, [currentLang]);

  const handleSimulateQrScan = () => {
    setIsScanningQr(true);
    setTimeout(() => {
      setAbhaId('91-8842-1093-5512');
      setFullName('Sunita Rani Devi');
      setAge(48);
      setGender('Female');
      setIsScanningQr(false);
      setShowQrModal(false);
      
      const successMsg = currentLang === 'hi' 
        ? 'आभा कार्ड सफलतापूर्वक स्कैन हो गया।' 
        : 'ABHA Card scanned successfully.';
      playTextToSpeech(successMsg, currentLang, accessibilitySettings?.slowSpeech ? 0.75 : 0.95);
    }, 1500);
  };

  const handleAgeAdjust = (delta: number) => {
    setAge((prev) => Math.max(1, Math.min(120, prev + delta)));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) return;
    stopTextToSpeech();

    onComplete({
      abhaId: hasAbha ? abhaId : undefined,
      fullName,
      age: Number(age) || 30,
      gender,
      language: currentLang,
      ayushMode: medicalSystem === 'ayurveda',
      homeopathyMode: medicalSystem === 'homeopathy',
      medicalSystem,
      consent,
    });
  };

  const isLarge = Boolean(accessibilitySettings?.largeText);
  const isHighContrast = Boolean(accessibilitySettings?.highContrast);

  return (
    <div className={`max-w-3xl mx-auto rounded-3xl shadow-xl border overflow-hidden transition-all ${
      isHighContrast 
        ? 'bg-slate-950 border-yellow-400 text-white' 
        : 'bg-white border-slate-200 text-slate-900'
    }`}>
      
      {/* Header Banner */}
      <div className={`p-6 sm:p-8 ${
        isHighContrast 
          ? 'bg-slate-900 border-b-2 border-yellow-400 text-yellow-300' 
          : 'bg-gradient-to-r from-teal-700 to-teal-900 text-white'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs font-black uppercase tracking-wider mb-2 text-teal-200">
            <Sparkles className="w-4 h-4 text-amber-300" />
            <span>Step 1 of 4 • {t.step1Identify || 'Patient Identification'}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              const msg = `${t.identifyTitle}. Please choose language and register.`;
              playTextToSpeech(msg, currentLang, accessibilitySettings?.slowSpeech ? 0.75 : 0.95);
            }}
            className="p-2.5 rounded-xl bg-white/20 hover:bg-white/30 text-white transition-colors cursor-pointer"
            title="Read screen aloud"
          >
            <Volume2 className="w-5 h-5" />
          </button>
        </div>
        <h2 className={`font-black tracking-tight ${isLarge ? 'text-3xl sm:text-4xl' : 'text-2xl sm:text-3xl'}`}>
          {t.identifyTitle}
        </h2>
        <p className={`text-teal-100 font-medium mt-1 max-w-xl ${isLarge ? 'text-base' : 'text-sm'}`}>
          Quick intake to prepare your clinical file for the doctor. Select your language, clinical system, and details below.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="p-6 sm:p-8 space-y-8">
        
        {/* 1. Language Selection Pills */}
        <div className="space-y-3">
          <label className={`block font-black flex items-center justify-between ${
            isHighContrast ? 'text-yellow-300' : 'text-slate-950'
          } ${isLarge ? 'text-lg' : 'text-base'}`}>
            <span className="flex items-center space-x-2">
              <Globe className="w-5 h-5 text-teal-700" />
              <span>{t.selectLanguage}</span>
            </span>
            <span className="text-xs font-bold text-slate-500">5 Indian Languages</span>
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {languages.map((lang) => (
              <button
                type="button"
                key={lang.code}
                onClick={() => onLanguageChange(lang.code)}
                className={`py-3.5 px-3 rounded-2xl border-2 text-center transition-all min-h-[58px] cursor-pointer flex flex-col items-center justify-center ${
                  currentLang === lang.code
                    ? isHighContrast
                      ? 'border-yellow-400 bg-yellow-400 text-slate-950 font-black shadow-md ring-2 ring-yellow-300'
                      : 'border-teal-700 bg-teal-50 text-teal-950 font-black shadow-md ring-2 ring-teal-500/40'
                    : isHighContrast
                    ? 'border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-500'
                    : 'border-slate-300 hover:border-teal-500 bg-slate-50 hover:bg-teal-50/40 text-slate-800'
                }`}
              >
                <div className={`font-black ${isLarge ? 'text-lg' : 'text-sm sm:text-base'}`}>{lang.native}</div>
                <div className="text-xs font-bold opacity-80">{lang.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* 2. System of Medicine Selector (Allopathy / Ayurveda / Homeopathy) */}
        <div className="space-y-3">
          <label className={`block font-black flex items-center justify-between ${
            isHighContrast ? 'text-yellow-300' : 'text-slate-950'
          } ${isLarge ? 'text-lg' : 'text-base'}`}>
            <span className="flex items-center space-x-2">
              <HeartPulse className="w-5 h-5 text-teal-700" />
              <span>Select System of Medicine (OPD Track)</span>
            </span>
            <span className="text-xs font-bold text-slate-500">AYUSH &amp; Modern Medicine</span>
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            
            {/* 1. Allopathy Card */}
            <button
              type="button"
              onClick={() => setMedicalSystem('allopathy')}
              className={`p-4 sm:p-5 rounded-2xl border-2 text-left transition-all cursor-pointer flex flex-col justify-between min-h-[120px] ${
                medicalSystem === 'allopathy'
                  ? isHighContrast
                    ? 'border-yellow-400 bg-yellow-400/20 text-yellow-300 shadow-md ring-2 ring-yellow-400'
                    : 'border-teal-600 bg-teal-50 text-teal-950 shadow-md ring-2 ring-teal-500/30'
                  : isHighContrast
                  ? 'border-slate-700 bg-slate-900 text-slate-300'
                  : 'border-slate-300 hover:border-teal-500 bg-white hover:bg-teal-50/40 text-slate-900 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="p-2.5 rounded-xl bg-teal-100 text-teal-900 shadow-xs">
                  <Stethoscope className="w-6 h-6 text-teal-800" />
                </div>
                {medicalSystem === 'allopathy' && (
                  <CheckCircle2 className="w-5 h-5 text-teal-700" />
                )}
              </div>
              <div className="space-y-1">
                <h4 className="font-black text-base text-slate-950">Modern Allopathy</h4>
                <p className="text-xs text-slate-700 font-semibold leading-snug">
                  MBBS/MD Specialist OPD • SOCRATES triage &amp; evidence-based care.
                </p>
              </div>
            </button>

            {/* 2. Ayurveda Card */}
            <button
              type="button"
              onClick={() => setMedicalSystem('ayurveda')}
              className={`p-4 sm:p-5 rounded-2xl border-2 text-left transition-all cursor-pointer flex flex-col justify-between min-h-[120px] ${
                medicalSystem === 'ayurveda'
                  ? isHighContrast
                    ? 'border-yellow-400 bg-yellow-400/20 text-yellow-300 shadow-md ring-2 ring-yellow-400'
                    : 'border-amber-600 bg-amber-50 text-amber-950 shadow-md ring-2 ring-amber-500/30'
                  : isHighContrast
                  ? 'border-slate-700 bg-slate-900 text-slate-300'
                  : 'border-slate-300 hover:border-amber-500 bg-white hover:bg-amber-50/40 text-slate-900 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="p-2.5 rounded-xl bg-amber-100 text-amber-900 shadow-xs">
                  <Leaf className="w-6 h-6 text-amber-800" />
                </div>
                {medicalSystem === 'ayurveda' && (
                  <CheckCircle2 className="w-5 h-5 text-amber-700" />
                )}
              </div>
              <div className="space-y-1">
                <h4 className="font-black text-base text-slate-950">AYUSH Ayurveda</h4>
                <p className="text-xs text-slate-700 font-semibold leading-snug">
                  BAMS/MD Ayu • Dashavidha Pariksha, Prakriti, Agni &amp; Doshas.
                </p>
              </div>
            </button>

            {/* 3. Homeopathy Card */}
            <button
              type="button"
              onClick={() => setMedicalSystem('homeopathy')}
              className={`p-4 sm:p-5 rounded-2xl border-2 text-left transition-all cursor-pointer flex flex-col justify-between min-h-[120px] ${
                medicalSystem === 'homeopathy'
                  ? isHighContrast
                    ? 'border-yellow-400 bg-yellow-400/20 text-yellow-300 shadow-md ring-2 ring-yellow-400'
                    : 'border-cyan-600 bg-cyan-50 text-cyan-950 shadow-md ring-2 ring-cyan-500/30'
                  : isHighContrast
                  ? 'border-slate-700 bg-slate-900 text-slate-300'
                  : 'border-slate-300 hover:border-cyan-500 bg-white hover:bg-cyan-50/40 text-slate-900 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="p-2.5 rounded-xl bg-cyan-100 text-cyan-900 shadow-xs">
                  <Droplets className="w-6 h-6 text-cyan-800" />
                </div>
                {medicalSystem === 'homeopathy' && (
                  <CheckCircle2 className="w-5 h-5 text-cyan-700" />
                )}
              </div>
              <div className="space-y-1">
                <h4 className="font-black text-base text-slate-950">AYUSH Homeopathy</h4>
                <p className="text-xs text-slate-700 font-semibold leading-snug">
                  BHMS/MD Hom • Totality, Thermals, Modalities (&lt; &amp; &gt;) &amp; Similimum.
                </p>
              </div>
            </button>

          </div>
        </div>

        {/* 3. ABHA Mode vs New Patient Mode */}
        <div className={`border-2 rounded-3xl p-5 sm:p-7 space-y-6 ${
          isHighContrast ? 'bg-slate-900 border-slate-700' : 'bg-slate-50 border-slate-300 shadow-xs'
        }`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-300 pb-4">
            <span className={`font-black ${isHighContrast ? 'text-white' : 'text-slate-950'} ${isLarge ? 'text-lg' : 'text-base'}`}>
              {t.abhaOrManual}
            </span>
            <div className="inline-flex rounded-xl bg-slate-200 p-1 border border-slate-300">
              <button
                type="button"
                onClick={() => setHasAbha(true)}
                className={`px-4 py-2 text-xs sm:text-sm font-black rounded-lg transition-all cursor-pointer min-h-[42px] ${
                  hasAbha ? 'bg-teal-700 text-white shadow' : 'text-slate-800 hover:text-slate-950'
                }`}
              >
                ABHA ID / Scan QR
              </button>
              <button
                type="button"
                onClick={() => setHasAbha(false)}
                className={`px-4 py-2 text-xs sm:text-sm font-black rounded-lg transition-all cursor-pointer min-h-[42px] ${
                  !hasAbha ? 'bg-teal-700 text-white shadow' : 'text-slate-800 hover:text-slate-950'
                }`}
              >
                New Patient Form
              </button>
            </div>
          </div>

          {hasAbha ? (
            <div className="space-y-2">
              <label className="block text-xs sm:text-sm font-black text-slate-900">
                {t.abhaIdLabel}
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={abhaId}
                  onChange={(e) => setAbhaId(e.target.value)}
                  placeholder={t.abhaPlaceholder}
                  className="flex-1 px-4 py-3.5 border-2 border-slate-300 rounded-xl text-base font-mono font-bold focus:ring-2 focus:ring-teal-500 focus:border-teal-500 focus:outline-none bg-white text-slate-950 min-h-[54px]"
                />
                <button
                  type="button"
                  onClick={() => setShowQrModal(true)}
                  className="px-6 py-3.5 bg-gradient-to-r from-teal-700 to-teal-800 hover:from-teal-800 hover:to-teal-900 text-white font-black text-sm rounded-xl shadow-md transition-all flex items-center justify-center space-x-2 min-h-[54px] cursor-pointer"
                >
                  <QrCode className="w-5 h-5 text-amber-300" />
                  <span>{t.scanAbhaQr || 'Scan ABHA QR'}</span>
                </button>
              </div>
            </div>
          ) : (
            <p className="text-xs sm:text-sm text-slate-700 font-semibold italic">
              No ABHA ID? Fill in your details below to generate a temporary hospital OPD visit token.
            </p>
          )}

          {/* Patient Details: Full Name, Age (with +/- steppers), Gender (Visual Cards) */}
          <div className="space-y-5 pt-2">
            <div>
              <label className="block text-xs sm:text-sm font-black text-slate-900 mb-1.5">
                {t.fullNameLabel} *
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-3.5 border-2 border-slate-300 rounded-xl text-base font-bold focus:ring-2 focus:ring-teal-500 focus:border-teal-500 focus:outline-none bg-white text-slate-950 min-h-[52px]"
              />
            </div>

            {/* Age Stepper & Quick Adjustment Controls */}
            <div className="space-y-2">
              <label className="block text-xs sm:text-sm font-black text-slate-900">
                {t.ageLabel} *
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleAgeAdjust(-5)}
                  className="px-3 py-3 bg-slate-200 hover:bg-slate-300 text-slate-900 font-black rounded-xl text-xs min-h-[48px] min-w-[48px] transition-colors border border-slate-300 cursor-pointer"
                  title="Minus 5 years"
                >
                  -5
                </button>
                <button
                  type="button"
                  onClick={() => handleAgeAdjust(-1)}
                  className="px-3 py-3 bg-slate-200 hover:bg-slate-300 text-slate-900 font-black rounded-xl text-sm min-h-[48px] min-w-[48px] flex items-center justify-center transition-colors border border-slate-300 cursor-pointer"
                  title="Minus 1 year"
                >
                  <Minus className="w-5 h-5 stroke-[3]" />
                </button>

                <input
                  type="number"
                  required
                  min={1}
                  max={120}
                  value={age}
                  onChange={(e) => setAge(parseInt(e.target.value) || 0)}
                  className="w-24 text-center py-3 border-2 border-slate-300 rounded-xl text-xl font-black focus:ring-2 focus:ring-teal-500 focus:outline-none bg-white text-slate-950 min-h-[48px]"
                />

                <button
                  type="button"
                  onClick={() => handleAgeAdjust(1)}
                  className="px-3 py-3 bg-slate-200 hover:bg-slate-300 text-slate-900 font-black rounded-xl text-sm min-h-[48px] min-w-[48px] flex items-center justify-center transition-colors border border-slate-300 cursor-pointer"
                  title="Plus 1 year"
                >
                  <Plus className="w-5 h-5 stroke-[3]" />
                </button>
                <button
                  type="button"
                  onClick={() => handleAgeAdjust(5)}
                  className="px-3 py-3 bg-slate-200 hover:bg-slate-300 text-slate-900 font-black rounded-xl text-xs min-h-[48px] min-w-[48px] transition-colors border border-slate-300 cursor-pointer"
                  title="Plus 5 years"
                >
                  +5
                </button>
              </div>
            </div>

            {/* Visual Touch Gender Selection Cards */}
            <div className="space-y-2">
              <label className="block text-xs sm:text-sm font-black text-slate-900">
                {t.genderLabel} *
              </label>
              <div className="grid grid-cols-3 gap-3">
                
                {/* Male Card */}
                <button
                  type="button"
                  onClick={() => setGender('Male')}
                  className={`p-3.5 sm:p-4 rounded-2xl border-2 text-center transition-all cursor-pointer min-h-[58px] flex items-center justify-center space-x-2 ${
                    gender === 'Male'
                      ? 'border-teal-700 bg-teal-50 text-teal-950 font-black shadow-md ring-2 ring-teal-500/40'
                      : 'border-slate-300 hover:border-slate-400 bg-white text-slate-800'
                  }`}
                >
                  <User className="w-5 h-5 text-teal-700 shrink-0" />
                  <span className="text-sm sm:text-base font-black">{t.male}</span>
                  {gender === 'Male' && <Check className="w-4 h-4 text-teal-700" />}
                </button>

                {/* Female Card */}
                <button
                  type="button"
                  onClick={() => setGender('Female')}
                  className={`p-3.5 sm:p-4 rounded-2xl border-2 text-center transition-all cursor-pointer min-h-[58px] flex items-center justify-center space-x-2 ${
                    gender === 'Female'
                      ? 'border-teal-700 bg-teal-50 text-teal-950 font-black shadow-md ring-2 ring-teal-500/40'
                      : 'border-slate-300 hover:border-slate-400 bg-white text-slate-800'
                  }`}
                >
                  <UserCheck className="w-5 h-5 text-pink-600 shrink-0" />
                  <span className="text-sm sm:text-base font-black">{t.female}</span>
                  {gender === 'Female' && <Check className="w-4 h-4 text-teal-700" />}
                </button>

                {/* Other Card */}
                <button
                  type="button"
                  onClick={() => setGender('Other')}
                  className={`p-3.5 sm:p-4 rounded-2xl border-2 text-center transition-all cursor-pointer min-h-[58px] flex items-center justify-center space-x-2 ${
                    gender === 'Other'
                      ? 'border-teal-700 bg-teal-50 text-teal-950 font-black shadow-md ring-2 ring-teal-500/40'
                      : 'border-slate-300 hover:border-slate-400 bg-white text-slate-800'
                  }`}
                >
                  <Sparkles className="w-5 h-5 text-purple-600 shrink-0" />
                  <span className="text-sm sm:text-base font-black">{t.otherGender}</span>
                  {gender === 'Other' && <Check className="w-4 h-4 text-teal-700" />}
                </button>

              </div>
            </div>

          </div>
        </div>

        {/* 4. Granular Consent Section (DPDP & ABDM Compliant) */}
        <div className={`border-2 rounded-3xl p-5 sm:p-7 space-y-5 ${
          isHighContrast ? 'bg-slate-900 border-slate-700' : 'bg-slate-50 border-slate-300 shadow-xs'
        }`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-300 pb-3">
            <div className="flex items-center space-x-2 font-black text-base text-slate-950">
              <ShieldCheck className="w-6 h-6 text-teal-700" />
              <span>{t.consentTitle}</span>
            </div>
            <button
              type="button"
              onClick={() => playConsentAudio(currentLang, accessibilitySettings?.slowSpeech ? 0.75 : 0.95)}
              className="inline-flex items-center space-x-1.5 px-4 py-2.5 text-xs font-black bg-teal-100 hover:bg-teal-200 text-teal-950 rounded-xl transition-colors min-h-[44px] cursor-pointer border border-teal-300 shadow-xs"
            >
              <Volume2 className="w-4 h-4 text-teal-800" />
              <span>{t.playAudio}</span>
            </button>
          </div>

          <p className="text-xs sm:text-sm text-slate-800 font-semibold leading-relaxed">
            {t.consentDesc}
          </p>

          <div className="space-y-3 pt-1">
            {/* Toggle 1 */}
            <label className={`flex items-center space-x-3.5 p-4 rounded-2xl border-2 transition-all cursor-pointer min-h-[58px] ${
              consent.recordVoice
                ? 'bg-teal-50 border-teal-600 text-teal-950 shadow-xs'
                : 'bg-white border-slate-300 text-slate-900 hover:border-slate-400'
            }`}>
              <input
                type="checkbox"
                checked={consent.recordVoice}
                onChange={(e) => setConsent({ ...consent, recordVoice: e.target.checked })}
                className="w-6 h-6 rounded-lg border-2 border-teal-600 text-teal-600 focus:ring-teal-500 accent-teal-600 cursor-pointer shrink-0"
              />
              <span className="text-sm sm:text-base font-black text-slate-950 leading-snug">
                {t.consentVoice}
              </span>
            </label>

            {/* Toggle 2 */}
            <label className={`flex items-center space-x-3.5 p-4 rounded-2xl border-2 transition-all cursor-pointer min-h-[58px] ${
              consent.storeDocuments
                ? 'bg-teal-50 border-teal-600 text-teal-950 shadow-xs'
                : 'bg-white border-slate-300 text-slate-900 hover:border-slate-400'
            }`}>
              <input
                type="checkbox"
                checked={consent.storeDocuments}
                onChange={(e) => setConsent({ ...consent, storeDocuments: e.target.checked })}
                className="w-6 h-6 rounded-lg border-2 border-teal-600 text-teal-600 focus:ring-teal-500 accent-teal-600 cursor-pointer shrink-0"
              />
              <span className="text-sm sm:text-base font-black text-slate-950 leading-snug">
                {t.consentDocs}
              </span>
            </label>

            {/* Toggle 3 */}
            <label className={`flex items-center space-x-3.5 p-4 rounded-2xl border-2 transition-all cursor-pointer min-h-[58px] ${
              consent.shareHospital
                ? 'bg-teal-50 border-teal-600 text-teal-950 shadow-xs'
                : 'bg-white border-slate-300 text-slate-900 hover:border-slate-400'
            }`}>
              <input
                type="checkbox"
                checked={consent.shareHospital}
                onChange={(e) => setConsent({ ...consent, shareHospital: e.target.checked })}
                className="w-6 h-6 rounded-lg border-2 border-teal-600 text-teal-600 focus:ring-teal-500 accent-teal-600 cursor-pointer shrink-0"
              />
              <span className="text-sm sm:text-base font-black text-slate-950 leading-snug">
                {t.consentShare}
              </span>
            </label>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-gradient-to-r from-teal-700 to-teal-800 hover:from-teal-800 hover:to-teal-900 text-white font-black text-lg sm:text-xl py-4 px-6 rounded-2xl shadow-xl shadow-teal-700/30 transition-all flex items-center justify-center space-x-2 min-h-[64px] cursor-pointer active:scale-[0.99] border border-teal-600"
        >
          {isLoading ? (
            <span>Preparing Kiosk Session...</span>
          ) : (
            <>
              <span>{t.startBtn}</span>
              <ArrowRight className="w-6 h-6 stroke-[3]" />
            </>
          )}
        </button>

      </form>

      {/* ABHA QR Scanner Simulated Modal */}
      {showQrModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white max-w-md w-full rounded-3xl p-6 sm:p-8 text-center space-y-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center space-x-2 font-black text-slate-950 text-base">
                <QrCode className="w-5 h-5 text-teal-700" />
                <span>{t.scanAbhaQr || 'Scan ABHA QR Code'}</span>
              </div>
              <button
                type="button"
                onClick={() => setShowQrModal(false)}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 cursor-pointer"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Simulated Camera Window */}
            <div className="relative w-full aspect-square bg-slate-950 rounded-2xl overflow-hidden border-2 border-dashed border-teal-400 flex flex-col items-center justify-center p-6 space-y-4">
              <div className="w-48 h-48 border-2 border-teal-400 rounded-xl relative flex items-center justify-center">
                <div className="absolute top-0 left-0 w-4 h-4 border-t-4 border-l-4 border-teal-400" />
                <div className="absolute top-0 right-0 w-4 h-4 border-t-4 border-r-4 border-teal-400" />
                <div className="absolute bottom-0 left-0 w-4 h-4 border-b-4 border-l-4 border-teal-400" />
                <div className="absolute bottom-0 right-0 w-4 h-4 border-b-4 border-r-4 border-teal-400" />

                {isScanningQr ? (
                  <div className="space-y-2 text-center text-teal-300">
                    <div className="w-12 h-12 border-4 border-teal-400 border-t-transparent rounded-full animate-spin mx-auto" />
                    <span className="text-xs font-bold">Decoding ABHA QR...</span>
                  </div>
                ) : (
                  <div className="text-center text-slate-400 space-y-2">
                    <Camera className="w-10 h-10 mx-auto text-teal-400 animate-pulse" />
                    <span className="text-xs font-bold block text-slate-200">
                      Hold ABHA Card / Ayushman QR in front of camera
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Demo Scan Trigger */}
            <div className="space-y-2">
              <button
                type="button"
                onClick={handleSimulateQrScan}
                disabled={isScanningQr}
                className="w-full py-3.5 bg-teal-700 hover:bg-teal-800 text-white font-black text-sm rounded-xl shadow-md transition-all flex items-center justify-center space-x-2 min-h-[50px] cursor-pointer"
              >
                <Camera className="w-4 h-4" />
                <span>Simulate Scan ABHA Card (Demo)</span>
              </button>

              <button
                type="button"
                onClick={() => setShowQrModal(false)}
                className="w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-black text-xs rounded-xl transition-colors min-h-[44px] cursor-pointer"
              >
                {t.closeModal || 'Cancel'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
