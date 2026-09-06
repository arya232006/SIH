"""
Tests for formulary grounding of extracted medications:
- Name normalisation that survives brands whose names contain real digits
- Phonetic and fuzzy matching of misread Indian brand names
- Strength plausibility against what a brand is actually marketed in
- Downgrading unverified readings instead of presenting them as read
- Brand -> generic normalisation so the DDI rules can see brand-only entries
"""
import pytest

from app.models import PatientSession, DrugAllergyHistory
from app.services.ddi_service import DDIService
from app.services.formulary_service import (
    FormularyService, normalise_name, phonetic_key, parse_strength,
)
from app.services.medication_clarification_service import MedicationClarificationService

F = FormularyService()


# --- Normalisation ----------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Tab Telma 40", "Telma"),
    ("Tab. Azulix 2", "Azulix"),
    ("Cap Trinerve", "Trinerve"),
    ("Augmentin 625", "Augmentin"),
    ("Pan 40", "Pan"),
    ("Thyronorm 75mcg", "Thyronorm"),
])
def test_dose_form_and_trailing_strength_are_stripped(raw, expected):
    assert normalise_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Uprise-D3 60K", "Uprise-D3"),   # the 3 belongs to the name
    ("Telma AM", "Telma AM"),
    ("Zerodol-SP", "Zerodol-SP"),
    ("Glycomet GP 1", "Glycomet GP"),
])
def test_digits_that_belong_to_the_brand_survive(raw, expected):
    assert normalise_name(raw) == expected


# --- Strength parsing -------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("60,000 IU", (60000.0, "iu")),
    ("60K IU", (60000.0, "iu")),
    ("2.5 mg", (2.5, "mg")),
    ("75 mcg", (75.0, "mcg")),
    ("1 g", (1000.0, "mg")),      # normalised to mg for comparison
    ("no numbers here", None),
])
def test_strength_parsing_handles_commas_decimals_and_k(text, expected):
    assert parse_strength(text) == expected


# --- Matching ---------------------------------------------------------------

def test_exact_brand_is_verified_not_merely_corrected():
    for name in ["Tab Telma 40", "Pan 40", "Augmentin 625", "Ecosprin"]:
        assert F.verify(name).status == "verified", name


@pytest.mark.parametrize("misread,expected_generic", [
    ("Telmisatan", "Telmisartan"),   # dropped letter
    ("Zerodal", "Aceclofenac"),      # vowel swap
    ("Thyronom", "Levothyroxine"),   # dropped letter
])
def test_misread_names_are_corrected_to_real_products(misread, expected_generic):
    result = F.verify(misread)
    assert result.status == "corrected"
    assert result.generic == expected_generic


def test_phonetic_key_groups_indian_transliteration_variants():
    assert phonetic_key("Cifran") == phonetic_key("Siphran")
    assert phonetic_key("Zerodol") == phonetic_key("Serodol")


@pytest.mark.parametrize("misread,expected_generic", [
    ("Telmisatan", "Telmisartan"),
    ("Pantoprazol", "Pantoprazole"),
    ("Levothyroxin", "Levothyroxine"),
])
def test_misread_generic_names_are_corrected(misread, expected_generic):
    """Prescriptions are written in generics as often as brands."""
    result = F.verify(misread)
    assert result.status == "corrected"
    assert result.generic == expected_generic


@pytest.mark.parametrize("name,must_not_match", [
    ("Cremalax", "Cremaffin"),   # different laxatives, 5 shared leading letters
    ("Azee", "Azulix"),
    ("Losar", "Losacar"),
    ("Telma", "Telsartan"),
])
def test_distinct_products_are_never_merged(name, must_not_match):
    """
    Rewriting one real drug into a different real drug is worse than returning
    nothing: it feeds the wrong generic to the interaction rules. A shared
    leading substring alone must not justify a correction.
    """
    assert F.verify(name).matchedBrand != must_not_match


def test_a_drug_that_does_not_exist_is_not_invented():
    result = F.verify("Xyzomite Forte", "10mg")
    assert result.status == "unverified"
    assert result.generic is None
    assert result.notes


# --- Strength plausibility --------------------------------------------------

def test_impossible_strength_is_flagged_on_a_real_brand():
    result = F.verify("Telma", "400mg")     # marketed at 20/40/80
    assert result.status == "verified"
    assert result.strengthKnown is False
    assert any("not a marketed strength" in n for n in result.notes)


def test_marketed_strength_passes():
    assert F.verify("Telma", "40mg").strengthKnown is True
    assert F.verify("Uprise-D3", "60,000 IU").strengthKnown is True


def test_brand_with_no_listed_strengths_is_not_judged():
    assert F.verify("Trinerve").strengthKnown is None


# --- Pipeline integration ---------------------------------------------------

def _normalise(meds, doc_type="handwritten_prescription"):
    return MedicationClarificationService.normalize_extracted_medications(
        meds, doc_type, 0.85)


