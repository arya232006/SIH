"""
Tests for the shared event substrate and the policies riding on it:
- Ordered, replayable append with causal links
- Subscription patterns, and one bad subscriber not taking the rest down
- Bed allocation as a subscriber, including the reserve ordering
- Honest waitlisting instead of down-grading a patient into an unsafe bed
- The end-to-end chain: a doctor accepts, a bed is allocated, nothing calls it
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.bed_service import BED_CLASS_ACUITY, BedService
from app.services.dispatch_service import DispatchService
from app.services.event_log import EventLog, event_log

client = TestClient(app)


def doctor_auth(username="dr_khan", password="emerg123"):
    res = client.post("/api/doctor/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture
def log():
    """A private, non-persisting log so tests never touch the shared DB."""
    return EventLog(persist=False)


# --- Append and replay ------------------------------------------------------

@pytest.mark.asyncio
async def test_events_are_appended_in_total_order(log):
    for i in range(3):
        await log.emit("test.thing", {"i": i})
    assert [e.sequence for e in log.all()] == [1, 2, 3]


@pytest.mark.asyncio
async def test_a_session_can_be_replayed_in_order(log):
    await log.emit("patient.registered", {"sessionId": "s1"})
    await log.emit("patient.registered", {"sessionId": "s2"})
    await log.emit("history.completed", {"sessionId": "s1"})
    story = log.for_session("s1")
    assert [e.type for e in story] == ["patient.registered", "history.completed"]


@pytest.mark.asyncio
async def test_causal_chain_answers_why_this_happened(log):
    a = await log.emit("redflag.raised", {"sessionId": "s1"})
    b = await log.emit("dispatch.offered", {"sessionId": "s1"}, causedBy=a.eventId)
    c = await log.emit("bed.assigned", {"sessionId": "s1"}, causedBy=b.eventId)
    chain = log.causal_chain(c.eventId)
    assert [e.type for e in chain] == [
        "redflag.raised", "dispatch.offered", "bed.assigned"]


# --- Subscription -----------------------------------------------------------

@pytest.mark.asyncio
async def test_subscription_patterns_match_exact_prefix_and_wildcard(log):
    seen = {"exact": 0, "prefix": 0, "all": 0}
    log.subscribe("bed.assigned", lambda e: seen.__setitem__("exact", seen["exact"] + 1))
    log.subscribe("bed.*", lambda e: seen.__setitem__("prefix", seen["prefix"] + 1))
    log.subscribe("*", lambda e: seen.__setitem__("all", seen["all"] + 1))

    await log.emit("bed.assigned", {})
    await log.emit("bed.released", {})
    await log.emit("dispatch.offered", {})
    assert seen == {"exact": 1, "prefix": 2, "all": 3}


@pytest.mark.asyncio
async def test_async_and_sync_subscribers_both_run(log):
    hits = []

    async def async_handler(event):
        hits.append("async")

    log.subscribe("*", lambda e: hits.append("sync"))
    log.subscribe("*", async_handler)
    await log.emit("test.thing", {})
    assert sorted(hits) == ["async", "sync"]


@pytest.mark.asyncio
async def test_one_failing_subscriber_does_not_stop_the_others(log):
    """A broken policy must not unwind the fact, or silence its peers."""
    survived = []

    def explodes(event):
        raise RuntimeError("policy is broken")

    log.subscribe("*", explodes)
    log.subscribe("*", lambda e: survived.append(e.type))

    await log.emit("redflag.raised", {})       # must not raise
    assert survived == ["redflag.raised"]
    assert len(log.all()) == 1                 # the fact was still recorded


# --- Bed allocation policy --------------------------------------------------

def test_a_case_never_gets_a_bed_rated_below_its_acuity():
    beds = BedService()
    allocation = beds.allocate("s1", required_acuity=5.0)
    assert allocation.status == "assigned"
    assert BED_CLASS_ACUITY[allocation.bedClass] >= 5.0


def test_lower_acuity_does_not_consume_a_resuscitation_bay():
    """
    The same reserve reasoning dispatch applies to scarce privileges: giving a
    moderate case the last resus bay is how the next arrest finds nowhere.
    """
    beds = BedService()
    allocation = beds.allocate("s1", required_acuity=2.0)
    assert allocation.bedClass == "general_ward"
    assert all(b.isFree for b in beds.beds.values() if b.bedClass == "resus")


def test_ward_full_waitlists_rather_than_down_grading():
    beds = BedService()
    high = [b for b in beds.beds.values() if BED_CLASS_ACUITY[b.bedClass] >= 5.0]
    for i, _ in enumerate(high):
        assert beds.allocate(f"filler-{i}", required_acuity=5.0).status == "assigned"

    overflow = beds.allocate("s-overflow", required_acuity=5.0)
    assert overflow.status == "waitlisted"
    assert overflow.bedId is None
    assert overflow.escalation, "a full ward must not resolve silently"
    # Crucially it did not put a resuscitation case on an observation trolley.
    assert all(b.isFree for b in beds.beds.values() if b.bedClass == "observation")


def test_releasing_a_bed_returns_it_to_the_pool():
    beds = BedService()
    allocation = beds.allocate("s1", required_acuity=5.0)
    bed_id = allocation.bedId
    assert beds.beds[bed_id].isFree is False

    beds.release("s1")
    assert beds.beds[bed_id].isFree is True
    assert beds.allocations["s1"].status == "released"


def test_allocating_twice_is_idempotent():
    beds = BedService()
    first = beds.allocate("s1", required_acuity=4.0)
    second = beds.allocate("s1", required_acuity=4.0)
    assert first.bedId == second.bedId


def test_occupancy_reports_by_class():
    beds = BedService()
    beds.allocate("s1", required_acuity=5.0)
    occupancy = beds.occupancy()
    assert occupancy["freeBeds"] == occupancy["totalBeds"] - 1
    assert "resus" in occupancy["byClass"]


# --- The substrate paying off ----------------------------------------------

def _accept_an_emergency(headers):
    """Dispatch a seeded red-flag case and accept it as whoever was paged."""
    session_id = client.get("/api/emergency/queue", headers=headers).json()[0]["sessionId"]
    record = client.post(f"/api/dispatch/session/{session_id}/dispatch",
                         headers=headers).json()
    paged = record["currentOffer"]["doctorId"]
    logins = {
        "DOC-EMER-301": ("dr_khan", "emerg123"),
        "DOC-EMER-302": ("dr_dsouza", "emerg456"),
        "DOC-CARD-201": ("dr_banerjee", "cardio123"),
        "DOC-CARD-202": ("dr_iyer", "cardio456"),
        "DOC-NEUR-310": ("dr_sen", "neuro123"),
        "DOC-GMED-101": ("dr_chandra", "genmed123"),
    }
    username, password = logins[paged]
    accepting = doctor_auth(username, password)
    client.post(f"/api/dispatch/session/{session_id}/accept", headers=accepting)
    return session_id


def test_accepting_an_emergency_allocates_a_bed_with_nothing_calling_it():
    """
    Bed management is wired to no caller. It subscribes to the fact that a
    doctor accepted a case -- which is the entire argument for the substrate.
    """
    headers = doctor_auth()
    assert "bed_management" in event_log.subscribers_for("emergency_dispatch_accepted")

    session_id = _accept_an_emergency(headers)

    res = client.get(f"/api/beds/session/{session_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "assigned"


def test_the_bed_event_records_what_caused_it():
    headers = doctor_auth()
    session_id = _accept_an_emergency(headers)

    events = client.get(f"/api/events?sessionId={session_id}", headers=headers).json()["events"]
    types = [e["type"] for e in events]
    assert "emergency_dispatch_accepted" in types
    assert "bed.assigned" in types

    bed_event = next(e for e in events if e["type"] == "bed.assigned")
    assert bed_event["actor"] == "policy:bed_management"
    assert bed_event["causedBy"], "an autonomous action must record its cause"


def test_event_endpoints_require_authentication():
    assert client.get("/api/events").status_code == 401
    assert client.get("/api/beds").status_code == 401


# --- One fact, several independent reactions --------------------------------

def _isolated_world():
    """Fresh roster, ledger and ward, wired to the live event log."""
    import app.services.dispatch_service as dmod
    from app.services.bed_service import bed_service
    from app.services.doctor_service import DoctorService
    svc = DoctorService()
    dmod.doctor_service = svc
    DispatchService.reset()
    bed_service.reset()
    event_log.reset()
    return svc


@pytest.mark.asyncio
async def test_doctor_going_off_duty_reoffers_their_unanswered_case():
    """
    The duty endpoint knows nothing about the dispatch ledger. Dispatch
    subscribes to the fact and reacts, so a case is never stranded with a
    doctor who has left.
    """
    from app.models import PatientSession, RedFlag, HistoryOfPresentIllness
    from app.store import session_store

    svc = _isolated_world()
    session = PatientSession(sessionId="cascade-1", patientId="p", visitId="v",
                             tokenNumber="T", patientName="Test", age=58, gender="Male")
    session.redFlag = RedFlag(triggered=True, action="", urgency="emergency",
                              reason="Potential Acute Stroke Warning (focal deficit)")
    session.historyOfPresentIllness = HistoryOfPresentIllness(onset="1 hour ago")
    session_store._sessions["cascade-1"] = session

    record = DispatchService.dispatch(session)
    paged = record.currentOffer.doctorId
    assert record.status == "pending"

    svc.set_duty_state(paged, "off_duty")
    await event_log.emit("doctor_duty_changed",
                         {"doctorId": paged, "dutyState": "off_duty",
                          "fullName": "Test Doctor"})

    after = DispatchService.record_for("cascade-1")
    assert paged in after.declinedDoctorIds
    if after.currentOffer:
        assert after.currentOffer.doctorId != paged
        assert any(e.type == "dispatch.reoffered" for e in event_log.all(200))
    else:
        assert after.status == "escalated"


@pytest.mark.asyncio
async def test_an_accepted_case_raises_a_handover_that_flags_the_bed():
    """Two hops: dispatch raises the handover, bed management reacts to it."""
    from app.models import PatientSession, RedFlag, HistoryOfPresentIllness
    from app.services.bed_service import bed_service
    from app.store import session_store

    svc = _isolated_world()
    session = PatientSession(sessionId="cascade-2", patientId="p", visitId="v",
                             tokenNumber="T", patientName="Test", age=58, gender="Male")
    session.redFlag = RedFlag(triggered=True, action="", urgency="emergency",
                              reason="Potential Acute Stroke Warning (focal deficit)")
    session.historyOfPresentIllness = HistoryOfPresentIllness(onset="1 hour ago")
    session_store._sessions["cascade-2"] = session

    record = DispatchService.dispatch(session)
    owner_id = record.currentOffer.doctorId
    owner = svc.get_doctor_by_id(owner_id)
    DispatchService.accept(session, owner)
    bed_service.allocate("cascade-2", required_acuity=5.0, patient_name="Test")

    svc.set_duty_state(owner_id, "off_duty")
    await event_log.emit("doctor_duty_changed",
                         {"doctorId": owner_id, "dutyState": "off_duty",
                          "fullName": owner.fullName})

    types = [e.type for e in event_log.all(200)]
    assert "dispatch.handover_required" in types
    assert "bed.handover_flagged" in types

    allocation = bed_service.allocations["cascade-2"]
    assert allocation.handoverRequired is True
    assert allocation.status == "assigned", "the patient is still in the bed"

    # The chain is traceable back to the single originating fact.
    flagged = next(e for e in event_log.all(200) if e.type == "bed.handover_flagged")
    chain = [e.type for e in event_log.causal_chain(flagged.eventId)]
    assert chain == ["doctor_duty_changed", "dispatch.handover_required",
                     "bed.handover_flagged"]


@pytest.mark.asyncio
async def test_the_roster_notices_when_a_capability_leaves_the_building():
    """
    Losing the last holder of a critical privilege is an operational emergency,
    not a rota gap. Nothing asks the roster to check; it subscribes.

    Uses the live singleton rather than an isolated roster, because the
    subscriber registered at startup is bound to that instance -- an isolated
    copy would be checked by nothing.
    """
    from app.services.doctor_service import doctor_service as live

    event_log.reset()
    original = dict(live._explicit_state)
    try:
        for row in live.roster():
            if row["duty"].onShift:
                live.set_duty_state(row["doctor"].doctorId, "off_duty")

        await event_log.emit("doctor_duty_changed",
                             {"doctorId": "DOC-EMER-301", "dutyState": "off_duty",
                              "fullName": "Dr. Imran Khan"})

        gap_events = [e for e in event_log.all(200)
                      if e.type == "roster.capability_gap"]
        assert gap_events, "the hospital lost every capability and said nothing"
        gaps = gap_events[0].payload["gaps"]
        assert any(g["privilege"] == "thrombolysis" for g in gaps)
        assert gap_events[0].actor == "policy:roster"
        # It also says who could be recalled, rather than only reporting a hole.
        assert any(g["recallCandidates"] for g in gaps)
    finally:
        for row in live.roster():
            live.set_duty_state(row["doctor"].doctorId, "available")
        live._explicit_state = original


def test_capability_gaps_are_empty_when_the_roster_is_covered():
    svc = _isolated_world()
    assert svc.capability_gaps() == [] or all(
        g["privilege"] not in ("thrombolysis", "acls") for g in svc.capability_gaps())


# --- OPD economics ----------------------------------------------------------

def test_kiosk_frees_doctor_time_per_patient():
    """The mechanism the whole project rests on, stated as a number."""
    from app.services.opd_simulation import OPDSimulation
    sim = OPDSimulation(seed=7)
    out = sim.compare(patients=1200, doctors=12)
    h = out["headline"]
    assert h["doctorMinutesPerPatientKiosk"] < h["doctorMinutesPerPatientBaseline"]
    assert h["costPerPatientKiosk"] < h["costPerPatientBaseline"]


def test_too_few_kiosks_makes_things_worse_and_says_so():
    """
    A model that always flatters the idea is worthless. With too few terminals
    the queue moves from the doctor's door to the kiosk and throughput falls
    below doing nothing -- the result must report that rather than hide it.
    """
    from app.services.opd_simulation import OPDSimulation
    sim = OPDSimulation(seed=7)
    starved = sim.compare(patients=1200, doctors=12, kiosks=2)
    assert starved["headline"]["intakeIsBottleneck"] is True
    assert starved["headline"]["additionalPatientsSeenPerDay"] < 0
    assert "too few kiosks" in starved["headline"]["note"].lower()


def test_capacity_curve_saturates_once_doctors_become_the_limit():
    from app.services.opd_simulation import OPDSimulation
    sim = OPDSimulation(seed=7)
    curve = sim.capacity_curve(1200, 12, max_kiosks=20)
    seen = [row["patientsSeen"] for row in curve]
    assert seen == sorted(seen), "adding kiosks must never reduce throughput"
    assert seen[-1] - seen[-2] < seen[1] - seen[0], "returns should diminish"


def test_nurse_desks_do_not_scale():
    """The problem statement's own argument, reproduced by the model."""
    from app.services.opd_simulation import OPDSimulation
    out = OPDSimulation(seed=7).compare(patients=1200, doctors=12)
    nurse = next(r for r in out["results"] if r["mode"] == "nurse_desk")
    kiosk = next(r for r in out["results"] if r["mode"] == "kiosk")
    assert nurse["patientsSeen"] < kiosk["patientsSeen"]
    assert nurse["costPerPatientSeen"] > kiosk["costPerPatientSeen"]


def test_assumptions_are_returned_so_they_can_be_challenged():
    from app.services.opd_simulation import OPDSimulation
    out = OPDSimulation().compare(patients=600, doctors=6)
    assert "doctorCostPerHour" in out["assumptions"]
    assert "kioskIntakeMinutes" in out["assumptions"]


def test_economics_endpoint_requires_authentication():
    assert client.get("/api/simulation/opd-economics").status_code == 401
