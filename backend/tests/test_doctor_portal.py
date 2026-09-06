"""
Tests for the Doctor Portal:
- Doctor credential authentication and bearer token issue
- Token forgery rejection (no shape-based fallback)
- Duty roster with live shift windows, including overnight shifts
- Duty state reporting and interruptibility
- Assignment-candidate filtering by department, privilege and duty state
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.doctor_service import DoctorService

client = TestClient(app)

EMERGENCY_DOCTOR = "DOC-EMER-301"          # Dr. Imran Khan, shift 08:00-20:00
NIGHT_DOCTOR = "DOC-EMER-302"              # Dr. Maria D'Souza, shift 20:00-08:00


def _login(username="dr_khan", password="emerg123"):
    res = client.post("/api/doctor/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# --- Authentication ---------------------------------------------------------

def test_doctor_login_returns_profile_privileges_and_duty():
    data = _login()
    assert data["token"].startswith("doctok_")
    assert data["doctor"]["fullName"] == "Dr. Imran Khan"
    assert data["doctor"]["department"] == "Emergency"
    assert data["doctor"]["registrationNumber"] == "WBMC-38914"
    assert "thrombolysis" in data["doctor"]["privileges"]
    assert data["duty"]["doctorId"] == EMERGENCY_DOCTOR


def test_doctor_login_rejects_bad_credentials():
    assert client.post("/api/doctor/login",
                       json={"username": "dr_khan", "password": "wrong"}).status_code == 401
    assert client.post("/api/doctor/login",
                       json={"username": "nobody", "password": "emerg123"}).status_code == 401


def test_protected_routes_require_a_real_token():
    assert client.get("/api/doctor/me").status_code == 401
    # A token that merely looks right must not authenticate.
    assert client.get("/api/doctor/me",
                      headers=_auth_header("doctok_forged")).status_code == 401
    token = _login()["token"]
    assert client.get("/api/doctor/me", headers=_auth_header(token)).status_code == 200


def test_logout_invalidates_token():
    token = _login()["token"]
    assert client.get("/api/doctor/me", headers=_auth_header(token)).status_code == 200
    assert client.post("/api/doctor/logout", headers=_auth_header(token)).status_code == 200
    assert client.get("/api/doctor/me", headers=_auth_header(token)).status_code == 401


# --- Roster and shift windows ----------------------------------------------

def test_roster_lists_every_doctor_with_duty_state():
    token = _login()["token"]
    roster = client.get("/api/doctor/roster", headers=_auth_header(token)).json()
    assert len(roster) == len(DoctorService._PRE_REGISTERED_DOCTORS)
    for row in roster:
        assert row["doctor"]["doctorId"]
        assert row["duty"]["dutyState"] in {"available", "on_rounds", "in_procedure", "off_duty"}


@pytest.mark.parametrize("hour,minute,expected", [
    (7, 59, False), (8, 0, True), (15, 59, True), (16, 0, False),
])
def test_day_shift_window_boundaries(hour, minute, expected):
    assert DoctorService._within_shift(
        "08:00", "16:00", datetime(2026, 9, 4, hour, minute)) is expected


@pytest.mark.parametrize("hour,minute,expected", [
    (19, 59, False), (20, 0, True), (23, 59, True),
    (0, 30, True), (7, 59, True), (8, 0, False),
])
def test_overnight_shift_window_wraps_past_midnight(hour, minute, expected):
    assert DoctorService._within_shift(
        "20:00", "08:00", datetime(2026, 9, 4, hour, minute)) is expected


def test_doctor_off_shift_is_never_on_duty():
    svc = DoctorService()
    # 23:00 falls outside D'Souza's window only once she has handed over at 08:00,
    # so use the day doctor, who is definitively off shift at that hour.
    duty = svc.get_duty(EMERGENCY_DOCTOR, datetime(2026, 9, 4, 23, 0))
    assert duty.onShift is False
    assert duty.dutyState == "off_duty"

    night = svc.get_duty(NIGHT_DOCTOR, datetime(2026, 9, 4, 23, 0))
    assert night.onShift is True


# --- Duty state and assignment candidates ----------------------------------

def test_duty_state_controls_interruptibility():
    token = _login()["token"]
    res = client.post("/api/doctor/duty", json={"dutyState": "in_procedure"},
                      headers=_auth_header(token))
    assert res.status_code == 200
    assert res.json()["duty"]["interruptible"] is False

    res = client.post("/api/doctor/duty", json={"dutyState": "available"},
                      headers=_auth_header(token))
    assert res.json()["duty"]["interruptible"] is True


@pytest.mark.parametrize("state,idle_only,with_interrupted", [
    ("available",    True,  True),
    ("on_rounds",    False, True),   # busy but can be pulled out
    ("in_procedure", False, False),  # must not be interrupted
    ("off_duty",     False, False),  # stepped away; escalation ladder only
])
def test_candidate_filtering_by_duty_state(state, idle_only, with_interrupted):
    svc = DoctorService()
    noon = datetime(2026, 9, 4, 12, 0)
    svc.set_duty_state(EMERGENCY_DOCTOR, state)

    def khan_in(**kwargs):
        return any(d.doctorId == EMERGENCY_DOCTOR
                   for d in svc.available_doctors(privilege="thrombolysis", now=noon, **kwargs))

    assert khan_in() is idle_only
    assert khan_in(include_interrupted=True) is with_interrupted


def test_explicit_duty_state_is_cleared_at_shift_end():
    svc = DoctorService()
    noon, night = datetime(2026, 9, 4, 12, 0), datetime(2026, 9, 4, 23, 0)

    svc.set_duty_state(EMERGENCY_DOCTOR, "in_procedure")
    assert svc.get_duty(EMERGENCY_DOCTOR, noon).dutyState == "in_procedure"
    assert svc.get_duty(EMERGENCY_DOCTOR, night).dutyState == "off_duty"
    # Next shift starts clean rather than resuming a stale procedure flag.
    assert svc.get_duty(EMERGENCY_DOCTOR, noon).dutyState == "available"


# --- Protected clinical routes -------------------------------------------

PROTECTED_ROUTES = [
    ("get", "/api/physician/queue"),
    ("get", "/api/physician/session/session_seed_ramesh"),
    ("post", "/api/physician/session/session_seed_ramesh/save-record"),
    ("post", "/api/physician/session/session_seed_ramesh/clinical-decision-support"),
    ("get", "/api/emergency/queue"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_clinical_routes_reject_anonymous_callers(method, path):
    """These routes expose identifiable clinical records; none may be public."""
    assert getattr(client, method)(path).status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_clinical_routes_reject_forged_tokens(method, path):
    res = getattr(client, method)(path, headers=_auth_header("doctok_forged"))
    assert res.status_code == 401


def test_clinical_routes_accept_a_signed_in_doctor():
    token = _login()["token"]
    res = client.get("/api/physician/queue", headers=_auth_header(token))
    assert res.status_code == 200


def test_candidates_filtered_by_privilege_and_department():
    svc = DoctorService()
    noon = datetime(2026, 9, 4, 12, 0)

    cardiology = svc.available_doctors(department="Cardiology", now=noon)
    assert all(d.department == "Cardiology" for d in cardiology)

    cath = svc.available_doctors(privilege="cardiac_cath", now=noon)
    assert all("cardiac_cath" in d.privileges for d in cath)

    assert svc.available_doctors(privilege="not_a_real_privilege", now=noon) == []