def test_verified_medication_carries_its_generic_through_the_pipeline():
    items = _normalise([{"name": "Tab Telma 40", "dosage": "40mg",
                         "frequency": "OD", "duration": "30 days"}])
    assert items[0].verificationStatus == "verified"
    assert items[0].genericName == "Telmisartan"
    assert items[0].drugClass == "ARB"


def test_unverified_medication_is_downgraded_not_presented_as_read():
    items = _normalise([{"name": "Tab Xyzomite Forte", "dosage": "10mg"}])
    item = items[0]
    assert item.verificationStatus == "unverified"
    assert item.status == "needs_clarification"
    assert "medicine" in item.unreliableFields
    assert item.confidence.medicine <= 0.45


def test_impossible_strength_downgrades_the_strength_field():
    items = _normalise([{"name": "Tab Telma", "dosage": "400mg"}])
    item = items[0]
    assert item.strengthPlausible is False
    assert item.status == "needs_clarification"
    assert "strength" in item.unreliableFields


# --- The payoff: DDI sees brand-only prescriptions --------------------------

def _safety(meds, allergy="NKDA"):
    session = PatientSession(sessionId="t", patientId="p", visitId="v",
                             tokenNumber="T", patientName="T", age=55, gender="Male")
    session.drugAllergyHistory = DrugAllergyHistory(currentMedications=meds,
                                                    allergies=allergy)
    return DDIService.evaluate_session_safety(session)


@pytest.mark.parametrize("meds", [
    ["Tab Telma 40", "Tab Aldactone 25"],       # ARB + spironolactone
    ["Tab Ecosprin 75", "Tab Combiflam"],       # aspirin + NSAID
    ["Tab Storvas 10", "Tab Fenolip 145"],      # statin + fibrate
    ["Tab Azulix 2", "Tab Metolar 50"],         # sulfonylurea + beta blocker
])
def test_brand_only_prescriptions_now_trigger_interaction_rules(meds):
    """These were all silent before: the rules are written in generic names."""
    assert _safety(meds).alerts, f"no interaction detected for {meds}"


def test_brand_only_allergy_contraindication_fires():
    result = _safety(["Tab Augmentin 625"], "Allergic to Penicillin")
    assert result.allergyWarnings


def test_a_drug_is_never_paired_with_itself():
    """Brand and generic naming the same product must not look like two drugs."""
    assert _safety(["Tab Telma 40", "Telmisartan 40mg"]).alerts == []


def test_unknown_drugs_do_not_break_the_safety_sweep():
    result = _safety(["Tab Xyzomite Forte", "Tab Telma 40"])
    assert result is not None


# --- Upload format handling -------------------------------------------------

def test_image_type_is_read_from_bytes_not_the_client_label():
    """
    Phone browsers and scanner apps mislabel uploads or omit the type entirely,
    and the vision API rejects a wrong MIME outright -- which surfaced as an
    unreadable prescription rather than a bad header.
    """
    import io
    from PIL import Image
    from app.services.ocr_service import OCRService

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="JPEG")
    jpeg = buf.getvalue()

    for lie in ["application/octet-stream", "image/png", "image/jpg", ""]:
        assert OCRService.sniff_image_mime(jpeg, "scan", lie) == "image/jpeg"


@pytest.mark.parametrize("fmt,expected", [
    ("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp"),
    ("BMP", "image/bmp"), ("TIFF", "image/tiff"), ("GIF", "image/gif"),
])
def test_common_image_formats_are_identified(fmt, expected):
    import io
    from PIL import Image
    from app.services.ocr_service import OCRService

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format=fmt)
    assert OCRService.sniff_image_mime(buf.getvalue(), "scan", "") == expected


@pytest.mark.parametrize("fmt", ["BMP", "TIFF", "GIF"])
def test_formats_the_vision_api_rejects_are_converted_not_dropped(fmt):
    """A patient should not have to care what their scanner app produced."""
    import io
    from PIL import Image
    from app.services.ocr_service import OCRService

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format=fmt)
    _, mime = OCRService.prepare_image_for_vision(buf.getvalue(), "scan", "")
    assert mime in OCRService.VISION_MIME_TYPES


def test_supported_formats_are_passed_through_unchanged():
    """No needless re-encoding, which would cost quality on handwriting."""
    import io
    from PIL import Image
    from app.services.ocr_service import OCRService

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="JPEG")
    original = buf.getvalue()
    out, mime = OCRService.prepare_image_for_vision(original, "rx.jpg", "image/jpeg")
    assert out == original and mime == "image/jpeg"


def test_iphone_heic_is_recognised():
    """iPhones shoot HEIC by default; it must not be guessed as PNG."""
    from app.services.ocr_service import OCRService
    heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00" + b"\x00" * 32
    assert OCRService.sniff_image_mime(heic, "IMG_0001.HEIC", "") == "image/heic"
