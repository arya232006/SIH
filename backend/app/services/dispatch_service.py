"""
Deadline-aware emergency dispatch for MediKiosk.

Emergency assignment is not "find a free doctor". It is meeting a clinical
deadline using a scarce, non-interchangeable, reusable resource, committing now
without knowing what arrives next. Assign the only interventional cardiologist
to a moderate case and the next STEMI has nobody.

The policy is therefore built on four ideas:

1. Acuity becomes a deadline, not a priority number. STEMI has a door-to-balloon
   target; stroke thrombolysis is measured from symptom ONSET, so part of the
   window is already gone when the patient reaches the desk.
2. Doctors are filtered by hard constraints -- privilege, on shift, shift long
   enough to finish, and never interrupting a procedure -- before any scoring.
3. Remaining candidates are ranked on time-to-patient, current load and a
   scarcity reserve that holds rare privileges back from lower-acuity cases.
4. Assignment is automatic and the RECEIVING doctor accepts. There is no third
   party approving each case: that would add latency to the most time-critical
   path in the system, and an approval that is always granted launders
   accountability rather than creating it. The doctor who accepts owns the case,
   which is how clinical responsibility already works. A decline reassigns
   immediately and its reason is kept -- "I am scrubbed in" is ground truth the
   roster does not have. Human judgment is reserved for the exception path,
   where the escalation ladder fires because the policy could not place the case.
"""
import re
from datetime import datetime

from app.services import clock
from typing import Any, Dict, List, Optional, Tuple

from app.models import (
    DispatchCandidate, DispatchDeadline, DispatchProposal,
    DispatchOffer, DispatchRecord, DoctorAccount,
)
from app.services.doctor_service import doctor_service

# Minutes of doctor time a case of this kind realistically consumes. Used to
# reject a doctor whose shift ends before they could finish.
DEFAULT_CASE_MINUTES = 45

# Where emergencies are received. Travel cost is measured to here.
CASUALTY_FLOOR = 0


