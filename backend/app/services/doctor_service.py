"""
Doctor identity, credentials, privileges and duty-roster service for MediKiosk.

Separate from StaffService: nurses and kiosk operators run triage and takeover,
while doctors consult, attest records and receive emergency assignments. Emergency
dispatch needs more than a name -- it needs to know who is on shift, what they are
privileged to do, and whether they can be interrupted right now.
"""
import hashlib
import uuid
from datetime import datetime

from app.services import clock
from typing import Dict, List, Optional, Tuple

from app.models import DoctorAccount, DoctorDutyStatus, DutyState


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class DoctorService:
    """Authenticates doctors and tracks their duty state for assignment."""

    # Pre-registered doctors. Names and rooms mirror routing_service.DEPARTMENT_DIRECTORY
    # so automated routing and the doctor roster refer to the same people. Cardiology and
    # Emergency intentionally carry more than one doctor -- a dispatcher with a single
    # candidate per specialty has nothing to decide.
    _PRE_REGISTERED_DOCTORS = [
        {
            "doctorId": "DOC-CARD-201", "username": "dr_banerjee", "password": "cardio123",
            "fullName": "Dr. A. K. Banerjee", "title": "Senior Interventional Cardiologist",
            "department": "Cardiology", "departmentCode": "CARDIO",
            "registrationNumber": "WBMC-41207",
            "privileges": ["cardiac_cath", "thrombolysis", "acls", "echocardiography"],
            "roomNumber": "Room 204", "floorLocation": "First Floor (West Wing - Heart Institute)",
            "shiftStart": "08:00", "shiftEnd": "16:00", "onCall": False,
        },
        {
            "doctorId": "DOC-CARD-202", "username": "dr_iyer", "password": "cardio456",
            "fullName": "Dr. Lakshmi Iyer", "title": "Consultant Cardiologist",
            "department": "Cardiology", "departmentCode": "CARDIO",
            "registrationNumber": "WBMC-52883",
            "privileges": ["thrombolysis", "acls", "echocardiography"],
            "roomNumber": "Room 206", "floorLocation": "First Floor (West Wing - Heart Institute)",
            "shiftStart": "14:00", "shiftEnd": "22:00", "onCall": True,
        },
        {
            "doctorId": "DOC-EMER-301", "username": "dr_khan", "password": "emerg123",
            "fullName": "Dr. Imran Khan", "title": "Emergency Medicine Officer",
            "department": "Emergency", "departmentCode": "EMERG",
            "registrationNumber": "WBMC-38914",
            "privileges": ["acls", "atls", "intubation", "thrombolysis", "resuscitation"],
            "roomNumber": "ER Bay-1", "floorLocation": "Ground Floor (Emergency Trauma Center)",
            "shiftStart": "08:00", "shiftEnd": "20:00", "onCall": False,
        },
        {
            "doctorId": "DOC-EMER-302", "username": "dr_dsouza", "password": "emerg456",
            "fullName": "Dr. Maria D'Souza", "title": "Casualty Medical Officer",
            "department": "Emergency", "departmentCode": "EMERG",
            "registrationNumber": "WBMC-60142",
            "privileges": ["acls", "atls", "intubation", "resuscitation"],
            "roomNumber": "ER Bay-2", "floorLocation": "Ground Floor (Emergency Trauma Center)",
            "shiftStart": "20:00", "shiftEnd": "08:00", "onCall": False,
        },
        {
            "doctorId": "DOC-NEUR-310", "username": "dr_sen", "password": "neuro123",
            "fullName": "Dr. Debabrata Sen", "title": "Senior Consultant Neurologist",
            "department": "Neurology", "departmentCode": "NEURO",
            "registrationNumber": "WBMC-29551",
            "privileges": ["thrombolysis", "stroke_protocol", "eeg_interpretation"],
            "roomNumber": "Room 310", "floorLocation": "Second Floor (East Wing - Neurosciences)",
            "shiftStart": "09:00", "shiftEnd": "17:00", "onCall": True,
        },
        {
            "doctorId": "DOC-GMED-101", "username": "dr_chandra", "password": "genmed123",
            "fullName": "Dr. Subhash Chandra", "title": "Senior Consultant Physician",
            "department": "General_Medicine", "departmentCode": "GEN_MED",
            "registrationNumber": "WBMC-19022",
            "privileges": ["acls", "general_medicine"],
            "roomNumber": "Room 101", "floorLocation": "Ground Floor (Main Central OPD Wing)",
            "shiftStart": "08:00", "shiftEnd": "16:00", "onCall": False,
        },
        {
            "doctorId": "DOC-PEDI-105", "username": "dr_sengupta", "password": "pedia123",
            "fullName": "Dr. Ananya Sengupta", "title": "Senior Consultant Pediatrician",
            "department": "Pediatrics", "departmentCode": "PEDIA",
            "registrationNumber": "WBMC-44730",
            "privileges": ["pals", "neonatal_resuscitation"],
            "roomNumber": "Room 105", "floorLocation": "Ground Floor (West Wing - Children OPD)",
            "shiftStart": "09:00", "shiftEnd": "17:00", "onCall": False,
        },
        {
            "doctorId": "DOC-AYUS-001", "username": "vaidya_sharma", "password": "ayush123",
            "fullName": "Vaidya Raghavan Sharma", "title": "Ayurvedic Physician (BAMS, MD Ayu)",
            "department": "AYUSH_Ayurveda", "departmentCode": "AYUSH",
            "registrationNumber": "CCIM-AY-7741",
            "privileges": ["panchakarma", "ayurvedic_consultation"],
            "roomNumber": "AYUSH-01", "floorLocation": "Ground Floor (AYUSH Holistic Care Annex)",
            "shiftStart": "09:00", "shiftEnd": "15:00", "onCall": False,
        },
    ]

    def __init__(self):
        self.doctors: Dict[str, DoctorAccount] = {}          # username -> account
        self._password_map: Dict[str, str] = {}              # username -> sha256
        self._active_tokens: Dict[str, DoctorAccount] = {}   # token -> account
        self._duty: Dict[str, DoctorDutyStatus] = {}         # doctorId -> duty
        self._shift_windows: Dict[str, Tuple[str, str]] = {}  # doctorId -> (start, end)
        # Doctors who have reported their own state this shift. Without this we cannot
        # tell "on shift, has not said anything yet" from "on shift, stepped away" --
        # and would keep handing emergencies to someone who marked themselves off duty.
        self._explicit_state: Dict[str, bool] = {}

        for d in self._PRE_REGISTERED_DOCTORS:
            account = DoctorAccount(
                doctorId=d["doctorId"],
                username=d["username"],
                fullName=d["fullName"],
                title=d["title"],
                department=d["department"],
                departmentCode=d["departmentCode"],
                registrationNumber=d["registrationNumber"],
                privileges=d["privileges"],
                roomNumber=d["roomNumber"],
                floorLocation=d["floorLocation"],
            )
            self.doctors[d["username"]] = account
            self._password_map[d["username"]] = _hash(d["password"])
            self._shift_windows[d["doctorId"]] = (d["shiftStart"], d["shiftEnd"])
            self._duty[d["doctorId"]] = DoctorDutyStatus(
                doctorId=d["doctorId"],
                shiftStart=d["shiftStart"],
                shiftEnd=d["shiftEnd"],
                onCall=d["onCall"],
            )

    # --- Authentication -------------------------------------------------

    def authenticate(self, username: str, password: str) -> Optional[Tuple[str, DoctorAccount]]:
        hashed = _hash(password)
        if self._password_map.get(username) == hashed:
            account = self.doctors[username]
            token = f"doctok_{uuid.uuid4().hex}"
            self._active_tokens[token] = account
            return token, account
        return None

    def verify_token(self, token: str) -> Optional[DoctorAccount]:
        """
        Validates a bearer token. Only tokens actually issued by authenticate()
        are accepted -- there is deliberately no prefix-shaped fallback, since a
        token whose shape alone grants access is not authentication.
        """
        if not token:
            return None
        clean = token.replace("Bearer ", "").replace("bearer ", "").strip()
        return self._active_tokens.get(clean)

    def logout_token(self, token: str) -> None:
        clean = token.replace("Bearer ", "").replace("bearer ", "").strip()
        self._active_tokens.pop(clean, None)

    def get_doctor_by_id(self, doctor_id: str) -> Optional[DoctorAccount]:
        for acc in self.doctors.values():
            if acc.doctorId == doctor_id:
                return acc
        return None

    # --- Duty roster ----------------------------------------------------

    @staticmethod
    def _within_shift(start: str, end: str, now: Optional[datetime] = None) -> bool:
        """True if `now` falls inside the shift, handling windows that cross midnight."""
        if not start or not end:
            return False
        now = now or clock.now()
        try:
            sh, sm = (int(x) for x in start.split(":"))
            eh, em = (int(x) for x in end.split(":"))
        except ValueError:
            return False
        cur = now.hour * 60 + now.minute
        s, e = sh * 60 + sm, eh * 60 + em
        if s == e:
            return True
        return s <= cur < e if s < e else (cur >= s or cur < e)

    def get_duty(self, doctor_id: str, now: Optional[datetime] = None) -> Optional[DoctorDutyStatus]:
        duty = self._duty.get(doctor_id)
        if duty is None:
            return None
        start, end = self._shift_windows.get(doctor_id, ("", ""))
        duty.onShift = self._within_shift(start, end, now)
        if not duty.onShift:
            # Shift end overrides any self-reported state, and clears it so the
            # next shift starts from a clean slate.
            duty.dutyState = "off_duty"
            self._explicit_state.pop(doctor_id, None)
        elif not self._explicit_state.get(doctor_id):
            # On shift and nothing reported yet -- assume available.
            duty.dutyState = "available"
        duty.interruptible = duty.dutyState != "in_procedure"
        return duty

    def set_duty_state(self, doctor_id: str, state: DutyState,
                       now: Optional[datetime] = None) -> Optional[DoctorDutyStatus]:
        duty = self._duty.get(doctor_id)
        if duty is None:
            return None
        duty.dutyState = state
        duty.interruptible = state != "in_procedure"
        self._explicit_state[doctor_id] = True
        return self.get_duty(doctor_id, now)

    def record_assignment(self, doctor_id: str, acuity_weight: float = 1.0) -> Optional[DoctorDutyStatus]:
        """
        Books a case against a doctor. acuityLoad is cumulative and weighted, so
        fairness is measured in effort rather than headcount -- three crashes is
        not the same shift as three sore throats.
        """
        duty = self._duty.get(doctor_id)
        if duty is None:
            return None
        duty.activeCaseCount += 1
        duty.acuityLoad = round(duty.acuityLoad + float(acuity_weight), 2)
        return duty

    def release_assignment(self, doctor_id: str) -> Optional[DoctorDutyStatus]:
        """Closes a case. Cumulative acuityLoad is kept -- it is a shift total."""
        duty = self._duty.get(doctor_id)
        if duty is None:
            return None
        duty.activeCaseCount = max(0, duty.activeCaseCount - 1)
        return duty

    def roster(self, now: Optional[datetime] = None) -> List[Dict]:
        """Full roster with live duty state, for the dispatcher and the portal."""
        out = []
        for acc in self.doctors.values():
            out.append({"doctor": acc, "duty": self.get_duty(acc.doctorId, now)})
        return out

    def available_doctors(
        self,
        department: Optional[str] = None,
        privilege: Optional[str] = None,
        include_interrupted: bool = False,
        now: Optional[datetime] = None,
    ) -> List[DoctorAccount]:
        """
        Candidates for assignment: on shift, and holding the required privilege.
        `include_interrupted` also returns doctors mid-task but interruptible,
        which the dispatcher needs when nobody is idle and a deadline is close.
        """
        found = []
        for acc in self.doctors.values():
            if department and acc.department != department:
                continue
            if privilege and privilege not in acc.privileges:
                continue
            duty = self.get_duty(acc.doctorId, now)
            if not duty or not duty.onShift:
                continue
            if duty.dutyState == "off_duty":
                # On shift but stepped away. Not a dispatch candidate at any urgency;
                # reaching them is the escalation ladder's job, not routine assignment.
                continue
            if duty.dutyState == "available" or (include_interrupted and duty.interruptible):
                found.append(acc)
        return found


doctor_service = DoctorService()
