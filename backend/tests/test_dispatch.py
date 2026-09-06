"""
Tests for deadline-aware emergency dispatch:
- Red-flag text mapped to the right clinical protocol and deadline
- Stroke deadlines anchored to symptom onset, not arrival
- Hard constraints: privilege, shift, duty state, shift long enough to finish
- Reserve policy holding scarce specialists back
- Escalation ladder when no candidate meets the deadline
- Automatic assignment, accept/decline by the receiving doctor, route protection
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import PatientSession, RedFlag, HistoryOfPresentIllness
from app.services.dispatch_service import DispatchService
from app.services.doctor_service import DoctorService

client = TestClient(app)

# 15:00 puts Banerjee, Iyer, Khan and Sen on shift.
AFTERNOON = datetime(2026, 9, 4, 15, 0)

STEMI = "Potential Acute Coronary Syndrome Warning (Severe chest pain with left arm radiation)"
STROKE = "Potential Acute Stroke Warning (Sudden focal neurological deficit)"
ANAPHYLAXIS = "Severe Anaphylaxis / Airway Swelling Warning"


def make_session(reason: str, onset: str = "", session_id: str = "sess-1") -> PatientSession:
    s = PatientSession(sessionId=session_id, patientId="p", visitId="v",
                       tokenNumber="T1", patientName="Test Patient", age=58, gender="Male")
    s.redFlag = RedFlag(triggered=True, reason=reason, action="", urgency="emergency")
    s.historyOfPresentIllness = HistoryOfPresentIllness(onset=onset)
    return s


def doctor_auth(username="dr_khan", password="emerg123"):
    res = client.post("/api/doctor/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


# --- Protocol selection -----------------------------------------------------

@pytest.mark.parametrize("reason,condition_fragment,privilege,target", [
    (STEMI, "Acute Coronary Syndrome", "cardiac_cath", 90),
    (STROKE, "Stroke", "thrombolysis", 270),
    (ANAPHYLAXIS, "Anaphylaxis", "intubation", 10),
    ("Acute Active Hemorrhage Warning (Hematemesis)", "haemorrhage", "resuscitation", 15),
])
def test_red_flag_maps_to_clinical_protocol(reason, condition_fragment, privilege, target):
    proto = DispatchService.protocol_for(reason)
    assert condition_fragment.lower() in proto["condition"].lower()
    assert proto["privilege"] == privilege
    assert proto["deadlineMinutes"] == target


def test_unmatched_red_flag_falls_back_to_esi_target():
    urgent = DispatchService.protocol_for("Something not in the catalogue", esi_level=1)
    routine = DispatchService.protocol_for("Something not in the catalogue", esi_level=3)
    assert urgent["deadlineMinutes"] < routine["deadlineMinutes"]


# --- Onset-anchored deadlines ----------------------------------------------

@pytest.mark.parametrize("text,minutes", [
    ("2 hours ago", 120), ("30 minutes ago", 30), ("1 hr ago", 60),
    ("started 3 hours ago while walking", 180), ("just now", 0),
    ("", None), ("some time back", None),
])
def test_onset_parsing(text, minutes):
    assert DispatchService.parse_onset_minutes(text) == minutes


def test_stroke_deadline_counts_from_onset_not_arrival():
    """The thrombolysis clock starts before the patient reaches the kiosk."""
    fresh = DispatchService.propose(make_session(STROKE, "1 hour ago"), AFTERNOON)
    assert fresh.deadline.anchor == "onset"
    assert fresh.deadline.elapsedMinutes == 60
    assert fresh.deadline.remainingMinutes == 210
    assert fresh.deadline.breached is False

    late = DispatchService.propose(make_session(STROKE, "5 hours ago"), AFTERNOON)
    assert late.deadline.elapsedMinutes == 300
    assert late.deadline.breached is True


def test_stemi_deadline_counts_from_arrival():
    p = DispatchService.propose(make_session(STEMI), AFTERNOON)
    assert p.deadline.anchor == "arrival"
    assert p.deadline.elapsedMinutes == 0
    assert p.deadline.remainingMinutes == 90


def test_unknown_onset_is_flagged_rather_than_assumed():
    p = DispatchService.propose(make_session(STROKE, ""), AFTERNOON)
    assert p.deadline.elapsedMinutes == 0
    assert "not established" in p.deadline.basis


# --- Hard constraints -------------------------------------------------------

def test_proposal_only_offers_doctors_holding_the_privilege():
    p = DispatchService.propose(make_session(STROKE, "1 hour ago"), AFTERNOON)
    svc = DoctorService()
    for cand in [p.proposed] + p.alternatives:
        doctor = svc.get_doctor_by_id(cand.doctorId)
        assert p.requiredPrivilege in doctor.privileges


def test_doctor_is_excluded_when_shift_ends_before_case_could_finish():
    """A STEMI needs ~90 min; at 15:00 the only cath operator has 60 min left."""
    p = DispatchService.propose(make_session(STEMI), AFTERNOON)
    banerjee = next(c for c in p.excluded if c.doctorId == "DOC-CARD-201")
    assert "Shift ends" in banerjee.exclusionReason


def test_falls_back_to_wider_privilege_when_preferred_is_unusable():
    """No cath operator can take it, so thrombolysis is offered instead."""
    p = DispatchService.propose(make_session(STEMI), AFTERNOON)
    assert p.requiredPrivilege == "thrombolysis"
    assert p.proposed is not None


def test_doctor_in_procedure_is_never_proposed():
    import app.services.dispatch_service as mod
    svc = DoctorService()
    original, mod.doctor_service = mod.doctor_service, svc
    try:
        svc.set_duty_state("DOC-EMER-301", "in_procedure")
        p = DispatchService.propose(make_session(STROKE, "1 hour ago"), AFTERNOON)
        assert p.proposed.doctorId != "DOC-EMER-301"
        khan = next(c for c in p.excluded if c.doctorId == "DOC-EMER-301")
        assert "uninterruptible" in khan.exclusionReason
    finally:
        mod.doctor_service = original


# --- Reserve policy and load ------------------------------------------------

def test_scarce_specialist_is_held_in_reserve():
    """
    The only cath operator should carry a reserve penalty on a case that does
    not need cath, so an equally close colleague is preferred.
    """
    p = DispatchService.propose(make_session(STROKE, "1 hour ago"), AFTERNOON)
    banerjee = next((c for c in [p.proposed] + p.alternatives
                     if c.doctorId == "DOC-CARD-201"), None)
    assert banerjee is not None
    assert banerjee.scarcityPenalty > 0
    assert p.proposed.doctorId != "DOC-CARD-201"


def test_successive_cases_spread_across_the_roster():
    import app.services.dispatch_service as mod
    svc = DoctorService()
    original, mod.doctor_service = mod.doctor_service, svc
    try:
        picked = []
        for _ in range(3):
            p = DispatchService.propose(make_session(STROKE, "1 hour ago"), AFTERNOON)
            picked.append(p.proposed.doctorId)
            svc.record_assignment(p.proposed.doctorId, p.acuityWeight)
        assert len(set(picked)) == 3, f"load not spread: {picked}"
    finally:
        mod.doctor_service = original


# --- Escalation -------------------------------------------------------------

def test_breached_deadline_produces_an_escalation_ladder():
    p = DispatchService.propose(make_session(STROKE, "6 hours ago"), AFTERNOON)
    assert p.deadline.breached is True
    assert p.escalation, "a breached window must not resolve silently"
    joined = " ".join(p.escalation).lower()
    assert "duty medical officer" in joined
    assert "divers" in joined


def test_met_deadline_produces_no_escalation():
    p = DispatchService.propose(make_session(STROKE, "1 hour ago"), AFTERNOON)
    assert p.proposed.meetsDeadline is True
    assert p.escalation == []


def test_proposal_is_a_dry_run_and_creates_no_assignment():
    """/proposal previews the ranking; only /dispatch actually pages anyone."""
    DispatchService.reset()
    session = make_session(STROKE, "1 hour ago", session_id="preview-1")
    DispatchService.propose(session, AFTERNOON)
    assert DispatchService.record_for("preview-1") is None


# --- Endpoints --------------------------------------------------------------

def _emergency_session_id() -> str:
    """A seeded red-flagged session from the store."""
    queue = client.get("/api/emergency/queue", headers=doctor_auth()).json()
    assert queue, "expected at least one seeded red-flag session"
    return queue[0]["sessionId"]


def test_dispatch_endpoints_require_authentication():
    sid = _emergency_session_id()
    assert client.post(f"/api/dispatch/session/{sid}/dispatch").status_code == 401
    assert client.get(f"/api/dispatch/session/{sid}/proposal").status_code == 401
    assert client.post(f"/api/dispatch/session/{sid}/accept").status_code == 401
    assert client.post(f"/api/dispatch/session/{sid}/decline",
                       json={"reason": "busy"}).status_code == 401
    assert client.get("/api/doctor/inbox").status_code == 401
    assert client.get("/api/dispatch/benchmark").status_code == 401


def test_proposal_endpoint_returns_reasoning():
    sid = _emergency_session_id()
    res = client.get(f"/api/dispatch/session/{sid}/proposal", headers=doctor_auth())
    assert res.status_code == 200
    body = res.json()
    assert body["condition"]
    assert body["deadline"]["targetMinutes"] > 0
    assert body["rationale"]


def test_dispatch_assigns_automatically_without_human_approval():
    """No confirmation step: the case is paged the moment it is dispatched."""
    DispatchService.reset()
    sid = _emergency_session_id()
    res = client.post(f"/api/dispatch/session/{sid}/dispatch", headers=doctor_auth())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending"
    assert body["currentOffer"] is not None
    assert body["currentOffer"]["doctorId"]
    assert body["currentOffer"]["respondBySeconds"] > 0


def test_dispatch_is_idempotent():
    DispatchService.reset()
    sid = _emergency_session_id()
    headers = doctor_auth()
    first = client.post(f"/api/dispatch/session/{sid}/dispatch", headers=headers).json()
    second = client.post(f"/api/dispatch/session/{sid}/dispatch", headers=headers).json()
    assert first["currentOffer"]["doctorId"] == second["currentOffer"]["doctorId"]


def test_only_the_paged_doctor_may_accept():
    DispatchService.reset()
    sid = _emergency_session_id()
    record = client.post(f"/api/dispatch/session/{sid}/dispatch",
                         headers=doctor_auth()).json()
    paged = record["currentOffer"]["doctorId"]

    # Sign in as somebody who was not paged.
    others = {"DOC-EMER-301": ("dr_iyer", "cardio456")}
    username, password = others.get(paged, ("dr_khan", "emerg123"))
    wrong = doctor_auth(username, password)
    res = client.post(f"/api/dispatch/session/{sid}/accept", headers=wrong)
    assert res.status_code == 409
    assert "not currently offered" in res.json()["detail"].lower()


# --- Ledger lifecycle (unit level, isolated roster) ------------------------

def _stroke_session(sid="ledger-1"):
    return make_session(STROKE, "1 hour ago", session_id=sid)


def _isolated():
    """Fresh roster + ledger so assignment state cannot leak between tests."""
    import app.services.dispatch_service as mod
    svc = DoctorService()
    mod.doctor_service = svc
    DispatchService.reset()
    return svc, {d.doctorId: d for d in svc.doctors.values()}


def test_decline_rolls_to_the_next_candidate_and_keeps_the_reason():
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    first = rec.currentOffer.doctorId

    rec = DispatchService.decline(session, docs[first], "Scrubbed in", AFTERNOON)
    assert rec.currentOffer is not None
    assert rec.currentOffer.doctorId != first
    assert first in rec.declinedDoctorIds
    declined = [h for h in rec.history if h.status == "declined"]
    assert declined[0].declineReason == "Scrubbed in"


def test_a_doctor_who_declined_is_not_offered_the_case_again():
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    seen = []
    for _ in range(3):
        if rec.currentOffer is None:
            break
        did = rec.currentOffer.doctorId
        seen.append(did)
        rec = DispatchService.decline(session, docs[did], "unavailable", AFTERNOON)
    assert len(seen) == len(set(seen)), f"case re-offered to a decliner: {seen}"


def test_unanswered_offer_expires_and_rolls_onward():
    from datetime import timedelta
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    first = rec.currentOffer.doctorId
    window = rec.currentOffer.respondBySeconds

    # Still inside the window: nothing moves.
    same = DispatchService.sweep(session, AFTERNOON + timedelta(seconds=window - 1))
    assert same.currentOffer.doctorId == first

    later = DispatchService.sweep(session, AFTERNOON + timedelta(seconds=window + 1))
    assert later.currentOffer is None or later.currentOffer.doctorId != first
    assert any(h.status == "expired" for h in later.history)


def test_accept_locks_the_case_to_that_doctor():
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    paged = rec.currentOffer.doctorId

    rec = DispatchService.accept(session, docs[paged], AFTERNOON)
    assert rec.status == "accepted"
    assert rec.acceptedByDoctorId == paged
    assert rec.currentOffer is None

    with pytest.raises(ValueError):
        DispatchService.accept(session, docs[paged], AFTERNOON)


def test_a_doctor_cannot_accept_a_case_offered_to_someone_else():
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    paged = rec.currentOffer.doctorId
    other = next(d for d in docs if d != paged)
    with pytest.raises(PermissionError):
        DispatchService.accept(session, docs[other], AFTERNOON)


def test_exhausting_every_candidate_escalates_rather_than_stalling():
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    for _ in range(len(docs) + 1):
        if rec.currentOffer is None:
            break
        rec = DispatchService.decline(session, docs[rec.currentOffer.doctorId],
                                      "unavailable", AFTERNOON)
    assert rec.status == "escalated"
    assert rec.currentOffer is None
    assert rec.escalation, "an exhausted ledger must not resolve silently"


def test_declining_frees_the_doctor_again():
    """A decline is information the roster lacked; the load booked must come back off."""
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    paged = rec.currentOffer.doctorId
    assert svc.get_duty(paged, AFTERNOON).activeCaseCount == 1

    DispatchService.decline(session, docs[paged], "at another crash", AFTERNOON)
    assert svc.get_duty(paged, AFTERNOON).activeCaseCount == 0


def test_inbox_shows_only_cases_paged_to_that_doctor():
    svc, docs = _isolated()
    session = _stroke_session()
    rec = DispatchService.dispatch(session, AFTERNOON)
    paged = rec.currentOffer.doctorId

    assert len(DispatchService.offers_for_doctor(paged)) == 1
    other = next(d for d in docs if d != paged)
    assert DispatchService.offers_for_doctor(other) == []


# --- Benchmark --------------------------------------------------------------

def test_benchmark_compares_policies_on_the_same_arrival_stream():
    res = client.get("/api/dispatch/benchmark?cases=40&seed=7", headers=doctor_auth())
    assert res.status_code == 200
    results = {r["policy"]: r for r in res.json()["results"]}
    assert set(results) == {"first_available", "round_robin", "deadline_aware"}
    assert all(r["cases"] == 40 for r in results.values())


def test_deadline_aware_never_hands_over_mid_case():
    """
    The safety property the policy exists to guarantee: it will refuse a case
    rather than give it to a doctor whose shift ends before they could finish.
    """
    from app.services.dispatch_simulation import DispatchSimulation
    results = {r["policy"]: r for r in DispatchSimulation(seed=42).compare(count=60)}
    assert results["deadline_aware"]["handoverRisk"] == 0
    assert results["first_available"]["handoverRisk"] > 0
    assert results["round_robin"]["handoverRisk"] > 0


def test_deadline_aware_distributes_load_more_evenly():
    from app.services.dispatch_simulation import DispatchSimulation
    results = {r["policy"]: r for r in DispatchSimulation(seed=42).compare(count=60)}
    assert results["deadline_aware"]["loadSpread"] < results["first_available"]["loadSpread"]
    assert results["deadline_aware"]["p90TimeToDoctor"] <= results["round_robin"]["p90TimeToDoctor"]
