"""
Discrete-event simulation for benchmarking emergency dispatch policies.

A dispatch policy is only as good as what it beats. This runs a stream of
emergency arrivals through competing policies on an identical roster and the
identical arrival sequence, so the comparison is like-for-like:

  first_available  -- take whoever is free, ignoring privilege scarcity
  round_robin      -- rotate through qualified doctors in turn
  deadline_aware   -- the DispatchService policy

Reported per policy: deadline misses, unassignable cases, median and 90th
percentile time-to-doctor, and how evenly work landed across the roster.
Deadline misses are the metric that matters; the rest explain why.

Deterministic for a given seed, so results are reproducible in a report.
"""
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.services.dispatch_service import DispatchService, DEFAULT_CASE_MINUTES
from app.services.doctor_service import DoctorService

# Presentations sampled by the generator, with their share of emergency arrivals.
CASE_MIX = [
    ("Potential Acute Coronary Syndrome Warning (Severe chest pain with left arm radiation)", 0.22),
    ("Potential Acute Stroke Warning (Sudden focal neurological deficit)", 0.18),
    ("Severe Acute Airway/Respiratory Distress Warning", 0.15),
    ("Acute Active Hemorrhage Warning (Hematemesis / Melena)", 0.12),
    ("Severe Anaphylaxis / Airway Swelling Warning", 0.08),
    ("High Fever with Altered Sensorium or Meningismus Warning", 0.15),
    ("High-Acuity Psychiatric Crisis / Suicide Risk Alert", 0.10),
]

ONSET_CHOICES = ["", "30 minutes ago", "1 hour ago", "2 hours ago",
                 "3 hours ago", "4 hours ago", "6 hours ago"]


@dataclass
class SimCase:
    caseId: int
    arrivalMinute: int
    redFlagReason: str
    onsetText: str


@dataclass
class SimResult:
    policy: str
    cases: int = 0
    assigned: int = 0
    unassignable: int = 0
    deadlineMisses: int = 0
    # Assignments handed to a doctor whose shift ends before the case could
    # finish -- a handover mid-resuscitation. deadline_aware refuses these,
    # which is why it reports more unassignable cases than the baselines.
    handoverRisk: int = 0
    timesToDoctor: List[int] = field(default_factory=list)
    perDoctorLoad: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        times = sorted(self.timesToDoctor)
        loads = list(self.perDoctorLoad.values())
        return {
            "policy": self.policy,
            "cases": self.cases,
            "assigned": self.assigned,
            "unassignable": self.unassignable,
            "deadlineMisses": self.deadlineMisses,
            "handoverRisk": self.handoverRisk,
            "medianTimeToDoctor": statistics.median(times) if times else None,
            "p90TimeToDoctor": times[int(len(times) * 0.9)] if times else None,
            "maxTimeToDoctor": max(times) if times else None,
            "loadSpread": round(max(loads) - min(loads), 2) if loads else 0.0,
            "perDoctorLoad": dict(sorted(self.perDoctorLoad.items())),
        }


class _SimSession:
    """Minimal stand-in for PatientSession, carrying only what dispatch reads."""

    def __init__(self, case: SimCase):
        self.sessionId = f"sim-{case.caseId}"
        self.redFlag = type("RF", (), {"reason": case.redFlagReason, "triggered": True})()
        self.historyOfPresentIllness = type("HPI", (), {"onset": case.onsetText})()
        self.triageScore = None


