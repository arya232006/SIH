"""
Prescription scan tester.

Runs a prescription image (or a bundled sample) through the real extraction
pipeline and prints the medicines it found, with per-field confidence and which
fields the pipeline itself considers unreliable.

    python scan_prescription.py path/to/prescription.jpg
    python scan_prescription.py --sample sample_dr_biswas_rx
    python scan_prescription.py --list

Runs in-process against the FastAPI app, so the backend server does not need to
be running. Without a live GEMINI_API_KEY the Vision-LLM step is skipped and the
local fallback answers instead -- the header tells you which one you got, since
the two look identical in the output otherwise.
"""
import argparse
import os
import sys

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.ocr_service import ocr_service

client = TestClient(app)

BAR = "=" * 78


def _pct(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


def header():
    # Only Gemini has a vision branch in ocr_service. Groq and OpenRouter run
    # text-only models, so their keys cannot read a prescription image -- saying
    # "LLM configured" would be true and useless here.
    vision = bool(settings.GEMINI_API_KEY)
    print(BAR)
    print("MediKiosk prescription extraction")
    print(BAR)
    print(f"  provider        : {settings.LLM_PROVIDER}")
    print(f"  GEMINI (vision) : {'configured' if vision else 'NOT SET'}")
    print(f"  GROQ (text only): {'configured' if settings.GROQ_API_KEY else 'not set'}")
    if not vision:
        print()
        print("  Image OCR is UNAVAILABLE. Only Gemini can read a prescription;")
        print("  a Groq key powers the text paths but cannot see an image.")
        print("  Get a free key at https://aistudio.google.com/ and set")
        print("  GEMINI_API_KEY in backend/.env")
    print()


def start_session():
    res = client.post("/api/session/start", json={
        "fullName": "Prescription Scan Test", "age": 55,
        "gender": "Male", "language": "en",
    })
    res.raise_for_status()
    return res.json()["sessionId"]


def scan_file(session_id, path):
    if not os.path.exists(path):
        sys.exit(f"File not found: {path}")
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".pdf": "application/pdf"}.get(ext, "application/octet-stream")
    print(f"Uploading {name} ...\n")
    with open(path, "rb") as fh:
        res = client.post(f"/api/session/{session_id}/document/upload",
                          files={"file": (name, fh, mime)})
    res.raise_for_status()
    return res.json()


def scan_sample(session_id, sample_id):
    print(f"Loading bundled sample '{sample_id}' ...\n")
    res = client.post(f"/api/session/{session_id}/document/sample/{sample_id}")
    if res.status_code != 200:
        sys.exit(f"Sample failed [{res.status_code}]: {res.text[:300]}")
    return res.json()


def report(doc):
    if doc.get("extractionSource") == "extraction_failed":
        print(BAR)
        print("EXTRACTION FAILED -- nothing was read from this document.")
        print(BAR)
        print(f"  {doc.get('flag', '')}")
        print()
        print("  Check the uvicorn console for a [Vision LLM] line giving the")
        print("  reason (timeout, HTTP status, quota). No content is shown here")
        print("  because none was extracted.")
        return

    print(BAR)
    print(f"DOCUMENT : {doc.get('document')}")
    print(f"  type       : {doc.get('documentType')}")
    print(f"  source     : {doc.get('extractionSource')}")
    print(f"  confidence : {_pct(doc.get('confidence'))}"
          f"   quality: {doc.get('qualityAssessment')}"
          f"   cross-check: {doc.get('crossCheckStatus')}")
    if doc.get("flag"):
        print(f"  FLAG       : {doc['flag']}")
    print(BAR)

    meds = doc.get("medicationItems") or []
    if not meds:
        extracted = doc.get("extracted") or {}
        meds = extracted.get("medications") or []

    if not meds:
        print("\nNo medications extracted.")
    else:
        print(f"\nMEDICINES FOUND ({len(meds)})\n")
        for i, m in enumerate(meds, 1):
            if not isinstance(m, dict):
                print(f"  {i}. {m}")
                continue
            conf = m.get("confidence") or {}
            overall = conf.get("overall") if isinstance(conf, dict) else None
            status = m.get("status", "")
            mark = "  <-- NEEDS CLARIFICATION" if status in (
                "needs_clarification", "uncertain") else ""
            print(f"  {i}. {m.get('name', '?')}  {m.get('strength') or ''}".rstrip())
            bits = [("dose", m.get("dosage")), ("freq", m.get("frequency")),
                    ("duration", m.get("duration")), ("timing", m.get("timing"))]
            line = "   ".join(f"{k}: {v}" for k, v in bits if v)
            if line:
                print(f"      {line}")
            print(f"      confidence {_pct(overall)}   status: {status}{mark}")
            if m.get("unreliableFields"):
                print(f"      low-confidence fields: {', '.join(m['unreliableFields'])}")

            # Formulary grounding: is this a real product, at a real dose?
            vstatus = m.get("verificationStatus")
            if vstatus and vstatus != "not_checked":
                badge = {"verified": "[OK]", "corrected": "[FIXED]",
                         "unverified": "[UNKNOWN]"}.get(vstatus, "")
                generic = m.get("genericName")
                line = f"      {badge} formulary: {vstatus}"
                if generic:
                    line += f" -> {m.get('matchedBrand')} ({generic})"
                print(line)
                if m.get("strengthPlausible") is False:
                    print("      [!] strength is not a marketed dose for this product")
                for note in (m.get("verificationNotes") or []):
                    print(f"          {note}")
            print()

    extracted = doc.get("extracted") or {}
    for key, label in (("diagnoses", "DIAGNOSES"), ("investigations", "INVESTIGATIONS")):
        rows = extracted.get(key) or []
        if rows:
            print(f"{label} ({len(rows)})")
            for r in rows:
                print(f"  - {r if not isinstance(r, dict) else r}")
            print()


def main():
    ap = argparse.ArgumentParser(description="Scan a prescription and list its medicines.")
    ap.add_argument("image", nargs="?", help="path to a prescription image or PDF")
    ap.add_argument("--sample", help="use a bundled sample document instead")
    ap.add_argument("--list", action="store_true", help="list bundled samples and exit")
    args = ap.parse_args()

    if args.list:
        print("Bundled sample documents:\n")
        for sid, meta in ocr_service.SAMPLE_DOCS_METADATA.items():
            print(f"  {sid:24s} {meta.get('title', '')}")
        return

    if not args.image and not args.sample:
        ap.error("give an image path or --sample <id> (see --list)")

    header()
    session_id = start_session()
    doc = scan_sample(session_id, args.sample) if args.sample else scan_file(session_id, args.image)
    report(doc)

    safety = client.get(f"/api/session/{session_id}/safety-check")
    if safety.status_code == 200:
        body = safety.json()
        alerts = body.get("alerts") or []
        warnings = body.get("allergyWarnings") or []
        if alerts or warnings:
            print(BAR)
            print("DRUG SAFETY CHECK ON THE EXTRACTED MEDICINES")
            print(BAR)
            for w in warnings:
                print(f"  ! {w}")
            for a in alerts:
                print(f"  [{a.get('severity')}] {a.get('medication1')} + {a.get('medication2')}")
                print(f"      {a.get('mechanism', '')[:110]}")
            print()


if __name__ == "__main__":
    main()
