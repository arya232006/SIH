"""
Shared pytest configuration.

The suite must not depend on a live LLM. Several tests assert on the
deterministic question flow and the curated extraction paths -- they passed for
a long time only because the configured Gemini model had been retired and every
call 404'd, so the fallback always answered. The moment a working key was added
they became nondeterministic, and the suite slowed from ~50s to ~160s because it
was making real API calls.

Outbound model calls are therefore disabled by default. A test that genuinely
wants live behaviour can opt in with @pytest.mark.live_llm.
"""
from datetime import datetime

import pytest

from app.services import clock
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService

# Wednesday 15:00. Chosen so the seeded roster has several doctors on shift with
# overlapping privileges -- the interesting case for dispatch. Without freezing,
# any test reaching the API through datetime.now() passes in the afternoon and
# fails at night, when every day-shift doctor is correctly off duty.
FROZEN_NOW = datetime(2026, 9, 4, 15, 0, 0)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live_llm: allow this test to make real model API calls"
    )
    config.addinivalue_line(
        "markers", "real_clock: let this test read the actual wall clock"
    )


@pytest.fixture(autouse=True)
def clean_shared_state():
    """
    The event log and bed board are process-wide, so one test's admissions would
    otherwise fill the ward for the next.
    """
    from app.services.bed_service import bed_service
    from app.services.event_log import event_log
    event_log.reset()
    bed_service.reset()
    yield
    event_log.reset()
    bed_service.reset()


@pytest.fixture(autouse=True)
def frozen_clock(request, monkeypatch):
    """Pins shift and dispatch time so roster behaviour is reproducible."""
    if "real_clock" in request.keywords:
        yield
        return
    monkeypatch.setattr(clock, "now", lambda: FROZEN_NOW)
    yield


@pytest.fixture(autouse=True)
def no_live_llm(request, monkeypatch):
    """
    Routes every model call to the deterministic fallback, so results depend on
    our own logic rather than on a network round trip.
    """
    if "live_llm" in request.keywords:
        yield
        return

    async def _no_llm(*args, **kwargs):
        return None

    async def _no_vision(*args, **kwargs):
        # Same shape _extract_with_vision_llm returns when it cannot answer.
        return ({}, 0.0, "other", None, "local_ocr_fallback")

    monkeypatch.setattr(LLMService, "_call_llm_provider", classmethod(_no_llm))
    monkeypatch.setattr(OCRService, "_extract_with_vision_llm", classmethod(_no_vision))
    yield
