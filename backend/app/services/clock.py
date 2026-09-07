"""
Single source of "now" for shift and dispatch logic.

Rosters, shift windows and offer expiry are all time-dependent, so reading the
wall clock directly makes them untestable: the same assertion passes at 15:00
and fails at 23:00 because the doctor has gone off shift. Routing every read
through here lets tests freeze time to a known hour and keeps the behaviour
identical in production.

It also has to be the *hospital's* clock, not the server's. Shift windows like
"08:00-20:00" are hospital wall-clock times, but the container runs in UTC on
Render -- so at 09:54 in the hospital the server read 04:24, decided every
doctor on a daytime shift was off shift, and forced their duty state back to
off_duty however they set it. The portal then disabled every duty button except
"Off Duty", which is exactly what it looked like from the outside: a roster
that could not be changed.
"""
from datetime import datetime, timedelta, timezone

# India has a single time zone and observes no daylight saving, so a fixed
# offset is exact and avoids depending on tzdata being present in the image.
HOSPITAL_TZ = timezone(timedelta(hours=5, minutes=30))   # IST, UTC+05:30


def now() -> datetime:
    """
    Current hospital wall-clock time, as a naive datetime.

    Naive deliberately: shift windows are naive, and so is the clock the tests
    freeze. Returning an aware datetime here would raise on every comparison
    against them.
    """
    return datetime.now(HOSPITAL_TZ).replace(tzinfo=None)


def stamp(fmt: str = "%H:%M:%S") -> str:
    """Hospital-local timestamp for audit lines that a person will read."""
    return now().strftime(fmt)
