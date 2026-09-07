import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Siren, Clock, CheckCircle2, XCircle, Loader2, AlertTriangle, ArrowRight,
  UserMinus, ShieldAlert
} from 'lucide-react';
import { DispatchInboxItem } from '../../types';
import { ApiService } from '../../services/api';

/**
 * Cases needing a decision from the signed-in doctor. Two kinds, and the
 * difference between them is the whole point.
 *
 * An OFFER is a new emergency being paged out. Nothing is owned until the paged
 * doctor accepts, and declining is not a failure path -- it is what makes
 * automatic assignment safe, because the roster does not know a doctor is
 * scrubbed in or already resuscitating someone. The reason is kept, since it is
 * ground truth the roster lacks.
 *
 * A HANDOVER is a patient already under treatment whose doctor went off duty.
 * It cannot be declined, because declining would leave nobody responsible for
 * someone who is already in a bed. It can only be claimed, and it is shown to
 * every doctor on shift rather than only the credentialled ones: an unowned
 * patient with nobody watching is the worse failure. The card says plainly
 * whether this doctor holds the privilege, so custody is taken with eyes open.
 */

const DECLINE_REASONS = [
  'Currently scrubbed into another procedure',
  'Already managing a higher-acuity case',
  'Not credentialled for this intervention',
  'Physically unable to reach in time',
];

