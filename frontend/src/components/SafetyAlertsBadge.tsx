import React, { useState } from 'react';
import { 
  ShieldAlert, AlertTriangle, ShieldCheck, 
  Pill, Sparkles, ChevronDown, ChevronUp, Info, HeartPulse
} from 'lucide-react';
import { SafetyCheckResponse, DrugInteractionAlert } from '../types';

interface SafetyAlertsBadgeProps {
  safetyData: SafetyCheckResponse;
  compact?: boolean;
}

export const SafetyAlertsBadge: React.FC<SafetyAlertsBadgeProps> = ({
  safetyData,
  compact = false
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(!compact);

  const totalAlerts = (safetyData.alerts?.length || 0) + 
                      (safetyData.allergyWarnings?.length || 0) + 
                      (safetyData.contraindications?.length || 0);

  if (totalAlerts === 0) {
    return (
      <div className="p-3 bg-teal-50 border border-teal-200 rounded-2xl flex items-center justify-between text-teal-900 text-xs">
        <div className="flex items-center space-x-2.5">
          <div className="w-6 h-6 rounded-full bg-teal-600 text-white flex items-center justify-center shrink-0">
            <ShieldCheck className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="font-bold">No Active DDI or Herb-Drug Contraindications</span>
            <span className="text-[11px] text-teal-700 block">Verified against CDSCO, NLEM & Integrative Medicine database.</span>
          </div>
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 bg-teal-200/80 text-teal-900 rounded-full">
          Safe Regimen
        </span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden space-y-0">
      
      {/* Alert Header */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className={`p-3.5 flex items-center justify-between cursor-pointer transition-colors ${
          safetyData.hasHighRiskAlerts 
            ? 'bg-rose-50 border-b border-rose-200 text-rose-950' 
            : 'bg-amber-50 border-b border-amber-200 text-amber-950'
        }`}
      >
        <div className="flex items-center space-x-2.5">
          <div className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 ${
            safetyData.hasHighRiskAlerts ? 'bg-rose-600 text-white' : 'bg-amber-500 text-white'
          }`}>
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold flex items-center space-x-2">
              <span>Clinical Safety & Drug Interaction Alerts ({totalAlerts})</span>
              {safetyData.hasHighRiskAlerts && (
                <span className="text-[10px] font-extrabold px-2 py-0.5 bg-rose-600 text-white rounded-full uppercase tracking-wider">
                  High Risk
                </span>
              )}
            </div>
            <div className="text-[11px] opacity-85">
              Identified potential drug-drug, herb-drug, or contraindication risks.
            </div>
          </div>
        </div>

        <button type="button" className="p-1 text-slate-500 hover:text-slate-800">
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expanded Alert List */}
      {isExpanded && (
        <div className="p-4 space-y-3 bg-slate-50/60">
          
          {/* Allergy Warnings */}
          {safetyData.allergyWarnings?.map((w, idx) => (
            <div key={`all-${idx}`} className="p-3 bg-rose-100/70 border border-rose-300 rounded-xl text-xs text-rose-950 font-medium flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
              <div>{w}</div>
            </div>
          ))}

          {/* Contraindications */}
          {safetyData.contraindications?.map((c, idx) => (
            <div key={`ci-${idx}`} className="p-3 bg-amber-100/70 border border-amber-300 rounded-xl text-xs text-amber-950 font-medium flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
              <div>{c}</div>
            </div>
          ))}

          {/* Pairwise Alerts */}
          {safetyData.alerts?.map((alert: DrugInteractionAlert, idx: number) => {
            const isHigh = alert.severity === 'high';
            const isHerb = alert.severity === 'herb_drug';

            return (
              <div 
                key={`alert-${idx}`} 
                className={`p-3.5 rounded-xl border text-xs space-y-1.5 ${
                  isHigh 
                    ? 'bg-rose-50 border-rose-200 text-rose-950' 
                    : isHerb 
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-950' 
                    : 'bg-amber-50 border-amber-200 text-amber-950'
                }`}
              >
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <div className="font-bold flex items-center space-x-1.5">
                    <Pill className="w-3.5 h-3.5 text-slate-700" />
                    <span>{alert.medication1}</span>
                    <span className="text-slate-400 font-normal">↔</span>
                    <span>{alert.medication2}</span>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                    isHigh 
                      ? 'bg-rose-200 text-rose-900 border border-rose-300' 
                      : isHerb 
                      ? 'bg-emerald-200 text-emerald-900 border border-emerald-300' 
                      : 'bg-amber-200 text-amber-900 border border-amber-300'
                  }`}>
                    {isHerb ? 'Ayush Herb-Drug' : `${alert.severity} severity`}
                  </span>
                </div>

                <div className="text-[11px] text-slate-700 font-normal">
                  <strong className="font-semibold text-slate-900">Mechanism:</strong> {alert.mechanism}
                </div>

                <div className="text-[11px] text-teal-900 bg-white/80 p-2 rounded-lg border border-slate-200 font-medium">
                  <strong className="font-semibold text-teal-950">Recommendation:</strong> {alert.clinicalRecommendation}
                </div>
              </div>
            );
          })}

          {/* Ayurvedic Pathya / Apathya Notes if present */}
          {safetyData.ayurvedicPathyaApathya && safetyData.ayurvedicPathyaApathya.length > 0 && (
            <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-1 text-xs text-emerald-950">
              <div className="font-bold flex items-center space-x-1 text-emerald-900">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                <span>Ayurvedic Lifestyle & Dietary Advisory (Pathya-Apathya):</span>
              </div>
              {safetyData.ayurvedicPathyaApathya.map((item, idx) => (
                <div key={idx} className="text-[11px] text-emerald-800">• {item}</div>
              ))}
            </div>
          )}

        </div>
      )}

    </div>
  );
};