class DispatchService:
    """Proposes an emergency assignment and explains why."""

    # Red-flag reason -> clinical protocol. `match` is tested against the
    # red-flag text produced by red_flag_service, so the catalogue stays tied to
    # what the system actually detects rather than a parallel taxonomy.
    EMERGENCY_PROTOCOLS: List[Dict[str, Any]] = [
        {
            "match": r"acute coronary syndrome|chest pain with left arm",
            "condition": "Acute Coronary Syndrome (STEMI pathway)",
            "privilege": "cardiac_cath",
            "fallbackPrivilege": "thrombolysis",
            "department": "Cardiology",
            "deadlineLabel": "Door-to-balloon",
            "deadlineMinutes": 90,
            "anchor": "arrival",
            "acuityWeight": 5.0,
            "caseMinutes": 90,
        },
        {
            "match": r"stroke|focal neurological deficit",
            "condition": "Acute Ischaemic Stroke (thrombolysis window)",
            "privilege": "thrombolysis",
            "fallbackPrivilege": "stroke_protocol",
            "department": "Neurology",
            "deadlineLabel": "Onset-to-needle",
            "deadlineMinutes": 270,          # 4.5 hours
            "anchor": "onset",               # clock started before arrival
            "acuityWeight": 5.0,
            "caseMinutes": 60,
        },
        {
            "match": r"anaphylaxis|airway swelling",
            "condition": "Anaphylaxis with airway compromise",
            "privilege": "intubation",
            "fallbackPrivilege": "acls",
            "department": "Emergency",
            "deadlineLabel": "Time-to-adrenaline",
            "deadlineMinutes": 10,
            "anchor": "arrival",
            "acuityWeight": 5.0,
            "caseMinutes": 45,
        },
        {
            "match": r"airway|respiratory distress",
            "condition": "Acute airway / respiratory failure",
            "privilege": "intubation",
            "fallbackPrivilege": "acls",
            "department": "Emergency",
            "deadlineLabel": "Time-to-airway",
            "deadlineMinutes": 10,
            "anchor": "arrival",
            "acuityWeight": 5.0,
            "caseMinutes": 45,
        },
        {
            "match": r"hemorrhage|haemorrhage|hematemesis|melena",
            "condition": "Acute active haemorrhage",
            "privilege": "resuscitation",
            "fallbackPrivilege": "acls",
            "department": "Emergency",
            "deadlineLabel": "Time-to-resuscitation",
            "deadlineMinutes": 15,
            "anchor": "arrival",
            "acuityWeight": 4.5,
            "caseMinutes": 60,
        },
        {
            "match": r"altered sensorium|meningismus|high fever",
            "condition": "Suspected sepsis / CNS infection",
            "privilege": "acls",
            "fallbackPrivilege": "general_medicine",
            "department": "Emergency",
            "deadlineLabel": "Time-to-antibiotics",
            "deadlineMinutes": 60,
            "anchor": "arrival",
            "acuityWeight": 4.0,
            "caseMinutes": 45,
        },
        {
            "match": r"psychiatric|suicide",
            "condition": "High-acuity psychiatric crisis",
            "privilege": "general_medicine",
            "fallbackPrivilege": "acls",
            "department": "Emergency",
            "deadlineLabel": "Time-to-assessment",
            "deadlineMinutes": 30,
            "anchor": "arrival",
            "acuityWeight": 3.5,
            "caseMinutes": 45,
        },
    ]

    DEFAULT_PROTOCOL: Dict[str, Any] = {
        "condition": "Undifferentiated emergency presentation",
        "privilege": "acls",
        "fallbackPrivilege": "general_medicine",
        "department": "Emergency",
        "deadlineLabel": "Time-to-doctor",
        "deadlineMinutes": 30,
        "anchor": "arrival",
        "acuityWeight": 3.0,
        "caseMinutes": DEFAULT_CASE_MINUTES,
    }

    # --- Clinical framing ------------------------------------------------

    @classmethod
    def protocol_for(cls, red_flag_reason: str, esi_level: Optional[int] = None) -> Dict[str, Any]:
        text = (red_flag_reason or "").lower()
        for proto in cls.EMERGENCY_PROTOCOLS:
            if re.search(proto["match"], text):
                return proto
        proto = dict(cls.DEFAULT_PROTOCOL)
        # With no matching protocol, fall back to the ESI target time, which the
        # triage service already computed from vitals and presentation.
        if esi_level == 1:
            proto["deadlineMinutes"], proto["acuityWeight"] = 10, 5.0
        elif esi_level == 2:
            proto["deadlineMinutes"], proto["acuityWeight"] = 20, 4.0
        return proto

    @staticmethod
    def parse_onset_minutes(onset_text: str) -> Optional[int]:
        """
        Minutes elapsed since symptom onset, read from the free-text HPI the
        kiosk already captured. For stroke this is the difference between a
        usable thrombolysis window and a missed one.
        """
        if not onset_text:
            return None
        t = onset_text.lower()
        m = re.search(r"(\d+(?:\.\d+)?)\s*(minute|min|hour|hr|day)s?", t)
        if not m:
            if "just now" in t or "moments ago" in t:
                return 0
            return None
        value, unit = float(m.group(1)), m.group(2)
        factor = {"minute": 1, "min": 1, "hour": 60, "hr": 60, "day": 1440}[unit]
        return int(value * factor)

    @classmethod
    def build_deadline(
        cls, proto: Dict[str, Any], session: Any, now: Optional[datetime] = None
    ) -> DispatchDeadline:
        target = int(proto["deadlineMinutes"])
        anchor = proto["anchor"]
        elapsed, basis = 0, "Clock started on arrival at the kiosk."

        if anchor == "onset":
            hpi = getattr(session, "historyOfPresentIllness", None)
            onset_text = getattr(hpi, "onset", "") if hpi is not None else ""
            parsed = cls.parse_onset_minutes(onset_text)
            if parsed is not None:
                elapsed = parsed
                basis = f"Symptom onset reported as '{onset_text}' during intake."
            else:
                basis = ("Symptom onset not established during intake; treating the "
                         "full window as available, which may be optimistic.")

        remaining = target - elapsed
        return DispatchDeadline(
            label=proto["deadlineLabel"],
            targetMinutes=target,
            anchor=anchor,
            elapsedMinutes=elapsed,
            remainingMinutes=remaining,
            breached=remaining <= 0,
            basis=basis,
        )

    # --- Candidate assessment -------------------------------------------

    @staticmethod
    def _floor_of(location: str) -> int:
        text = (location or "").lower()
        for word, level in (("ground", 0), ("first", 1), ("second", 2), ("third", 3)):
            if word in text:
                return level
        return 1

    @classmethod
    def travel_minutes(cls, doctor: DoctorAccount) -> int:
        """Rough walking time from the doctor's room to the casualty bay."""
        return 2 + int(abs(cls._floor_of(doctor.floorLocation) - CASUALTY_FLOOR) * 1.5)

    @classmethod
    def _privilege_scarcity(cls, privilege: str, now: Optional[datetime] = None) -> float:
        """
        Fraction of the on-shift roster lacking this privilege. A privilege only
        one doctor holds scores near 1.0, and that doctor is held in reserve for
        cases that genuinely need them.
        """
        on_shift = [r for r in doctor_service.roster(now) if r["duty"].onShift]
        if not on_shift:
            return 0.0
        holders = sum(1 for r in on_shift if privilege in r["doctor"].privileges)
        if holders == 0:
            return 1.0
        return 1.0 - (holders / len(on_shift))

    @classmethod
    def assess_candidate(
        cls,
        doctor: DoctorAccount,
        proto: Dict[str, Any],
        deadline: DispatchDeadline,
        privilege: str,
        now: Optional[datetime] = None,
    ) -> DispatchCandidate:
        duty = doctor_service.get_duty(doctor.doctorId, now)
        travel = cls.travel_minutes(doctor)
        reasoning: List[str] = []

        cand = DispatchCandidate(
            doctorId=doctor.doctorId, fullName=doctor.fullName, title=doctor.title,
            department=doctor.department, roomNumber=doctor.roomNumber,
            dutyState=duty.dutyState if duty else "unknown",
            feasible=False, travelMinutes=travel,
            activeCaseCount=duty.activeCaseCount if duty else 0,
            acuityLoad=duty.acuityLoad if duty else 0.0,
        )

        # --- Hard constraints, checked before any scoring ---
        if privilege not in doctor.privileges:
            cand.exclusionReason = f"Lacks required privilege '{privilege}'."
            return cand
        if not duty or not duty.onShift:
            cand.exclusionReason = "Not on shift."
            return cand
        if duty.dutyState == "off_duty":
            cand.exclusionReason = "On shift but reported off duty."
            return cand
        if duty.dutyState == "in_procedure":
            cand.exclusionReason = "In an uninterruptible procedure."
            return cand

        # A doctor whose shift ends before the case could finish is not a
        # candidate; handing over mid-resuscitation is its own clinical risk.
        shift_left = cls._minutes_until_shift_end(duty.shiftEnd, now)
        case_minutes = int(proto.get("caseMinutes", DEFAULT_CASE_MINUTES))
        if shift_left is not None and shift_left < case_minutes:
            cand.exclusionReason = (
                f"Shift ends in {shift_left} min; case needs about {case_minutes} min."
            )
            return cand

        # --- Feasible: score it ---
        queue_delay = int(duty.activeCaseCount * 10)
        projected = travel + queue_delay
        cand.projectedMinutesToDoctor = projected
        cand.meetsDeadline = projected <= deadline.remainingMinutes
        cand.feasible = True

        reasoning.append(f"Holds '{privilege}'.")
        reasoning.append(f"On shift until {duty.shiftEnd} ({shift_left} min left).")
        reasoning.append(f"{travel} min from casualty, {duty.activeCaseCount} active case(s).")

        # Reserve: hold back doctors whose OTHER capabilities are scarce. If this
        # case needs thrombolysis and one candidate is also the only cath operator
        # on shift, prefer someone else so they stay free for a STEMI. Scoring the
        # required privilege itself would be useless -- it is constant across every
        # candidate, since holding it is a hard constraint.
        rarest, rarest_priv = 0.0, ""
        for other in doctor.privileges:
            if other == privilege:
                continue
            s = cls._privilege_scarcity(other, now)
            if s > rarest:
                rarest, rarest_priv = s, other
        # Lower acuity means a stronger hold. A residual floor of 1.0 remains even
        # at maximum acuity: between two doctors who both meet the deadline, the
        # less scarce one should take it, so the specialist stays free for the
        # case only they can handle. The floor never overrides the deadline, which
        # dominates the score by two orders of magnitude.
        acuity_headroom = max(1.0, 5.0 - float(proto["acuityWeight"]))
        cand.scarcityPenalty = round(rarest * acuity_headroom * 6.0, 2)
        if cand.scarcityPenalty > 0:
            reasoning.append(
                f"Also the scarce holder of '{rarest_priv}'; held in reserve "
                f"(penalty {cand.scarcityPenalty})."
            )

        cand.score = round(
            projected                                  # time to the patient
            + duty.acuityLoad * 3.0                    # shift fairness / fatigue
            + cand.scarcityPenalty                     # reserve scarce privileges
            + (0.0 if cand.meetsDeadline else 100.0),  # deadline miss dominates
            2,
        )
        if not cand.meetsDeadline:
            reasoning.append(
                f"Would reach the patient in {projected} min but only "
                f"{deadline.remainingMinutes} min remain."
            )
        cand.reasoning = reasoning
        return cand

    @staticmethod
    def _minutes_until_shift_end(shift_end: str, now: Optional[datetime] = None) -> Optional[int]:
        if not shift_end:
            return None
        now = now or clock.now()
        try:
            eh, em = (int(x) for x in shift_end.split(":"))
        except ValueError:
            return None
        cur = now.hour * 60 + now.minute
        end = eh * 60 + em
        if end <= cur:          # shift ends after midnight
            end += 24 * 60
        return end - cur

    # --- Proposal --------------------------------------------------------

    @classmethod
    def propose(cls, session: Any, now: Optional[datetime] = None) -> DispatchProposal:
        now = now or clock.now()
        red_flag = getattr(session, "redFlag", None)
        reason = getattr(red_flag, "reason", "") if red_flag else ""
        triage = getattr(session, "triageScore", None)
        esi = getattr(triage, "esiLevel", None) if triage else None

        proto = cls.protocol_for(reason, esi)
        deadline = cls.build_deadline(proto, session, now)

        roster = doctor_service.roster(now)

        def assess_with(priv: str):
            found = [cls.assess_candidate(r["doctor"], proto, deadline, priv, now)
                     for r in roster]
            return (sorted([c for c in found if c.feasible], key=lambda c: c.score),
                    [c for c in found if not c.feasible])

        # Preferred privilege first. Fall back to the wider one when nobody
        # holding the preferred is actually usable -- if no cath operator can
        # take the case, thrombolysis is the clinical answer, not giving up.
        privilege = proto["privilege"]
        feasible, excluded = assess_with(privilege)
        fallback = proto.get("fallbackPrivilege")
        if not feasible and fallback and fallback != privilege:
            fb_feasible, fb_excluded = assess_with(fallback)
            if fb_feasible:
                privilege = fallback
                feasible, excluded = fb_feasible, fb_excluded
                for cand in feasible:
                    cand.reasoning.insert(
                        0, f"No doctor available for '{proto['privilege']}'; "
                           f"falling back to '{fallback}'."
                    )

        proposed = feasible[0] if feasible else None
        escalation = cls._escalation_ladder(proposed, deadline, privilege, now)
        rationale = cls._rationale(proto, deadline, privilege, proposed, feasible)

        return DispatchProposal(
            sessionId=getattr(session, "sessionId", ""),
            condition=proto["condition"],
            requiredPrivilege=privilege,
            preferredDepartment=proto["department"],
            acuityWeight=float(proto["acuityWeight"]),
            deadline=deadline,
            proposed=proposed,
            alternatives=feasible[1:4],
            excluded=excluded,
            escalation=escalation,
            rationale=rationale,
            generatedAt=now.strftime("%H:%M:%S"),
        )

    @classmethod
    def _escalation_ladder(
        cls,
        proposed: Optional[DispatchCandidate],
        deadline: DispatchDeadline,
        privilege: str,
        now: Optional[datetime] = None,
    ) -> List[str]:
        """
        A dispatcher that can fail must say what happens next. An unassigned
        emergency is never an acceptable resting state.
        """
        if proposed and proposed.meetsDeadline and not deadline.breached:
            return []

        ladder: List[str] = []
        if deadline.breached:
            ladder.append(
                f"{deadline.label} window already exceeded "
                f"({deadline.elapsedMinutes} min elapsed of {deadline.targetMinutes}). "
                "Senior review required on whether the pathway still applies."
            )
        if not proposed:
            ladder.append(f"No on-shift doctor holds '{privilege}' and is free.")
        elif not proposed.meetsDeadline:
            ladder.append(
                f"Best candidate reaches the patient in "
                f"{proposed.projectedMinutesToDoctor} min against "
                f"{deadline.remainingMinutes} min remaining."
            )

        on_call = [
            r["doctor"].fullName for r in doctor_service.roster(now)
            if r["duty"].onCall and privilege in r["doctor"].privileges
        ]
        if on_call:
            ladder.append("Page on-call: " + ", ".join(on_call) + ".")
        ladder.append("Escalate to the duty medical officer.")
        ladder.append("If still unmet, consider diversion to a centre with the capability.")
        return ladder

    @staticmethod
    def _rationale(
        proto: Dict[str, Any],
        deadline: DispatchDeadline,
        privilege: str,
        proposed: Optional[DispatchCandidate],
        feasible: List[DispatchCandidate],
    ) -> str:
        head = (
            f"{proto['condition']}: requires '{privilege}' within "
            f"{deadline.remainingMinutes} min ({deadline.label}, "
            f"{deadline.elapsedMinutes} min already elapsed)."
        )
        if not proposed:
            return head + " No feasible on-shift doctor; escalation required."
        tail = (
            f" Proposing {proposed.fullName} ({proposed.title}) -- reachable in "
            f"{proposed.projectedMinutesToDoctor} min, {len(feasible) - 1} "
            f"alternative(s) available."
        )
        if not proposed.meetsDeadline:
            tail += " Deadline is NOT met by any available doctor."
        return head + tail

    # --- Assignment ledger -----------------------------------------------
    #
    # Cases are assigned automatically and the receiving doctor accepts. A
    # third party approving each assignment would add latency to the most
    # time-critical path in the system, and an approval that is always granted
    # launders accountability rather than creating it. The doctor who accepts
    # owns the case, which is how clinical responsibility already works.

    # Response window before the offer falls through to the next candidate.
    URGENT_RESPONSE_SECONDS = 30       # acuity >= 4.5
    STANDARD_RESPONSE_SECONDS = 60

    _records: Dict[str, DispatchRecord] = {}

    @classmethod
    def _response_window(cls, acuity: float) -> int:
        return cls.URGENT_RESPONSE_SECONDS if acuity >= 4.5 else cls.STANDARD_RESPONSE_SECONDS

    @classmethod
    def _offer_to(
        cls, record: DispatchRecord, candidate: DispatchCandidate, now: datetime
    ) -> DispatchRecord:
        record.currentOffer = DispatchOffer(
            doctorId=candidate.doctorId,
            doctorName=candidate.fullName,
            offeredAt=now.isoformat(),
            respondBySeconds=cls._response_window(record.acuityWeight),
            reasoning=candidate.reasoning,
        )
        record.status = "pending"
        doctor_service.record_assignment(candidate.doctorId, record.acuityWeight)
        return record

    @classmethod
    def _next_candidate(
        cls, session: Any, record: DispatchRecord, now: datetime
    ) -> Optional[DispatchCandidate]:
        """
        Re-runs the policy rather than replaying a stale ranking -- by the time
        an offer is declined, shifts and loads have moved on. Doctors who have
        already declined this case are not offered it again.
        """
        proposal = cls.propose(session, now)
        for cand in ([proposal.proposed] if proposal.proposed else []) + proposal.alternatives:
            if cand.doctorId not in record.declinedDoctorIds:
                return cand
        return None

    @classmethod
    def _escalate(cls, record: DispatchRecord, session: Any, now: datetime) -> DispatchRecord:
        proposal = cls.propose(session, now)
        record.status = "escalated"
        record.currentOffer = None
        ladder = list(proposal.escalation)
        if record.declinedDoctorIds:
            ladder.insert(0, (
                f"{len(record.declinedDoctorIds)} doctor(s) declined or did not "
                f"respond; no further candidate holds '{record.requiredPrivilege}'."
            ))
        elif not ladder:
            ladder.append("No on-shift doctor could take this case.")
        record.escalation = ladder
        return record

    @classmethod
    def dispatch(cls, session: Any, now: Optional[datetime] = None) -> DispatchRecord:
        """
        Assigns the case automatically and offers it to the best candidate.
        Idempotent: an existing record is swept for expiry and returned.
        """
        now = now or clock.now()
        session_id = getattr(session, "sessionId", "")
        existing = cls._records.get(session_id)
        if existing is not None:
            return cls.sweep(session, now)

        proposal = cls.propose(session, now)
        record = DispatchRecord(
            sessionId=session_id,
            condition=proposal.condition,
            requiredPrivilege=proposal.requiredPrivilege,
            acuityWeight=proposal.acuityWeight,
            deadline=proposal.deadline,
            rationale=proposal.rationale,
        )
        cls._records[session_id] = record

        if proposal.proposed is None:
            return cls._escalate(record, session, now)
        return cls._offer_to(record, proposal.proposed, now)

    @classmethod
    def sweep(cls, session: Any, now: Optional[datetime] = None) -> DispatchRecord:
        """
        Expires an unanswered offer and moves to the next candidate.

        Expiry is evaluated lazily on read rather than by a background timer:
        with no scheduler in the process, a record is only ever observed through
        a read, so sweeping here gives the same result without a task loop.
        """
        now = now or clock.now()
        record = cls._records.get(getattr(session, "sessionId", ""))
        if record is None or record.status != "pending" or record.currentOffer is None:
            return record

        offered_at = datetime.fromisoformat(record.currentOffer.offeredAt)
        if (now - offered_at).total_seconds() < record.currentOffer.respondBySeconds:
            return record

        offer = record.currentOffer
        offer.status = "expired"
        offer.respondedAt = now.isoformat()
        record.history.append(offer)
        record.declinedDoctorIds.append(offer.doctorId)
        doctor_service.release_assignment(offer.doctorId)

        nxt = cls._next_candidate(session, record, now)
        if nxt is None:
            return cls._escalate(record, session, now)
        return cls._offer_to(record, nxt, now)

    @classmethod
    def accept(cls, session: Any, doctor: DoctorAccount,
               now: Optional[datetime] = None) -> DispatchRecord:
        now = now or clock.now()
        record = cls.sweep(session, now)
        if record is None:
            raise ValueError("No dispatch record for this session")
        if record.status == "accepted":
            raise ValueError(f"Already accepted by {record.acceptedByName}")
        if record.currentOffer is None or record.currentOffer.doctorId != doctor.doctorId:
            raise PermissionError("This case is not currently offered to you")

        offer = record.currentOffer
        offer.status = "accepted"
        offer.respondedAt = now.isoformat()
        record.history.append(offer)
        record.status = "accepted"
        record.acceptedByDoctorId = doctor.doctorId
        record.acceptedByName = doctor.fullName
        record.acceptedAt = now.strftime("%H:%M:%S")
        record.currentOffer = None
        record.escalation = []
        return record

    @classmethod
    def decline(cls, session: Any, doctor: DoctorAccount, reason: str,
                now: Optional[datetime] = None) -> DispatchRecord:
        now = now or clock.now()
        record = cls.sweep(session, now)
        if record is None:
            raise ValueError("No dispatch record for this session")
        if record.status == "accepted":
            raise ValueError(f"Already accepted by {record.acceptedByName}")
        if record.currentOffer is None or record.currentOffer.doctorId != doctor.doctorId:
            raise PermissionError("This case is not currently offered to you")

        offer = record.currentOffer
        offer.status = "declined"
        offer.declineReason = reason
        offer.respondedAt = now.isoformat()
        record.history.append(offer)
        record.declinedDoctorIds.append(doctor.doctorId)
        # The doctor told us something the roster did not know; free them again.
        doctor_service.release_assignment(doctor.doctorId)

        nxt = cls._next_candidate(session, record, now)
        if nxt is None:
            return cls._escalate(record, session, now)
        return cls._offer_to(record, nxt, now)

    @classmethod
    def record_for(cls, session_id: str) -> Optional[DispatchRecord]:
        return cls._records.get(session_id)

    @classmethod
    def offers_for_doctor(cls, doctor_id: str) -> List[DispatchRecord]:
        """Cases currently sitting on this doctor's screen awaiting a response."""
        return [
            r for r in cls._records.values()
            if r.status == "pending" and r.currentOffer
            and r.currentOffer.doctorId == doctor_id
        ]

    @classmethod
    def reset(cls) -> None:
        """Clears the ledger. Used by tests."""
        cls._records = {}


dispatch_service = DispatchService()
