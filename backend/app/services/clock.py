"""
Single source of "now" for shift and dispatch logic.

Rosters, shift windows and offer expiry are all time-dependent, so reading the
wall clock directly makes them untestable: the same assertion passes at 15:00
and fails at 23:00 because the doctor has gone off shift. Routing every read
through here lets tests freeze time to a known hour and keeps the behaviour
identical in production.
"""
from datetime import datetime


def now() -> datetime:
    return datetime.now()
