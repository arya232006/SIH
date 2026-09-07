"""
Whole-day OPD simulation: what the kiosk is actually worth.

"More efficient and cheaper" is an adjective until someone puts a number on it.
This runs a full outpatient day -- thousands of arrivals against a fixed number
of doctors -- under three configurations, and reports the difference in doctor
time, patient waiting and rupees.

  baseline        every history taken by the doctor inside the consultation
  nurse_desk      nurse-led history desks ahead of the doctor, the usual fix
  kiosk           self-service intake, the doctor reads a prepared summary

The comparison is like-for-like: identical arrival stream, identical doctors,
only the intake mechanism changes.

Every figure here is a modelled projection from stated assumptions, not a
measurement. The assumptions are declared in ASSUMPTIONS below so they can be
argued with -- which is the point. Change them and the numbers move.
"""
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List

# --- Assumptions ------------------------------------------------------------
# Sourced where possible; the rest are conservative estimates, deliberately so.
ASSUMPTIONS: Dict[str, Any] = {
    "consultationMinutesTotal": 5.0,      # PS cites 2-5; the optimistic end
    "historyMinutesInConsult": 3.0,       # of which history-taking
    "historyMinutesWithSummary": 0.7,     # reading a prepared summary instead
    "kioskIntakeMinutes": 6.0,            # patient's own time, not the doctor's
    "nurseDeskMinutes": 4.0,              # nurse time per patient
    "doctorCostPerHour": 1200.0,          # INR, government tertiary consultant
    "nurseCostPerHour": 350.0,            # INR, staff nurse
    "kioskCapitalCost": 85000.0,          # INR per terminal
    "kioskLifespanMonths": 36,
    "kioskRunningCostPerDay": 40.0,       # power, connectivity, maintenance
    "cloudCostPerIntake": 0.9,            # INR, vision + speech per patient
    "workingDaysPerMonth": 25,
    "opdHoursPerDay": 8.0,
}


@dataclass
class DayResult:
    mode: str
    patients: int = 0
    seen: int = 0
    unseen: int = 0
    waits: List[float] = field(default_factory=list)
    doctorMinutesUsed: float = 0.0
    nurseMinutesUsed: float = 0.0
    kiosksUsed: int = 0

    def summary(self, a: Dict[str, Any]) -> Dict[str, Any]:
        waits = sorted(self.waits)
        doctor_cost = (self.doctorMinutesUsed / 60.0) * a["doctorCostPerHour"]
        nurse_cost = (self.nurseMinutesUsed / 60.0) * a["nurseCostPerHour"]
        kiosk_cost = 0.0
        if self.kiosksUsed:
            per_day = (a["kioskCapitalCost"] /
                       (a["kioskLifespanMonths"] * a["workingDaysPerMonth"]))
            kiosk_cost = self.kiosksUsed * (per_day + a["kioskRunningCostPerDay"])
            kiosk_cost += self.seen * a["cloudCostPerIntake"]
        total = doctor_cost + nurse_cost + kiosk_cost
        return {
            "mode": self.mode,
            "patientsArrived": self.patients,
            "patientsSeen": self.seen,
            "patientsTurnedAway": self.unseen,
            "medianWaitMinutes": round(statistics.median(waits), 1) if waits else None,
            "p90WaitMinutes": round(waits[int(len(waits) * 0.9)], 1) if waits else None,
            "doctorHoursUsed": round(self.doctorMinutesUsed / 60.0, 1),
            "nurseHoursUsed": round(self.nurseMinutesUsed / 60.0, 1),
            "doctorCost": round(doctor_cost),
            "staffCost": round(nurse_cost),
            "kioskCost": round(kiosk_cost),
            "totalCost": round(total),
            "costPerPatientSeen": round(total / self.seen, 2) if self.seen else None,
        }


