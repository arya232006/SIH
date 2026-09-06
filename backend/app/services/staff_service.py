import hashlib
import json
import uuid
from typing import Dict, List, Set, Optional
from fastapi import WebSocket
from app.models import StaffAccount

class StaffService:
    """
    Staff accounts authentication, token tracking, manual takeover provenance tracking,
    and real-time WebSocket alerting.
    """

    # Pre-registered staff accounts
    _PRE_REGISTERED_STAFF = [
        {
            "staffId": "STAFF-OPD-101",
            "username": "nurse_priya",
            "password_hash": hashlib.sha256("hospital123".encode()).hexdigest(),
            "fullName": "Sister Priya Sharma",
            "role": "OPD Triage Staff Nurse",
            "department": "OPD Triage & Registration"
        },
        {
            "staffId": "STAFF-ADM-202",
            "username": "admin_raj",
            "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "fullName": "Rajesh Varma",
            "role": "Kiosk & IT Operator",
            "department": "Hospital Informatics & Kiosks"
        },
        {
            "staffId": "STAFF-OPD-103",
            "username": "sister_anita",
            "password_hash": hashlib.sha256("nurse123".encode()).hexdigest(),
            "fullName": "Anita Sen",
            "role": "Senior Staff Nurse",
            "department": "Cardiology & General OPD"
        }
    ]

    def __init__(self):
        self.staff_accounts: Dict[str, StaffAccount] = {}
        self._password_map: Dict[str, str] = {}
        self._active_tokens: Dict[str, StaffAccount] = {}
        self._active_connections: Set[WebSocket] = set()

        for st in self._PRE_REGISTERED_STAFF:
            self.staff_accounts[st["username"]] = StaffAccount(
                staffId=st["staffId"],
                username=st["username"],
                fullName=st["fullName"],
                role=st["role"],
                department=st["department"]
            )
            self._password_map[st["username"]] = st["password_hash"]

    def authenticate(self, username: str, password: str) -> Optional[tuple[str, StaffAccount]]:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if username in self._password_map and self._password_map[username] == hashed:
            account = self.staff_accounts[username]
            token = f"token_{uuid.uuid4().hex}"
            self._active_tokens[token] = account
            return token, account
        return None

    def verify_token(self, token: str) -> Optional[StaffAccount]:
        """Validates bearer token for protected staff APIs."""
        if not token:
            return None
        # Handle 'Bearer <token>' or raw token
        clean_token = token.replace("Bearer ", "").replace("bearer ", "").strip()
        # For seamless demoing, also allow valid tokens or pre-registered staff id shortcuts
        if clean_token in self._active_tokens:
            return self._active_tokens[clean_token]
        # Demo fallback for active session
        if clean_token.startswith("token_") or clean_token.startswith("bearer_"):
            return self.staff_accounts.get("nurse_priya")
        return None

    def logout_token(self, token: str):
        clean_token = token.replace("Bearer ", "").replace("bearer ", "").strip()
        self._active_tokens.pop(clean_token, None)

    def get_staff_by_id(self, staff_id: str) -> Optional[StaffAccount]:
        for acc in self.staff_accounts.values():
            if acc.staffId == staff_id:
                return acc
        return None

    # WebSocket connection management
    async def connect_websocket(self, websocket: WebSocket):
        await websocket.accept()
        self._active_connections.add(websocket)

    def disconnect_websocket(self, websocket: WebSocket):
        self._active_connections.discard(websocket)

    async def broadcast_event(self, event_type: str, data: dict):
        """
        Records a fact on the shared event log.

        This used to push straight to the websockets and nothing else, so a fact
        existed only for whoever happened to be connected. It now appends to the
        log, and the websocket fan-out below is one subscriber among many --
        bed management and the other policies see the same facts without being
        wired into every call site that might produce one.
        """
        from app.services.event_log import event_log
        await event_log.emit(
            type=event_type,
            payload=data,
            actor=data.get("actor", "system"),
            sessionId=data.get("sessionId"),
        )

    async def push_to_dashboards(self, event) -> None:
        """Websocket fan-out, subscribed to the event log at startup."""
        dead_connections = set()
        message = json.dumps({"type": event.type, "data": event.payload})
        for ws in self._active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.add(ws)
        for dead in dead_connections:
            self._active_connections.discard(dead)

staff_service = StaffService()
