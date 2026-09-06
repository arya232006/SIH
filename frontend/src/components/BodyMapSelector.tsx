import React, { useState } from 'react';
import { 
 Activity, X, Check, ArrowRight, ShieldAlert, 
 Sparkles, RefreshCw, Zap, Volume2, User, HelpCircle
} from 'lucide-react';
import { PainAssessment, LanguageCode } from '../types';
import { playTextToSpeech } from '../utils/sound';

interface BodyMapSelectorProps {
 initialPain?: PainAssessment;
 onSavePain: (pain: PainAssessment) => void;
 onClose: () => void;
 currentLang?: LanguageCode;
}

export const BodyMapSelector: React.FC<BodyMapSelectorProps> = ({
 initialPain,
 onSavePain,
 onClose,
 currentLang = 'en'
}) => {
 const [viewMode, setViewMode] = useState<'front' | 'back'>('front');
 const [selectedRegion, setSelectedRegion] = useState<string>(initialPain?.anatomicalRegion || 'Lower Back');
 const [side, setSide] = useState<string>(initialPain?.side || 'Bilateral');
 const [vasScore, setVasScore] = useState<number>(initialPain?.painSeverityVAS || 6);
 const [painCharacter, setPainCharacter] = useState<string>(initialPain?.painCharacter || 'Dull / Aching');
 const [radiationPath, setRadiationPath] = useState<string>(initialPain?.radiationPath || 'Radiates down right leg to calf');
 const [aggravatingFactors, setAggravatingFactors] = useState<string>(initialPain?.aggravatingFactors || 'Worse on prolonged standing or bending');

 const anatomicalZones = [
 { id: 'Head / Brain', label: 'Head / Forehead', plainLabel: 'Head & Face', icon: '🧠', category: 'Neuro / Head' },
 { id: 'Neck / Throat', label: 'Neck & Cervical Spine', plainLabel: 'Neck & Throat', icon: '🗣️', category: 'ENT / Spine' },
 { id: 'Chest / Heart', label: 'Chest (Retrosternal / Precordial)', plainLabel: 'Chest & Heart', icon: '❤️', category: 'Cardio / Resp' },
 { id: 'Upper Abdomen', label: 'Upper Abdomen (Epigastrium)', plainLabel: 'Upper Stomach', icon: '🔥', category: 'Gastro' },
 { id: 'Lower Abdomen', label: 'Lower Abdomen / Pelvis', plainLabel: 'Lower Belly / Bladder', icon: '💧', category: 'Gastro / Renal' },
 { id: 'Upper Back', label: 'Upper Back / Thoracic Spine', plainLabel: 'Upper Back & Ribs', icon: '🦴', category: 'Musculoskeletal' },
 { id: 'Lower Back', label: 'Lower Back (L-S Spine / Lumbar)', plainLabel: 'Lower Back / Waist', icon: '⚡', category: 'Musculoskeletal' },
 { id: 'Shoulders', label: 'Shoulders (Bilateral)', plainLabel: 'Shoulders & Collarbone', icon: '💪', category: 'Joints' },
 { id: 'Arms & Hands', label: 'Arms / Forearms / Wrists', plainLabel: 'Arms & Hands', icon: '✋', category: 'Upper Extremity' },
 { id: 'Hips & Pelvis', label: 'Hips & Sacroiliac Joints', plainLabel: 'Hips & Groin', icon: '🦵', category: 'Joints' },
 { id: 'Knees', label: 'Knees (Both Legs / Joints)', plainLabel: 'Knees & Joints', icon: '🩺', category: 'Lower Extremity' },
 { id: 'Legs & Calves', label: 'Legs / Calves / Shins', plainLabel: 'Legs & Calves', icon: '🦵', category: 'Lower Extremity' },
 { id: 'Feet & Ankles', label: 'Ankles & Plantar Feet', plainLabel: 'Feet & Ankles', icon: '🦶', category: 'Lower Extremity' }
 ];

 const characterOptions = [
 { id: 'Dull / Aching', label: 'Dull / Aching', desc: 'Constant ache / sore' },
 { id: 'Sharp / Stabbing', label: 'Sharp / Stabbing', desc: 'Piercing needle-like' },
 { id: 'Burning / Acidic', label: 'Burning / Hot', desc: 'Acidic or fiery heat' },
 { id: 'Throbbing / Pulsatile', label: 'Throbbing / Pounding', desc: 'Beating pulse feel' },
 { id: 'Cramping / Spasmodic', label: 'Cramping / Tight', desc: 'Tight muscle spasm' },
 { id: 'Crushing / Heavy Pressure', label: 'Heavy Pressure', desc: 'Tight heaviness' }
 ];

 const radiationPresets = [
 'None (Localized in one spot)',
 'Radiates down right leg to calf (Sciatica)',
 'Radiates down left leg to foot',
 'Radiates to left shoulder and jaw (Cardiac pattern)',
 'Radiates around ribs to back (Band-like)',
 'Radiates to groin / flank (Renal colic)'
 ];

 const handleSpeakSelection = () => {
 const text = `Selected area: ${side} ${selectedRegion}. Pain level: ${vasScore} out of 10. Character: ${painCharacter}.`;
 playTextToSpeech(text, currentLang);
 };

 const handleSave = () => {
 onSavePain({
 anatomicalRegion: selectedRegion,
 side,
 painSeverityVAS: vasScore,
 painCharacter,
 radiationPath: radiationPath.startsWith('None') ? undefined : radiationPath,
 aggravatingFactors
 });
 onClose();
 };

 const getVasColor = (score: number) => {
 if (score <= 3) return 'from-emerald-500 to-teal-500 text-teal-800 bg-emerald-50 border-emerald-300';
 if (score <= 6) return 'from-amber-500 to-orange-500 text-amber-900 bg-amber-50 border-amber-300';
 return 'from-rose-500 to-red-600 text-rose-900 bg-rose-50 border-rose-300';
 };

 return (
 <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4">
 <div className="bg-white w-full max-w-4xl rounded-3xl shadow-2xl border border-slate-200 overflow-hidden max-h-[94vh] flex flex-col animate-in fade-in zoom-in duration-200">
 
 {/* Header */}
 <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
 <div className="flex items-center space-x-3">
 <div className="w-10 h-10 rounded-2xl bg-teal-600 text-white flex items-center justify-center shadow-md shrink-0">
 <Activity className="w-6 h-6" />
 </div>
 <div>
 <h3 className="text-base sm:text-lg font-black">Where Does It Hurt? (Body Pain Map)</h3>
 <p className="text-xs text-slate-300">Tap your painful body area and choose how severe the pain is (1 to 10).</p>
 </div>
 </div>
 <button 
 onClick={onClose}
 className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
 >
 <X className="w-6 h-6" />
 </button>
 </div>

 {/* Modal Body */}
 <div className="p-4 sm:p-6 overflow-y-auto space-y-6 flex-1">
 
 <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-start">
 
 {/* Left Column: Anatomical Perspective & Visual Map */}
 <div className="md:col-span-5 bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-4 text-center">
 
 {/* Front / Back Toggle */}
 <div className="inline-flex p-1 bg-slate-200 rounded-xl w-full">
 <button
 type="button"
 onClick={() => setViewMode('front')}
 className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all min-h-[44px] ${
 viewMode === 'front' ? 'bg-white text-teal-900 shadow-sm font-extrabold' : 'text-slate-700 hover:text-slate-900'
 }`}
 >
 🧍 Front (Anterior)
 </button>
 <button
 type="button"
 onClick={() => setViewMode('back')}
 className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all min-h-[44px] ${
 viewMode === 'back' ? 'bg-white text-teal-900 shadow-sm font-extrabold' : 'text-slate-700 hover:text-slate-900'
 }`}
 >
 🔙 Back (Posterior)
 </button>
 </div>

 {/* Interactive Visual Zones Grid */}
 <div className="p-3 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-2">
 <div className="flex items-center justify-between text-xs font-bold text-slate-700 pb-1 border-b">
 <span>Tap Body Area:</span>
 <span className="text-[11px] text-teal-700 font-semibold">{viewMode === 'front' ? 'Front Side' : 'Back Side'}</span>
 </div>
 
 <div className="grid grid-cols-2 gap-2">
 {anatomicalZones
 .filter(z => viewMode === 'front' ? !z.id.includes('Back') : z.id.includes('Back') || z.id.includes('Neck') || z.id.includes('Legs') || z.id.includes('Head') || z.id.includes('Shoulders'))
 .map(z => {
 const isSelected = selectedRegion === z.id;
 return (
 <button
 key={z.id}
 type="button"
 onClick={() => setSelectedRegion(z.id)}
 className={`p-3 rounded-xl text-xs font-bold text-left transition-all border min-h-[56px] flex flex-col justify-between cursor-pointer ${
 isSelected
 ? 'bg-teal-700 text-white border-teal-800 shadow-md scale-[1.02] ring-2 ring-teal-500/40'
 : 'bg-slate-50 text-slate-800 border-slate-200 hover:bg-slate-100 hover:border-slate-300'
 }`}
 >
 <div className="flex items-center justify-between w-full">
 <span className="text-sm">{z.icon}</span>
 {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
 </div>
 <div className="truncate font-bold mt-1">{z.plainLabel}</div>
 <div className={`text-[10px] truncate ${isSelected ? 'text-teal-200' : 'text-slate-500'}`}>
 {z.category}
 </div>
 </button>
 );
 })}
 </div>
 </div>

 {/* Side / Laterality Selector */}
 <div className="space-y-1.5 pt-1">
 <span className="text-xs text-slate-600 font-bold block text-left">Which Side?</span>
 <div className="grid grid-cols-4 gap-1.5">
 {['Left', 'Right', 'Bilateral', 'Center'].map(s => (
 <button
 key={s}
 type="button"
 onClick={() => setSide(s === 'Center' ? 'Central' : s)}
 className={`py-2 rounded-xl text-xs font-bold border transition-all min-h-[42px] cursor-pointer ${
 (side === s || (s === 'Center' && side === 'Central'))
 ? 'bg-indigo-700 text-white border-indigo-800 shadow-sm' 
 : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
 }`}
 >
 {s}
 </button>
 ))}
 </div>
 </div>

 </div>

 {/* Right Column: Pain VAS Scale, Character & Radiation */}
 <div className="md:col-span-7 space-y-5">
 
 {/* VAS Pain Scale Slider (1 to 10) */}
 <div className={`p-4 sm:p-5 rounded-2xl border-2 ${getVasColor(vasScore)} space-y-3 shadow-sm`}>
 <div className="flex items-center justify-between">
 <span className="text-xs sm:text-sm font-black uppercase tracking-wider">
 How Bad Is Your Pain? (1 - 10)
 </span>
 <span className="text-2xl font-black font-mono px-3 py-1 bg-white rounded-xl shadow-xs">
 {vasScore} / 10
 </span>
 </div>

 <input
 type="range"
 min="1"
 max="10"
 value={vasScore}
 onChange={(e) => setVasScore(parseInt(e.target.value))}
 className="w-full h-4 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-teal-600 min-h-[32px]"
 />

 <div className="flex justify-between text-xs font-bold pt-1">
 <span className="text-emerald-800">1 - 3 (Mild / Bearable)</span>
 <span className="text-amber-800">4 - 6 (Medium / Hurts)</span>
 <span className="text-rose-700 font-black">7 - 10 (Very Severe)</span>
 </div>
 </div>

 {/* Character of Pain */}
 <div className="space-y-2">
 <label className="text-xs font-bold text-slate-800 block">
 How Does The Pain Feel?
 </label>
 <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
 {characterOptions.map(c => (
 <button
 key={c.id}
 type="button"
 onClick={() => setPainCharacter(c.id)}
 className={`p-3 rounded-xl text-xs font-bold border text-left transition-all min-h-[56px] flex flex-col justify-between cursor-pointer ${
 painCharacter === c.id
 ? 'bg-teal-700 text-white border-teal-800 shadow-sm ring-2 ring-teal-500/30'
 : 'bg-white text-slate-800 border-slate-200 hover:bg-slate-50'
 }`}
 >
 <div className="font-extrabold">{c.label}</div>
 <div className={`text-[10px] ${painCharacter === c.id ? 'text-teal-200' : 'text-slate-500'}`}>
 {c.desc}
 </div>
 </button>
 ))}
 </div>
 </div>

 {/* Radiation Path */}
 <div className="space-y-1.5">
 <label className="text-xs font-bold text-slate-800 block">
 Does Pain Travel or Spread to other parts?
 </label>
 <select
 value={radiationPath}
 onChange={(e) => setRadiationPath(e.target.value)}
 className="w-full p-3 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 font-bold focus:ring-2 focus:ring-teal-500 focus:outline-none min-h-[48px] cursor-pointer"
 >
 {radiationPresets.map(r => (
 <option key={r} value={r}>{r}</option>
 ))}
 </select>
 </div>

 {/* Aggravating / Relieving Notes */}
 <div className="space-y-1.5">
 <label className="text-xs font-bold text-slate-800 block">
 When Does It Hurt More?
 </label>
 <input
 type="text"
 value={aggravatingFactors}
 onChange={(e) => setAggravatingFactors(e.target.value)}
 placeholder="e.g. Worse on walking or bending, better with rest"
 className="w-full p-3 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-teal-500 focus:outline-none min-h-[48px]"
 />
 </div>

 {/* Clinical Summary Preview Box & Audio Readout Button */}
 <div className="p-3.5 bg-slate-900 text-slate-100 rounded-2xl text-xs space-y-2">
 <div className="flex items-center justify-between">
 <div className="text-[10px] uppercase tracking-wider text-teal-400 font-bold">
 Recorded Body Pain Summary:
 </div>
 <button
 type="button"
 onClick={handleSpeakSelection}
 className="p-1.5 bg-teal-700 hover:bg-teal-600 text-white rounded-lg flex items-center space-x-1 text-[11px] font-bold transition-colors cursor-pointer"
 >
 <Volume2 className="w-3.5 h-3.5" />
 <span>Read Aloud</span>
 </button>
 </div>
 <div className="font-bold text-slate-200">
 {side} {selectedRegion} pain • {painCharacter} • Severity {vasScore}/10
 {!radiationPath.startsWith('None') && ` • Spreads: ${radiationPath}`}
 </div>
 </div>

 </div>

 </div>

 </div>

 {/* Footer */}
 <div className="bg-slate-100 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
 <button
 type="button"
 onClick={onClose}
 className="px-5 py-3 text-xs font-bold text-slate-700 hover:text-slate-900 rounded-xl hover:bg-slate-200 transition-colors min-h-[48px] cursor-pointer"
 >
 Cancel
 </button>

 <button
 type="button"
 onClick={handleSave}
 className="px-6 py-3 bg-teal-700 hover:bg-teal-800 text-white text-xs sm:text-sm font-black rounded-xl shadow-md flex items-center space-x-2 transition-all min-h-[48px] cursor-pointer active:scale-95"
 >
 <Check className="w-4 h-4" />
 <span>Apply Pain Details</span>
 </button>
 </div>

 </div>
 </div>
 );
};