class OPDSimulation:
    """Discrete-event model of one outpatient day."""

    def __init__(self, seed: int = 7, assumptions: Dict[str, Any] = None):
        self.seed = seed
        self.a = {**ASSUMPTIONS, **(assumptions or {})}

    def _arrivals(self, count: int) -> List[float]:
        """
        Arrival minutes across the session. Indian OPD queues are famously
        front-loaded -- most of the day's patients are already waiting when the
        doors open -- so this is not a flat distribution.
        """
        rng = random.Random(self.seed)
        span = self.a["opdHoursPerDay"] * 60
        return sorted(min(span - 1, abs(rng.gauss(0, span / 3.2))) for _ in range(count))

    def _doctor_minutes_per_patient(self, mode: str) -> float:
        a = self.a
        base = a["consultationMinutesTotal"] - a["historyMinutesInConsult"]
        if mode == "baseline":
            return a["consultationMinutesTotal"]
        # A prepared history still has to be read and confirmed; it is not free.
        return base + a["historyMinutesWithSummary"]

    def run(self, mode: str, patients: int, doctors: int, kiosks: int = 0) -> DayResult:
        a = self.a
        result = DayResult(mode=mode, patients=patients,
                           kiosksUsed=kiosks if mode == "kiosk" else 0)
        per_patient = self._doctor_minutes_per_patient(mode)
        session_end = a["opdHoursPerDay"] * 60

        # Each doctor is a server; free_at is when they next become available.
        free_at = [0.0] * doctors
        # Intake capacity ahead of the doctor: nurse desks or kiosk terminals.
        intake_free: List[float] = []
        intake_minutes = 0.0
        if mode == "nurse_desk":
            intake_free = [0.0] * max(1, doctors // 3)   # one desk per 3 doctors
            intake_minutes = a["nurseDeskMinutes"]
        elif mode == "kiosk":
            intake_free = [0.0] * max(1, kiosks)
            intake_minutes = a["kioskIntakeMinutes"]

        for arrival in self._arrivals(patients):
            ready = arrival
            if intake_free:
                # Intake happens before the doctor and can queue in its own right.
                i = min(range(len(intake_free)), key=lambda k: intake_free[k])
                start = max(arrival, intake_free[i])
                intake_free[i] = start + intake_minutes
                ready = intake_free[i]
                if mode == "nurse_desk":
                    result.nurseMinutesUsed += intake_minutes

            d = min(range(len(free_at)), key=lambda k: free_at[k])
            start = max(ready, free_at[d])
            if start >= session_end:
                result.unseen += 1
                continue
            free_at[d] = start + per_patient
            result.doctorMinutesUsed += per_patient
            result.seen += 1
            result.waits.append(start - arrival)
        return result

    def kiosks_needed(self, patients: int, doctors: int) -> int:
        """
        Enough terminals that intake is not the bottleneck.

        Worth stating plainly: kiosks only help if there are enough of them. Too
        few and the queue simply moves from the doctor's door to the kiosk, and
        throughput falls below doing nothing at all -- the simulation shows that
        clearly, which is more useful than a model that always flatters the
        idea.
        """
        a = self.a
        session = a["opdHoursPerDay"] * 60
        doctor_capacity = (doctors * session) / self._doctor_minutes_per_patient("kiosk")
        target = min(patients, doctor_capacity)
        return max(1, int(-(-(target * a["kioskIntakeMinutes"]) // session)))

    def compare(self, patients: int = 1200, doctors: int = 12,
                kiosks: int = None) -> Dict[str, Any]:
        if kiosks is None:
            kiosks = self.kiosks_needed(patients, doctors)

        rows = [
            self.run("baseline", patients, doctors).summary(self.a),
            self.run("nurse_desk", patients, doctors).summary(self.a),
            self.run("kiosk", patients, doctors, kiosks).summary(self.a),
        ]
        baseline, nurse, kiosk = rows

        # Comparing total daily cost across modes that served different numbers
        # of patients is meaningless -- serving fewer people is always cheaper.
        # Cost per patient SEEN is the only honest unit, and the throughput
        # difference is reported separately rather than folded into a saving.
        intake_bound = kiosk["patientsTurnedAway"] > baseline["patientsTurnedAway"]

        saving_per_patient = None
        annual_saving = None
        payback = None
        if baseline["costPerPatientSeen"] and kiosk["costPerPatientSeen"]:
            saving_per_patient = round(
                baseline["costPerPatientSeen"] - kiosk["costPerPatientSeen"], 2)
            if saving_per_patient > 0:
                annual = (saving_per_patient * kiosk["patientsSeen"]
                          * self.a["workingDaysPerMonth"] * 12)
                annual_saving = round(annual)
                capital = kiosks * self.a["kioskCapitalCost"]
                payback = round(capital / (annual / 12.0), 1) if annual > 0 else None

        return {
            "assumptions": self.a,
            "scenario": {"patients": patients, "doctors": doctors, "kiosks": kiosks},
            "results": rows,
            "headline": {
                "patientsSeenBaseline": baseline["patientsSeen"],
                "patientsSeenKiosk": kiosk["patientsSeen"],
                "additionalPatientsSeenPerDay":
                    kiosk["patientsSeen"] - baseline["patientsSeen"],
                "doctorMinutesPerPatientBaseline":
                    round(self._doctor_minutes_per_patient("baseline"), 2),
                "doctorMinutesPerPatientKiosk":
                    round(self._doctor_minutes_per_patient("kiosk"), 2),
                "costPerPatientBaseline": baseline["costPerPatientSeen"],
                "costPerPatientNurseDesk": nurse["costPerPatientSeen"],
                "costPerPatientKiosk": kiosk["costPerPatientSeen"],
                "savingPerPatientRupees": saving_per_patient,
                "annualSavingRupees": annual_saving,
                "paybackMonths": payback,
                "intakeIsBottleneck": intake_bound,
                "note": ("Too few kiosks: intake is now the constraint and "
                         "throughput fell below baseline." if intake_bound else
                         "Kiosk count is sufficient; doctors remain the constraint."),
            },
        }

    def capacity_curve(self, patients: int, doctors: int,
                       max_kiosks: int = 16) -> List[Dict[str, Any]]:
        """How many kiosks are worth buying before the doctors become the limit."""
        curve = []
        for k in range(2, max_kiosks + 1, 2):
            row = self.run("kiosk", patients, doctors, k).summary(self.a)
            curve.append({"kiosks": k, "patientsSeen": row["patientsSeen"],
                          "medianWaitMinutes": row["medianWaitMinutes"],
                          "costPerPatientSeen": row["costPerPatientSeen"]})
        return curve


opd_simulation = OPDSimulation()
