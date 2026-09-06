import React, { useState, useEffect, useCallback } from 'react';
import {
  Stethoscope, LogOut, Clock, MapPin, Loader2,
  CheckCircle2, Footprints, Scissors, MoonStar
} from 'lucide-react';
import { DoctorAccount, DoctorDutyStatus, DutyState } from '../../types';
import { ApiService } from '../../services/api';
import { DoctorLogin } from './DoctorLogin';

interface RequireDoctorProps {
  children: React.ReactNode;
}

const DUTY_OPTIONS: { value: DutyState; label: string; icon: React.ElementType; tone: string }[] = [
  { value: 'available',    label: 'Available',    icon: CheckCircle2, tone: 'bg-teal-600' },
  { value: 'on_rounds',    label: 'On Rounds',    icon: Footprints,   tone: 'bg-blue-600' },
  { value: 'in_procedure', label: 'In Procedure', icon: Scissors,     tone: 'bg-amber-600' },
  { value: 'off_duty',     label: 'Off Duty',     icon: MoonStar,     tone: 'bg-slate-500' },
];

/**
 * Gates the physician routes behind doctor authentication.
 *
 * A stored account is not proof of a live session -- tokens live in backend
 * memory, so a server restart invalidates them. The profile is re-fetched on
 * mount and a 401 sends the doctor back to the sign-in screen.
 */
export const RequireDoctor: React.FC<RequireDoctorProps> = ({ children }) => {
  const [doctor, setDoctor] = useState<DoctorAccount | null>(() => ApiService.getDoctorAccount());
  const [duty, setDuty] = useState<DoctorDutyStatus | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(!!ApiService.getDoctorAccount());

  const verifySession = useCallback(async () => {
    if (!ApiService.getDoctorToken()) {
      setIsVerifying(false);
      return;
    }
    try {
      const profile = await ApiService.getDoctorProfile();
      setDoctor(profile.doctor);
      setDuty(profile.duty);
    } catch (err: any) {
      if (err?.status === 401) {
        ApiService.clearDoctorAuth();
        setDoctor(null);
        setDuty(null);
      }
    } finally {
      setIsVerifying(false);
    }
  }, []);

  useEffect(() => {
    verifySession();
  }, [verifySession]);

  const handleLoginSuccess = (acc: DoctorAccount) => {
    setDoctor(acc);
    setIsVerifying(true);
    verifySession();
  };

  const handleLogout = async () => {
    await ApiService.doctorLogout();
    setDoctor(null);
    setDuty(null);
  };

  const handleDutyChange = async (next: DutyState) => {
    try {
      const res = await ApiService.setDoctorDuty(next);
      setDuty(res.duty);
    } catch (err) {
      console.error('Failed to update duty state:', err);
    }
  };

  if (isVerifying) {
    return (
      <div className="max-w-md mx-auto py-24 flex flex-col items-center space-y-3 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        <span className="text-xs font-semibold">Verifying hospital credentials…</span>
      </div>
    );
  }

  if (!doctor) {
    return <DoctorLogin onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div>
      {/* Signed-in doctor bar */}
      <div className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex flex-wrap items-center justify-between gap-3">

          <div className="flex items-center space-x-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow shrink-0">
              <Stethoscope className="w-4.5 h-4.5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-bold text-slate-900 truncate">{doctor.fullName}</span>
                <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded shrink-0">
                  {doctor.registrationNumber}
                </span>
              </div>
              <div className="flex items-center space-x-2 text-[11px] text-slate-500">
                <span className="truncate">{doctor.title}</span>
                <span className="hidden sm:flex items-center space-x-1 shrink-0">
                  <MapPin className="w-3 h-3" />
                  <span>{doctor.roomNumber}</span>
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {duty && (
              <div className="flex items-center space-x-1.5 text-[11px] text-slate-500">
                <Clock className="w-3.5 h-3.5" />
                <span className="font-mono">{duty.shiftStart}–{duty.shiftEnd}</span>
                <span
                  className={`px-1.5 py-0.5 rounded font-bold ${
                    duty.onShift
                      ? 'bg-teal-50 text-teal-700 border border-teal-200'
                      : 'bg-slate-100 text-slate-500 border border-slate-200'
                  }`}
                >
                  {duty.onShift ? 'On shift' : 'Off shift'}
                </span>
              </div>
            )}

            {/* Duty state selector -- drives emergency dispatch eligibility */}
            <div className="flex items-center rounded-xl border border-slate-200 overflow-hidden">
              {DUTY_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const active = duty?.dutyState === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => handleDutyChange(opt.value)}
                    title={opt.label}
                    disabled={!duty?.onShift && opt.value !== 'off_duty'}
                    className={`px-2.5 py-1.5 text-[11px] font-bold flex items-center space-x-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                      active ? `${opt.tone} text-white` : 'bg-white text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span className="hidden lg:inline">{opt.label}</span>
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="px-2.5 py-1.5 rounded-xl border border-slate-200 text-[11px] font-bold text-slate-600 hover:bg-slate-50 flex items-center space-x-1 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>

        </div>
      </div>

      {children}
    </div>
  );
};
