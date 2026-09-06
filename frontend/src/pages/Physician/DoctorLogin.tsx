import React, { useState } from 'react';
import { Stethoscope, Lock, User, ShieldAlert, BadgeCheck } from 'lucide-react';
import { DoctorAccount } from '../../types';
import { ApiService } from '../../services/api';

interface DoctorLoginProps {
  onLoginSuccess: (doctor: DoctorAccount) => void;
}

export const DoctorLogin: React.FC<DoctorLoginProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState<string>('dr_khan');
  const [password, setPassword] = useState<string>('emerg123');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const demoAccounts = [
    { name: 'Dr. Imran Khan', user: 'dr_khan', pass: 'emerg123', role: 'Emergency Medicine Officer', shift: '08:00-20:00' },
    { name: 'Dr. Lakshmi Iyer', user: 'dr_iyer', pass: 'cardio456', role: 'Consultant Cardiologist', shift: '14:00-22:00' },
    { name: 'Dr. Debabrata Sen', user: 'dr_sen', pass: 'neuro123', role: 'Senior Consultant Neurologist', shift: '09:00-17:00' },
  ];

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await ApiService.doctorLogin(username, password);
      onLoginSuccess(data.doctor);
    } catch (err: any) {
      console.error('Doctor login error:', err);
      setErrorMessage(err.message || 'Invalid doctor username or password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-12 px-4">
      <div className="bg-white rounded-3xl p-8 shadow-2xl border border-slate-200 space-y-6">

        <div className="text-center space-y-2">
          <div className="w-14 h-14 bg-blue-600 text-white rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-blue-600/30">
            <Stethoscope className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-extrabold text-slate-900">Doctor Portal</h2>
          <p className="text-xs text-slate-500">
            Patient records carry identifiable clinical history. Sign in with your
            hospital credentials to open the OPD queue.
          </p>
        </div>

        {errorMessage && (
          <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Doctor Username
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="dr_khan"
                required
                className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              Hospital Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3.5 px-4 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-600/30 transition-all flex items-center justify-center space-x-2 min-h-[48px]"
          >
            <BadgeCheck className="w-4 h-4" />
            <span>{isLoading ? 'Authenticating...' : 'Sign In as Doctor'}</span>
          </button>
        </form>

        {/* Demo Fast Fill */}
        <div className="pt-4 border-t border-slate-100 space-y-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block text-center">
            Demo Registered Doctors
          </span>
          <div className="grid grid-cols-1 gap-2">
            {demoAccounts.map((acc) => (
              <button
                type="button"
                key={acc.user}
                onClick={() => {
                  setUsername(acc.user);
                  setPassword(acc.pass);
                }}
                className="text-left p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-xs text-slate-700 transition-colors flex items-center justify-between"
              >
                <div>
                  <span className="font-bold text-slate-900 block">{acc.name}</span>
                  <span className="text-[10px] text-slate-500">{acc.role}</span>
                </div>
                <span className="text-[10px] font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-600">
                  {acc.shift}
                </span>
              </button>
            ))}
          </div>
          <p className="text-[10px] text-slate-400 text-center pt-1">
            Shift hours are live — a doctor outside their window shows as off duty.
          </p>
        </div>

      </div>
    </div>
  );
};
