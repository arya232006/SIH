"""
Bed allocation policy.

The second organ on the shared substrate, and deliberately built the same way
as dispatch: hard constraints first, ranked policy second, reasoning attached,
and a human accountable at the point of consequence.

It is wired to nothing. It subscribes to `dispatch.accepted` on the event log
and reacts -- which is the whole argument for the substrate. Adding bed
management required no change to the dispatch service, the emergency endpoints,
or the kiosk. It joined the hospital by subscribing.

Beds are a genuinely constrained resource, so the interesting behaviour is what
happens when the right one is not free: escalate honestly rather than put a
resuscitation case on an observation trolley and call it solved.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services import clock

# Acuity a bed class can safely receive. A patient may occupy a bed rated above
# their acuity, never below it.
BED_CLASS_ACUITY = {
    "resus": 5.0,
    "trauma_bay": 5.0,
    "high_dependency": 4.0,
    "observation": 3.0,
    "general_ward": 2.0,
}


@dataclass
class Bed:
    bedId: str
    label: str
    bedClass: str
    zone: str
    occupiedBy: Optional[str] = None          # sessionId
    occupantName: Optional[str] = None
    since: Optional[str] = None
    condition: Optional[str] = None

    @property
    def isFree(self) -> bool:
        return self.occupiedBy is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bedId": self.bedId, "label": self.label, "bedClass": self.bedClass,
            "zone": self.zone, "isFree": self.isFree, "occupiedBy": self.occupiedBy,
            "occupantName": self.occupantName, "since": self.since,
            "condition": self.condition,
            "maxAcuity": BED_CLASS_ACUITY.get(self.bedClass, 0.0),
        }


@dataclass
class BedAllocation:
    sessionId: str
    status: str                                # assigned | waitlisted | released
    bedId: Optional[str] = None
    label: Optional[str] = None
    bedClass: Optional[str] = None
    requiredAcuity: float = 0.0
    reasoning: List[str] = field(default_factory=list)
    escalation: List[str] = field(default_factory=list)
    assignedAt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessionId": self.sessionId, "status": self.status, "bedId": self.bedId,
            "label": self.label, "bedClass": self.bedClass,
            "requiredAcuity": self.requiredAcuity, "reasoning": self.reasoning,
            "escalation": self.escalation, "assignedAt": self.assignedAt,
        }


class BedService:
    """Allocates beds in response to accepted emergency assignments."""

    _LAYOUT = [
        ("BED-RESUS-1", "Resuscitation Bay 1", "resus", "Red Zone"),
        ("BED-RESUS-2", "Resuscitation Bay 2", "resus", "Red Zone"),
        ("BED-TRAUMA-1", "Trauma Bay 1", "trauma_bay", "Red Zone"),
        ("BED-TRAUMA-2", "Trauma Bay 2", "trauma_bay", "Red Zone"),
        ("BED-HDU-1", "High Dependency 1", "high_dependency", "Amber Zone"),
        ("BED-HDU-2", "High Dependency 2", "high_dependency", "Amber Zone"),
        ("BED-OBS-1", "Observation 1", "observation", "Amber Zone"),
        ("BED-OBS-2", "Observation 2", "observation", "Amber Zone"),
        ("BED-OBS-3", "Observation 3", "observation", "Amber Zone"),
        ("BED-GEN-1", "General Ward 1", "general_ward", "Green Zone"),
        ("BED-GEN-2", "General Ward 2", "general_ward", "Green Zone"),
        ("BED-GEN-3", "General Ward 3", "general_ward", "Green Zone"),
    ]

    def __init__(self):
        self.beds: Dict[str, Bed] = {}
        self.allocations: Dict[str, BedAllocation] = {}
        self.reset()

    def reset(self) -> None:
        self.beds = {b[0]: Bed(bedId=b[0], label=b[1], bedClass=b[2], zone=b[3])
                     for b in self._LAYOUT}
        self.allocations = {}

    # --- Policy -----------------------------------------------------------

    def _candidates(self, required_acuity: float) -> List[Bed]:
        """
        Free beds rated for at least this acuity, least-capable first.

        Ordering matters as much as filtering: giving a moderate case the last
        resuscitation bay is how the next cardiac arrest finds nowhere to go.
        This is the same reserve reasoning the dispatcher applies to scarce
        privileges, applied to a scarce physical resource.
        """
        fit = [b for b in self.beds.values()
               if b.isFree and BED_CLASS_ACUITY.get(b.bedClass, 0.0) >= required_acuity]
        return sorted(fit, key=lambda b: BED_CLASS_ACUITY.get(b.bedClass, 0.0))

    def allocate(self, session_id: str, required_acuity: float,
                 patient_name: str = "", condition: str = "") -> BedAllocation:
        existing = self.allocations.get(session_id)
        if existing and existing.status == "assigned":
            return existing

        candidates = self._candidates(required_acuity)
        if not candidates:
            occupied = [b.label for b in self.beds.values()
                        if not b.isFree
                        and BED_CLASS_ACUITY.get(b.bedClass, 0.0) >= required_acuity]
            allocation = BedAllocation(
                sessionId=session_id, status="waitlisted",
                requiredAcuity=required_acuity,
                reasoning=[f"No free bed rated for acuity {required_acuity}."],
                escalation=[
                    f"All {len(occupied)} bed(s) at this level are occupied: "
                    f"{', '.join(occupied) or 'none configured'}.",
                    "Charge nurse to identify a step-down candidate.",
                    "If none, escalate to the duty medical officer for diversion.",
                ],
            )
            # Deliberately not down-grading to a lower-rated bed: putting a
            # resuscitation case on an observation trolley would clear the
            # queue while making the patient less safe.
            self.allocations[session_id] = allocation
            return allocation

        bed = candidates[0]
        bed.occupiedBy = session_id
        bed.occupantName = patient_name or None
        bed.since = clock.now().strftime("%H:%M:%S")
        bed.condition = condition or None

        allocation = BedAllocation(
            sessionId=session_id, status="assigned", bedId=bed.bedId,
            label=bed.label, bedClass=bed.bedClass, requiredAcuity=required_acuity,
            assignedAt=bed.since,
            reasoning=[
                f"{bed.label} is rated to acuity "
                f"{BED_CLASS_ACUITY.get(bed.bedClass, 0.0)}, case requires {required_acuity}.",
                f"Lowest-rated free bed that still fits, keeping "
                f"{len([b for b in self.beds.values() if b.isFree and BED_CLASS_ACUITY.get(b.bedClass, 0) > BED_CLASS_ACUITY.get(bed.bedClass, 0)])} "
                f"higher-acuity bed(s) free for what may arrive next.",
            ],
        )
        self.allocations[session_id] = allocation
        return allocation

    def release(self, session_id: str) -> Optional[BedAllocation]:
        allocation = self.allocations.get(session_id)
        if not allocation or not allocation.bedId:
            return None
        bed = self.beds.get(allocation.bedId)
        if bed:
            bed.occupiedBy = bed.occupantName = bed.since = bed.condition = None
        allocation.status = "released"
        return allocation

    def occupancy(self) -> Dict[str, Any]:
        total = len(self.beds)
        free = len([b for b in self.beds.values() if b.isFree])
        by_class: Dict[str, Dict[str, int]] = {}
        for bed in self.beds.values():
            row = by_class.setdefault(bed.bedClass, {"total": 0, "free": 0})
            row["total"] += 1
            row["free"] += 1 if bed.isFree else 0
        return {
            "totalBeds": total, "freeBeds": free,
            "occupancyPercent": round((total - free) / total * 100, 1) if total else 0.0,
            "byClass": by_class,
            "beds": [b.to_dict() for b in self.beds.values()],
        }

    # --- Event subscription ----------------------------------------------

    async def on_dispatch_accepted(self, event) -> None:
        """
        Reacts to a doctor accepting an emergency. Bed management was added
        without touching the dispatch service: it simply subscribes.
        """
        from app.services.event_log import event_log

        payload = event.payload or {}
        session_id = payload.get("sessionId") or event.sessionId
        if not session_id:
            return

        allocation = self.allocate(
            session_id=session_id,
            required_acuity=float(payload.get("acuityWeight", 4.0)),
            patient_name=payload.get("patientName", ""),
            condition=payload.get("condition", ""),
        )
        await event_log.emit(
            type="bed.assigned" if allocation.status == "assigned" else "bed.unavailable",
            payload={**allocation.to_dict(),
                     "patientName": payload.get("patientName", ""),
                     "condition": payload.get("condition", "")},
            actor="policy:bed_management",
            sessionId=session_id,
            causedBy=event.eventId,
        )

    async def on_record_completed(self, event) -> None:
        """Frees the bed when the visit closes."""
        from app.services.event_log import event_log

        session_id = (event.payload or {}).get("sessionId") or event.sessionId
        if not session_id:
            return
        released = self.release(session_id)
        if released:
            await event_log.emit(
                type="bed.released",
                payload=released.to_dict(),
                actor="policy:bed_management",
                sessionId=session_id,
                causedBy=event.eventId,
            )


bed_service = BedService()