class DispatchSimulation:
    """Runs the same arrival stream through each policy and scores the outcomes."""

    def __init__(self, seed: int = 42, base_hour: int = 15):
        self.seed = seed
        self.base_time = datetime(2026, 9, 4, base_hour, 0)

    def generate_cases(self, count: int, span_minutes: int = 480) -> List[SimCase]:
        rng = random.Random(self.seed)
        reasons = [r for r, _ in CASE_MIX]
        weights = [w for _, w in CASE_MIX]
        cases = []
        for i in range(count):
            cases.append(SimCase(
                caseId=i,
                arrivalMinute=rng.randint(0, span_minutes),
                redFlagReason=rng.choices(reasons, weights=weights, k=1)[0],
                onsetText=rng.choice(ONSET_CHOICES),
            ))
        return sorted(cases, key=lambda c: c.arrivalMinute)

    # --- Policies -------------------------------------------------------

    @staticmethod
    def _qualified(svc: DoctorService, privilege: str, now: datetime) -> List[Any]:
        """On-shift, non-off-duty, interruptible doctors holding the privilege."""
        out = []
        for row in svc.roster(now):
            doc, duty = row["doctor"], row["duty"]
            if privilege not in doc.privileges:
                continue
            if not duty.onShift or duty.dutyState in ("off_duty", "in_procedure"):
                continue
            out.append(doc)
        return out

    def _pick(self, policy: str, svc: DoctorService, session: Any,
              now: datetime, rr_state: Dict[str, int]):
        """Returns (doctorId, projectedMinutes, deadlineRemaining, acuity) or None."""
        proto = DispatchService.protocol_for(session.redFlag.reason, None)
        deadline = DispatchService.build_deadline(proto, session, now)
        privilege = proto["privilege"]

        if policy == "deadline_aware":
            proposal = DispatchService.propose(session, now)
            if not proposal.proposed:
                return None
            c = proposal.proposed
            return (c.doctorId, c.projectedMinutesToDoctor,
                    proposal.deadline.remainingMinutes, proposal.acuityWeight)

        candidates = self._qualified(svc, privilege, now)
        if not candidates:
            candidates = self._qualified(svc, proto.get("fallbackPrivilege", privilege), now)
        if not candidates:
            return None

        if policy == "first_available":
            # Whoever is nearest, ignoring load and scarcity entirely.
            doc = min(candidates, key=lambda d: DispatchService.travel_minutes(d))
        elif policy == "round_robin":
            idx = rr_state.get(privilege, 0) % len(candidates)
            rr_state[privilege] = idx + 1
            doc = candidates[idx]
        else:
            raise ValueError(f"Unknown policy '{policy}'")

        duty = svc.get_duty(doc.doctorId, now)
        projected = DispatchService.travel_minutes(doc) + int(duty.activeCaseCount * 10)
        return doc.doctorId, projected, deadline.remainingMinutes, float(proto["acuityWeight"])

    # --- Runner ---------------------------------------------------------

    def run_policy(self, policy: str, cases: List[SimCase]) -> SimResult:
        import app.services.dispatch_service as dispatch_module

        svc = DoctorService()                       # fresh roster per policy
        original = dispatch_module.doctor_service
        dispatch_module.doctor_service = svc        # dispatch reads this module global
        try:
            result = SimResult(policy=policy)
            release_at: List[tuple] = []            # (minute, doctorId)
            rr_state: Dict[str, int] = {}

            for case in cases:
                now = self.base_time + timedelta(minutes=case.arrivalMinute)

                # Free doctors whose earlier cases have finished by now.
                for minute, did in [r for r in release_at if r[0] <= case.arrivalMinute]:
                    svc.release_assignment(did)
                release_at = [r for r in release_at if r[0] > case.arrivalMinute]

                result.cases += 1
                pick = self._pick(policy, svc, _SimSession(case), now, rr_state)
                if pick is None:
                    result.unassignable += 1
                    continue

                doctor_id, projected, remaining, acuity = pick
                result.assigned += 1

                # Would this doctor's shift end mid-case?
                duty = svc.get_duty(doctor_id, now)
                shift_left = DispatchService._minutes_until_shift_end(duty.shiftEnd, now)
                if shift_left is not None and shift_left < DEFAULT_CASE_MINUTES:
                    result.handoverRisk += 1

                result.timesToDoctor.append(projected)
                if projected > remaining:
                    result.deadlineMisses += 1

                svc.record_assignment(doctor_id, acuity)
                release_at.append((case.arrivalMinute + DEFAULT_CASE_MINUTES, doctor_id))

            for row in svc.roster(self.base_time):
                result.perDoctorLoad[row["doctor"].fullName] = row["duty"].acuityLoad
            return result
        finally:
            dispatch_module.doctor_service = original

    def compare(self, count: int = 60) -> List[Dict[str, Any]]:
        """Same arrival stream through every policy."""
        cases = self.generate_cases(count)
        return [self.run_policy(p, cases).summary()
                for p in ("first_available", "round_robin", "deadline_aware")]


dispatch_simulation = DispatchSimulation()