export const DispatchInbox: React.FC<{ onChanged?: () => void }> = ({ onChanged }) => {
  const [items, setItems] = useState<DispatchInboxItem[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decliningFor, setDecliningFor] = useState<string | null>(null);
  const [declineReason, setDeclineReason] = useState<string>(DECLINE_REASONS[0]);
  const [customReason, setCustomReason] = useState<string>('');
  const [outcome, setOutcome] = useState<string | null>(null);
  // Offers expire server-side; this only drives the visible countdown.
  const [nowMs, setNowMs] = useState<number>(Date.now());
  // When each distinct offer was first seen here. Timing the countdown from the
  // last poll instead would restart it every ten seconds, so a ninety-second
  // window would never visibly run out.
  const firstSeen = useRef<Map<string, { offeredAt: string; at: number }>>(new Map());

  const load = useCallback(async () => {
    try {
      const next = await ApiService.getDoctorInbox();
      const seen = firstSeen.current;
      const live = new Set<string>();
      for (const { record } of next) {
        if (!record.currentOffer) continue;
        live.add(record.sessionId);
        const prior = seen.get(record.sessionId);
        if (!prior || prior.offeredAt !== record.currentOffer.offeredAt) {
          // A re-offer of the same case is a fresh window.
          seen.set(record.sessionId, {
            offeredAt: record.currentOffer.offeredAt, at: Date.now(),
          });
        }
      }
      for (const key of Array.from(seen.keys())) {
        if (!live.has(key)) seen.delete(key);
      }
      setItems(next);
      setError(null);
    } catch (err: any) {
      // A 401 is handled by the gate around this component; anything else is
      // worth showing, because an inbox that silently stops polling looks
      // exactly like an inbox with nothing in it.
      if (err?.status !== 401) {
        setError(err?.message || 'Could not load the emergency inbox.');
      }
    }
  }, []);

  useEffect(() => {
    load();
    // Fast enough that a paged case appears while there is still time to act on
    // it. Polling every ten seconds against a response window measured in tens
    // of seconds spent a large part of that window showing nothing.
    const poll = setInterval(load, 4000);
    const clock = setInterval(() => setNowMs(Date.now()), 1000);
    return () => { clearInterval(poll); clearInterval(clock); };
  }, [load]);

  const act = async (sessionId: string, fn: () => Promise<any>, done: string) => {
    setBusy(sessionId);
    setError(null);
    try {
      await fn();
      setOutcome(done);
      setDecliningFor(null);
      setCustomReason('');
      await load();
      onChanged?.();
    } catch (err: any) {
      setError(err?.message || 'The action could not be completed.');
    } finally {
      setBusy(null);
    }
  };

  if (!items.length && !error && !outcome) return null;

  // A live emergency outranks an unowned one for the colour of the whole strip.
  const hasOffer = items.some((i) => i.kind === 'offer');

  return (
    <div className={hasOffer
      ? 'bg-rose-50 border-b-2 border-rose-300'
      : 'bg-amber-50 border-b-2 border-amber-300'}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 space-y-3">

        {outcome && (
          <div className="flex items-center justify-between gap-3 p-2.5 bg-white border border-teal-300 rounded-xl text-xs">
            <span className="flex items-center gap-2 text-teal-900 font-bold">
              <CheckCircle2 className="w-4 h-4 text-teal-600" />
              {outcome}
            </span>
            <button type="button" onClick={() => setOutcome(null)}
                    className="text-slate-500 hover:text-slate-800 font-bold px-2">
              Dismiss
            </button>
          </div>
        )}

        {error && (
          <div className="p-2.5 bg-white border border-rose-300 rounded-xl text-xs text-rose-900 font-medium">
            {error}
          </div>
        )}

        {items.map(({ kind, record, patient, holdsPrivilege }) => {
          const offer = record.currentOffer;
          const isHandover = kind === 'handover';
          if (!offer && !isHandover) return null;

          const seenAt = firstSeen.current.get(record.sessionId)?.at ?? nowMs;
          const elapsed = Math.floor((nowMs - seenAt) / 1000);
          const secondsLeft = offer ? Math.max(0, offer.respondBySeconds - elapsed) : 0;
          const urgent = secondsLeft <= 30;
          const isBusy = busy === record.sessionId;

          return (
            <div key={`${kind}-${record.sessionId}`}
                 className={`bg-white rounded-2xl border-2 shadow-md overflow-hidden ${
                   isHandover ? 'border-amber-400' : 'border-rose-400'}`}>

              <div className={`px-4 py-2.5 text-white flex flex-wrap items-center justify-between gap-2 ${
                isHandover ? 'bg-amber-600' : 'bg-rose-600'}`}>
                <div className="flex items-center gap-2 min-w-0">
                  {isHandover ? <UserMinus className="w-4 h-4 shrink-0" />
                              : <Siren className="w-4 h-4 shrink-0" />}
                  <span className="text-xs font-black uppercase tracking-wider shrink-0">
                    {isHandover ? 'Patient left without a doctor'
                                : 'Emergency assigned to you'}
                  </span>
                  <span className="text-xs font-mono bg-white/20 px-1.5 py-0.5 rounded shrink-0">
                    {patient.tokenNumber}
                  </span>
                </div>
                {isHandover ? (
                  // No countdown: nothing rolls onward from here. The patient
                  // stays unowned until a person claims them, which is the
                  // reason this is visible at all.
                  <span className="text-xs font-bold bg-white/20 px-2 py-0.5 rounded">
                    Awaiting a clinician
                  </span>
                ) : (
                  <div className={`flex items-center gap-1.5 text-xs font-mono font-bold px-2 py-0.5 rounded ${
                    urgent ? 'bg-white text-rose-700 animate-pulse' : 'bg-white/20 text-white'}`}>
                    <Clock className="w-3.5 h-3.5" />
                    <span>{secondsLeft}s to respond</span>
                  </div>
                )}
              </div>

              <div className="p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-black text-slate-900">
                      {patient.patientName}
                      {patient.age != null && (
                        <span className="font-medium text-slate-500">
                          {' '}· {patient.age} yrs{patient.gender ? ` · ${patient.gender}` : ''}
                        </span>
                      )}
                    </div>
                    <div className={`text-xs font-bold mt-0.5 ${
                      isHandover ? 'text-amber-800' : 'text-rose-800'}`}>
                      {record.condition}
                    </div>
                    {patient.chiefComplaint && (
                      <p className="text-xs text-slate-600 mt-1 max-w-2xl">{patient.chiefComplaint}</p>
                    )}
                  </div>

                  {record.deadline && (
                    <div className={`text-[11px] rounded-xl px-3 py-2 border shrink-0 ${
                      record.deadline.breached
                        ? 'bg-rose-50 border-rose-300 text-rose-900'
                        : 'bg-amber-50 border-amber-200 text-amber-900'}`}>
                      <div className="font-black uppercase tracking-wider">
                        {record.deadline.label}
                      </div>
                      <div className="font-mono">
                        {record.deadline.remainingMinutes} min left of{' '}
                        {record.deadline.targetMinutes}
                      </div>
                      {record.deadline.breached && (
                        <div className="flex items-center gap-1 font-bold mt-0.5">
                          <AlertTriangle className="w-3 h-3" /> Target breached
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Why this landed on your screen and not someone else's. */}
                {offer && offer.reasoning.length > 0 && (
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5">
                    <span className="text-[10px] font-black uppercase tracking-wider text-slate-500 block mb-1">
                      Why you were paged
                    </span>
                    <ul className="text-[11px] text-slate-700 space-y-0.5">
                      {offer.reasoning.map((r, i) => (
                        <li key={i} className="flex gap-1.5">
                          <span className="text-slate-400">•</span><span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {isHandover && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-2.5 space-y-1.5">
                    <p className="text-[11px] text-amber-900 font-medium">
                      {record.handoverReason ||
                        'The doctor treating this patient has gone off duty.'}
                    </p>
                    <p className="text-[11px] text-amber-800">
                      They are still in their bed and still being treated. This case
                      is not re-assigned automatically &mdash; someone has to knowingly
                      pick them up.
                    </p>
                    {!holdsPrivilege && (
                      <p className="flex items-start gap-1.5 text-[11px] font-bold text-rose-800 pt-0.5">
                        <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-px" />
                        <span>
                          You do not hold &lsquo;{record.requiredPrivilege}&rsquo;. Taking
                          this patient means custodial responsibility until someone
                          credentialled is free.
                        </span>
                      </p>
                    )}
                  </div>
                )}

                {!isHandover && record.declinedDoctorIds.length > 0 && (
                  <p className="text-[11px] text-slate-500">
                    Previously offered to {record.declinedDoctorIds.length} other doctor(s).
                  </p>
                )}

                {decliningFor === record.sessionId ? (
                  <div className="space-y-2 border-t border-slate-100 pt-3">
                    <span className="text-[11px] font-black uppercase tracking-wider text-slate-600">
                      Why can you not take this case?
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {DECLINE_REASONS.map((r) => (
                        <label key={r}
                               className={`flex items-center gap-2 p-2 rounded-lg border text-[11px] cursor-pointer ${
                                 declineReason === r
                                   ? 'bg-slate-900 text-white border-slate-900 font-bold'
                                   : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}`}>
                          <input type="radio" name={`reason-${record.sessionId}`} value={r}
                                 checked={declineReason === r}
                                 onChange={(e) => setDeclineReason(e.target.value)}
                                 className="w-3 h-3" />
                          <span>{r}</span>
                        </label>
                      ))}
                    </div>
                    <input
                      type="text" value={customReason}
                      onChange={(e) => setCustomReason(e.target.value)}
                      placeholder="Or give another reason…"
                      className="w-full border border-slate-300 rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-slate-400"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        type="button" disabled={isBusy}
                        onClick={() => act(record.sessionId,
                          () => ApiService.declineDispatch(
                            record.sessionId, customReason.trim() || declineReason),
                          `Declined. The case has been re-offered to the next candidate.`)}
                        className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-black rounded-xl flex items-center gap-1.5 min-h-[44px] cursor-pointer"
                      >
                        {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                : <ArrowRight className="w-3.5 h-3.5" />}
                        <span>Confirm decline &amp; reassign</span>
                      </button>
                      <button
                        type="button" onClick={() => setDecliningFor(null)}
                        className="px-3 py-2.5 text-xs font-bold text-slate-600 hover:text-slate-900 min-h-[44px] cursor-pointer"
                      >
                        Back
                      </button>
                    </div>
                  </div>
                ) : isHandover ? (
                  <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                    <button
                      type="button" disabled={isBusy}
                      onClick={() => act(record.sessionId,
                        () => ApiService.takeOverDispatch(record.sessionId),
                        `${patient.patientName} is now under your care.`)}
                      className="px-5 py-2.5 bg-amber-700 hover:bg-amber-800 disabled:opacity-50 text-white text-xs font-black rounded-xl flex items-center gap-1.5 min-h-[44px] cursor-pointer"
                    >
                      {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              : <CheckCircle2 className="w-4 h-4" />}
                      <span>Take over this patient</span>
                    </button>
                    {/* Deliberately no decline. Refusing a patient who is already
                        in a bed would leave nobody responsible for them. */}
                    <span className="text-[11px] text-slate-500">
                      This stays on every on-duty doctor&rsquo;s screen until somebody takes it.
                    </span>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                    <button
                      type="button" disabled={isBusy}
                      onClick={() => act(record.sessionId,
                        () => ApiService.acceptDispatch(record.sessionId),
                        `You have accepted ${patient.patientName}. The case is yours; a bed is being allocated.`)}
                      className="px-5 py-2.5 bg-teal-700 hover:bg-teal-800 disabled:opacity-50 text-white text-xs font-black rounded-xl flex items-center gap-1.5 min-h-[44px] cursor-pointer"
                    >
                      {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              : <CheckCircle2 className="w-4 h-4" />}
                      <span>Accept &amp; take ownership</span>
                    </button>
                    <button
                      type="button" disabled={isBusy}
                      onClick={() => { setDecliningFor(record.sessionId); setDeclineReason(DECLINE_REASONS[0]); }}
                      className="px-5 py-2.5 bg-white hover:bg-slate-50 border border-slate-300 text-slate-800 text-xs font-black rounded-xl flex items-center gap-1.5 min-h-[44px] cursor-pointer"
                    >
                      <XCircle className="w-4 h-4 text-slate-500" />
                      <span>Cannot take it</span>
                    </button>
                    <span className="text-[11px] text-slate-500">
                      Declining reassigns immediately — it never drops the patient.
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
