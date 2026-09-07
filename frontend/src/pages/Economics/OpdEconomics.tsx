import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingDown, Clock, Users, IndianRupee, RefreshCw,
  AlertTriangle, CheckCircle2, SlidersHorizontal
} from 'lucide-react';
import { ApiService } from '../../services/api';

interface ModeRow {
  mode: string;
  patientsSeen: number;
  patientsTurnedAway: number;
  medianWaitMinutes: number | null;
  p90WaitMinutes: number | null;
  doctorHoursUsed: number;
  costPerPatientSeen: number | null;
}

interface CurvePoint {
  kiosks: number;
  patientsSeen: number;
  medianWaitMinutes: number | null;
  costPerPatientSeen: number | null;
}

const MODE_LABEL: Record<string, string> = {
  baseline: 'Doctor takes the history',
  nurse_desk: 'Nurse-led history desk',
  kiosk: 'MediKiosk self-service intake',
};

export const OpdEconomics: React.FC = () => {
  const [patients, setPatients] = useState(1200);
  const [doctors, setDoctors] = useState(12);
  const [doctorCost, setDoctorCost] = useState(1200);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await ApiService.getOpdEconomics({ patients, doctors, doctorCost }));
    } catch (e: any) {
      setError(e.message || 'Could not run the model.');
    } finally {
      setLoading(false);
    }
  }, [patients, doctors, doctorCost]);

  useEffect(() => { load(); }, [load]);

  const rows: ModeRow[] = data?.results || [];
  const head = data?.headline;
  const curve: CurvePoint[] = data?.capacityCurve || [];
  const maxSeen = Math.max(1, ...curve.map(c => c.patientsSeen));

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">

      <div className="space-y-1">
        <h1 className="text-2xl font-black text-slate-900">What the kiosk is worth</h1>
        <p className="text-sm text-slate-600 max-w-3xl">
          A simulated outpatient day &mdash; the same patients arriving at the same
          doctors, with only the intake method changed. These are projections from
          the assumptions below, not measurements. Change them and the numbers move.
        </p>
      </div>

      {/* Assumptions the judge can argue with, live */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center space-x-2 mb-4">
          <SlidersHorizontal className="w-4 h-4 text-indigo-600" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
            Change an assumption and watch it recompute
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          {[
            { label: 'Patients per day', value: patients, set: setPatients,
              min: 200, max: 6000, step: 100 },
            { label: 'Doctors on duty', value: doctors, set: setDoctors,
              min: 2, max: 60, step: 1 },
            { label: 'Doctor cost (₹/hour)', value: doctorCost, set: setDoctorCost,
              min: 300, max: 3000, step: 50 },
          ].map((f) => (
            <div key={f.label}>
              <div className="flex justify-between mb-1">
                <label className="text-xs font-bold text-slate-700">{f.label}</label>
                <span className="text-xs font-mono font-bold text-indigo-700">
                  {f.value.toLocaleString('en-IN')}
                </span>
              </div>
              <input
                type="range" min={f.min} max={f.max} step={f.step} value={f.value}
                onChange={(e) => f.set(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
            </div>
          ))}
        </div>
        {data && (
          <p className="text-[11px] text-slate-500 mt-4">
            Model sized <strong>{data.scenario.kiosks}</strong> kiosks for this load
            &mdash; enough that intake is not the constraint.
          </p>
        )}
      </div>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center space-x-2 text-slate-500 text-sm py-10 justify-center">
          <RefreshCw className="w-4 h-4 animate-spin" /><span>Running the day…</span>
        </div>
      )}

      {head && (
        <>
          {/* The four numbers that matter */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Tailwind cannot see class names built at runtime, so these are
                written out in full rather than interpolated. */}
            {[
              { icon: Clock, box: 'bg-teal-50 border-teal-200', ink: 'text-teal-700',
                value: `${head.doctorMinutesPerPatientBaseline} → ${head.doctorMinutesPerPatientKiosk} min`,
                label: 'Doctor time per patient' },
              { icon: IndianRupee, box: 'bg-indigo-50 border-indigo-200', ink: 'text-indigo-700',
                value: `₹${head.costPerPatientBaseline} → ₹${head.costPerPatientKiosk}`,
                label: 'Cost per patient seen' },
              { icon: Users, box: 'bg-violet-50 border-violet-200', ink: 'text-violet-700',
                value: `${head.additionalPatientsSeenPerDay > 0 ? '+' : ''}${head.additionalPatientsSeenPerDay}`,
                label: 'Patients seen per day' },
              { icon: TrendingDown, box: 'bg-emerald-50 border-emerald-200', ink: 'text-emerald-700',
                value: head.paybackMonths ? `${head.paybackMonths} mo` : '—',
                label: 'Payback on hardware' },
            ].map((c) => (
              <div key={c.label} className={`rounded-2xl p-4 border ${c.box}`}>
                <c.icon className={`w-4 h-4 mb-2 ${c.ink}`} />
                <div className="text-lg font-black text-slate-900 leading-tight">{c.value}</div>
                <div className="text-[11px] text-slate-600 mt-0.5">{c.label}</div>
              </div>
            ))}
          </div>

          {/* Honest health check on the scenario */}
          <div className={`rounded-xl p-3 text-xs flex items-start space-x-2 border ${
            head.intakeIsBottleneck
              ? 'bg-amber-50 border-amber-200 text-amber-900'
              : 'bg-teal-50 border-teal-200 text-teal-900'}`}>
            {head.intakeIsBottleneck
              ? <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              : <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />}
            <span>{head.note}</span>
          </div>

          {/* Three arrangements, same day */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100">
              <h2 className="text-sm font-bold text-slate-900">
                The same day, three ways of taking the history
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    {['Intake method', 'Seen', 'Turned away', 'Median wait',
                      '90th pct wait', 'Doctor hours', 'Cost / patient'].map(h => (
                      <th key={h} className="text-left font-bold px-4 py-2.5">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const isKiosk = r.mode === 'kiosk';
                    return (
                      <tr key={r.mode}
                          className={`border-t border-slate-100 ${isKiosk ? 'bg-teal-50/60' : ''}`}>
                        <td className={`px-4 py-2.5 ${isKiosk ? 'font-bold text-teal-900' : 'text-slate-700'}`}>
                          {MODE_LABEL[r.mode] || r.mode}
                        </td>
                        <td className="px-4 py-2.5 font-mono">{r.patientsSeen}</td>
                        <td className="px-4 py-2.5 font-mono text-slate-500">{r.patientsTurnedAway}</td>
                        <td className="px-4 py-2.5 font-mono">{r.medianWaitMinutes} min</td>
                        <td className="px-4 py-2.5 font-mono text-slate-500">{r.p90WaitMinutes} min</td>
                        <td className="px-4 py-2.5 font-mono">{r.doctorHoursUsed}</td>
                        <td className={`px-4 py-2.5 font-mono ${isKiosk ? 'font-bold text-teal-800' : ''}`}>
                          ₹{r.costPerPatientSeen}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="px-5 py-2.5 text-[11px] text-slate-500 border-t border-slate-100">
              Cost is per patient <strong>seen</strong>. Comparing total daily cost
              would reward whichever method turned the most people away.
            </p>
          </div>

          {/* How many terminals are worth buying */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
            <h2 className="text-sm font-bold text-slate-900 mb-1">
              How many kiosks are worth buying?
            </h2>
            <p className="text-[11px] text-slate-500 mb-4">
              Throughput climbs with each terminal until the doctors become the
              constraint again. Past that point, more kiosks buy shorter queues, not
              more patients.
            </p>
            <div className="flex items-end space-x-1.5 h-40">
              {curve.map((p) => {
                const h = Math.max(4, (p.patientsSeen / maxSeen) * 100);
                const saturated = p.patientsSeen >= maxSeen * 0.98;
                return (
                  <div key={p.kiosks} className="flex-1 flex flex-col items-center justify-end h-full group">
                    <span className="text-[9px] font-mono text-slate-500 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {p.patientsSeen}
                    </span>
                    <div
                      style={{ height: `${h}%` }}
                      title={`${p.kiosks} kiosks · ${p.patientsSeen} seen · ${p.medianWaitMinutes} min median wait`}
                      className={`w-full rounded-t transition-all ${
                        saturated ? 'bg-teal-600' : 'bg-indigo-400'}`}
                    />
                    <span className="text-[9px] font-mono text-slate-500 mt-1">{p.kiosks}</span>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center space-x-4 mt-3 text-[10px] text-slate-500">
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-2.5 rounded-sm bg-indigo-400 inline-block" />
                <span>intake still the constraint</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2.5 h-2.5 rounded-sm bg-teal-600 inline-block" />
                <span>doctors are the constraint</span>
              </span>
              <span className="ml-auto">terminals →</span>
            </div>
          </div>

          {/* Everything the numbers rest on */}
          <details className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
            <summary className="text-sm font-bold text-slate-900 cursor-pointer">
              Every assumption behind these numbers
            </summary>
            <p className="text-[11px] text-slate-500 mt-2 mb-3">
              Stated so they can be challenged. The result is most sensitive to the
              doctor cost per hour.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
              {Object.entries(data.assumptions).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-slate-50 py-1">
                  <span className="text-slate-600">
                    {k.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase())}
                  </span>
                  <span className="font-mono font-bold text-slate-900">{String(v)}</span>
                </div>
              ))}
            </div>
          </details>
        </>
      )}
    </div>
  );
};
