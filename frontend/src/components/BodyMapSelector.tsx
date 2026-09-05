import React, { useState } from 'react';
import { 
  Activity, X, Check, ArrowRight, ShieldAlert, 
  Sparkles, RefreshCw, Zap
} from 'lucide-react';
import { PainAssessment } from '../types';

interface BodyMapSelectorProps {
  initialPain?: PainAssessment;
  onSavePain: (pain: PainAssessment) => void;
  onClose: () => void;
}

export const BodyMapSelector: React.FC<BodyMapSelectorProps> = ({
  initialPain,
  onSavePain,
  onClose
}) => {
  const [viewMode, setViewMode] = useState<'front' | 'back'>('front');
  const [selectedRegion, setSelectedRegion] = useState<string>(initialPain?.anatomicalRegion || 'Lower Back');
  const [side, setSide] = useState<string>(initialPain?.side || 'Bilateral');
  const [vasScore, setVasScore] = useState<number>(initialPain?.painSeverityVAS || 6);
  const [painCharacter, setPainCharacter] = useState<string>(initialPain?.painCharacter || 'Dull / Aching');
  const [radiationPath, setRadiationPath] = useState<string>(initialPain?.radiationPath || 'Radiates down right leg to calf');
  const [aggravatingFactors, setAggravatingFactors] = useState<string>(initialPain?.aggravatingFactors || 'Worse on prolonged standing or bending');

  const anatomicalZones = [
    { id: 'Head / Brain', label: 'Head / Forehead', category: 'Neuro / Head' },
    { id: 'Neck / Throat', label: 'Neck & Cervical Spine', category: 'ENT / Spine' },
    { id: 'Chest / Heart', label: 'Chest (Retrosternal / Precordial)', category: 'Cardio / Resp' },
    { id: 'Upper Abdomen', label: 'Upper Abdomen (Epigastrium)', category: 'Gastro' },
    { id: 'Lower Abdomen', label: 'Lower Abdomen / Pelvis', category: 'Gastro / Renal' },
    { id: 'Upper Back', label: 'Upper Back / Thoracic Spine', category: 'Musculoskeletal' },
    { id: 'Lower Back', label: 'Lower Back (L-S Spine / Lumbar)', category: 'Musculoskeletal' },
    { id: 'Shoulders', label: 'Shoulders (Bilateral)', category: 'Joints' },
    { id: 'Arms & Hands', label: 'Arms / Forearms / Wrists', category: 'Upper Extremity' },
    { id: 'Hips & Pelvis', label: 'Hips & Sacroiliac Joints', category: 'Joints' },
    { id: 'Knees', label: 'Knees (Both Legs / Joints)', category: 'Lower Extremity' },
    { id: 'Legs & Calves', label: 'Legs / Calves / Shins', category: 'Lower Extremity' },
    { id: 'Feet & Ankles', label: 'Ankles & Plantar Feet', category: 'Lower Extremity' }
  ];

  const characterOptions = [
    'Dull / Aching',
    'Sharp / Stabbing',
    'Burning / Acidic',
    'Throbbing / Pulsatile',
    'Cramping / Spasmodic',
    'Crushing / Heavy Pressure'
  ];

  const radiationPresets = [
    'None (Localized)',
    'Radiates down right leg to calf (Sciatica)',
    'Radiates down left leg to foot',
    'Radiates to left shoulder and jaw (Cardiac pattern)',
    'Radiates around ribs to back (Band-like)',
    'Radiates to groin / flank (Renal colic)'
  ];

  const handleSave = () => {
    onSavePain({
      anatomicalRegion: selectedRegion,
      side,
      painSeverityVAS: vasScore,
      painCharacter,
      radiationPath: radiationPath === 'None (Localized)' ? undefined : radiationPath,
      aggravatingFactors
    });
    onClose();
  };

  const getVasColor = (score: number) => {
    if (score <= 3) return 'from-emerald-500 to-teal-500 text-teal-700 bg-teal-50 border-teal-200';
    if (score <= 6) return 'from-amber-500 to-orange-500 text-amber-700 bg-amber-50 border-amber-200';
    return 'from-rose-500 to-red-600 text-rose-700 bg-rose-50 border-rose-200';
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white w-full max-w-4xl rounded-3xl shadow-2xl border border-slate-200 overflow-hidden max-h-[92vh] flex flex-col animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-teal-500 text-white flex items-center justify-center shadow-md">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold">Interactive Anatomical Body Pain Map</h3>
              <p className="text-xs text-slate-400">Touch to pinpoint pain location, VAS severity (1-10), and radiation dermatome.</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
            
            {/* Left Column: Anatomical Perspective & Visual Map */}
            <div className="md:col-span-5 bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-4 text-center">
              
              {/* Front / Back Toggle */}
              <div className="inline-flex p-1 bg-slate-200 rounded-xl">
                <button
                  type="button"
                  onClick={() => setViewMode('front')}
                  className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    viewMode === 'front' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Anterior (Front)
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('back')}
                  className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    viewMode === 'back' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Posterior (Back)
                </button>
              </div>

              {/* Interactive Visual Zones Grid */}
              <div className="p-3 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-2">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                  Select Anatomical Region:
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {anatomicalZones
                    .filter(z => viewMode === 'front' ? !z.id.includes('Back') : z.id.includes('Back') || z.id.includes('Neck') || z.id.includes('Legs') || z.id.includes('Head') || z.id.includes('Shoulders'))
                    .map(z => (
                      <button
                        key={z.id}
                        type="button"
                        onClick={() => setSelectedRegion(z.id)}
                        className={`p-2 rounded-xl text-xs font-bold text-left transition-all border ${
                          selectedRegion === z.id
                            ? 'bg-teal-600 text-white border-teal-700 shadow-xs scale-[1.02]'
                            : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                        }`}
                      >
                        <div className="truncate">{z.label}</div>
                        <div className={`text-[10px] font-normal opacity-80 truncate ${selectedRegion === z.id ? 'text-teal-100' : 'text-slate-500'}`}>
                          {z.category}
                        </div>
                      </button>
                  ))}
                </div>
              </div>

              {/* Side / Laterality Selector */}
              <div className="flex items-center justify-center space-x-2 pt-1">
                <span className="text-xs text-slate-500 font-medium">Laterality:</span>
                {['Left', 'Right', 'Bilateral', 'Central'].map(s => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSide(s)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors ${
                      side === s 
                        ? 'bg-indigo-600 text-white border-indigo-700' 
                        : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>

            </div>

            {/* Right Column: Pain VAS Scale, Character & Radiation */}
            <div className="md:col-span-7 space-y-5">
              
              {/* VAS Pain Scale Slider (1 to 10) */}
              <div className={`p-4 rounded-2xl border ${getVasColor(vasScore)} space-y-3`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider">
                    Visual Analog Scale (VAS Pain Severity)
                  </span>
                  <span className="text-xl font-black font-mono">
                    {vasScore} / 10
                  </span>
                </div>

                <input
                  type="range"
                  min="1"
                  max="10"
                  value={vasScore}
                  onChange={(e) => setVasScore(parseInt(e.target.value))}
                  className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-teal-600"
                />

                <div className="flex justify-between text-[11px] font-semibold text-slate-600">
                  <span>1 - 3 (Mild)</span>
                  <span>4 - 6 (Moderate)</span>
                  <span className="text-rose-700 font-bold">7 - 10 (Severe / Excruciating)</span>
                </div>
              </div>

              {/* Character of Pain */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 block">
                  Character & Sensation of Pain:
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {characterOptions.map(c => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setPainCharacter(c)}
                      className={`p-2 rounded-xl text-xs font-bold border text-center transition-colors ${
                        painCharacter === c
                          ? 'bg-teal-600 text-white border-teal-700 shadow-2xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>

              {/* Radiation Path */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 block">
                  Radiation Path / Referred Pain Dermatome:
                </label>
                <select
                  value={radiationPath}
                  onChange={(e) => setRadiationPath(e.target.value)}
                  className="w-full p-2.5 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 font-medium focus:ring-2 focus:ring-teal-500 focus:outline-none"
                >
                  {radiationPresets.map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>

              {/* Aggravating / Relieving Notes */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700 block">
                  Aggravating / Relieving Factors:
                </label>
                <input
                  type="text"
                  value={aggravatingFactors}
                  onChange={(e) => setAggravatingFactors(e.target.value)}
                  placeholder="e.g. Worse on walking or bending, relieved by rest"
                  className="w-full p-2.5 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                />
              </div>

              {/* Clinical Summary Preview Box */}
              <div className="p-3 bg-slate-900 text-slate-100 rounded-xl text-xs space-y-1">
                <div className="text-[10px] uppercase tracking-wider text-teal-400 font-bold">
                  Mapped Clinical Impression (SOCRATES):
                </div>
                <div className="font-medium text-slate-200">
                  {side} {selectedRegion} pain • {painCharacter} character • VAS {vasScore}/10
                  {radiationPath !== 'None (Localized)' && ` • Radiates: ${radiationPath}`}
                </div>
              </div>

            </div>

          </div>

        </div>

        {/* Footer */}
        <div className="bg-slate-100 px-6 py-3.5 border-t border-slate-200 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-200 transition-colors"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleSave}
            className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl shadow-md flex items-center space-x-2 transition-all"
          >
            <Check className="w-4 h-4" />
            <span>Apply Pain Assessment to History</span>
          </button>
        </div>

      </div>
    </div>
  );
};

