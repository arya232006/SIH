"""
Tests for Advanced Clinical Features:
- Drug-Drug & Herb-Drug Interaction (DDI) Safety Engine
- ESI & NEWS2 Acuity Triage Scoring
- Interactive Body Pain Map Assessment
- HL7 FHIR R4 Bundle Export
- Official OPD Electronic Prescription Generation
- Indian CDSCO Drug Phonetic Autocomplete
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ddi_and_safety_engine():
    # 1. Start Session
    res = client.post("/api/session/start", json={
        "fullName": "Mohua Dey",
        "age": 48,
        "gender": "Female",
        "language": "en",
        "ayushMode": True
    })
    assert res.status_code == 200
    s_id = res.json()["sessionId"]

    # 2. Attach Dr. A. Biswas Prescription with Azulix 2 (Glimepiride) and Low Fasting Sugar (69 mg/dL)
    doc_res = client.post(f"/api/session/{s_id}/document/sample/sample_dr_biswas_rx")
    assert doc_res.status_code == 200

    # 3. Request Safety Analysis
    safety_res = client.get(f"/api/session/{s_id}/safety-check")
    assert safety_res.status_code == 200
    safety_data = safety_res.json()

    assert safety_data["hasHighRiskAlerts"] is True
    # Verify hypoglycemia contraindication flagged
    contraindications = safety_data["contraindications"]
    assert any("HYPOGLYCEMIA WARNING" in c for c in contraindications)

    # 4. Test Standalone DDI Check for Aspirin + Ibuprofen
    standalone_res = client.post("/api/clinical/ddi-check", json={
        "drugs": ["Ecosprin 75mg", "Combiflam / Ibuprofen 400mg"]
    })
    assert standalone_res.status_code == 200
    alerts = standalone_res.json()["alerts"]
    assert len(alerts) > 0
    assert alerts[0]["severity"] == "high"


def test_triage_acuity_scoring():
    # 1. Start Session for routine patient
    res = client.post("/api/session/start", json={
        "fullName": "Rahul Sharma",
        "age": 32,
        "gender": "Male",
        "language": "en"
    })
    assert res.status_code == 200
    s_id = res.json()["sessionId"]

    triage_res = client.get(f"/api/session/{s_id}/triage")
    assert triage_res.status_code == 200
    triage_data = triage_res.json()
    assert triage_data["esiLevel"] in [3, 4, 5]
    assert triage_data["news2Score"] >= 0


def test_body_pain_map_assessment():
    res = client.post("/api/session/start", json={
        "fullName": "Mohua Dey",
        "age": 48,
        "gender": "Female",
        "language": "en"
    })
    s_id = res.json()["sessionId"]

    pain_payload = {
        "anatomicalRegion": "Lower Back (L-S Spine)",
        "side": "Bilateral",
        "painSeverityVAS": 8,
        "painCharacter": "Dull / Aching",
        "radiationPath": "Radiates down both legs to calves",
        "aggravatingFactors": "Worse on walking"
    }

    pain_res = client.post(f"/api/session/{s_id}/pain-map", json=pain_payload)
    assert pain_res.status_code == 200
    data = pain_res.json()
    assert data["status"] == "pain_assessment_saved"
    assert data["session"]["painAssessment"]["painSeverityVAS"] == 8
    # High pain VAS 8 elevates ESI to 2 (Emergent)
    assert data["triageScore"]["esiLevel"] == 2


def test_fhir_r4_bundle_export():
    res = client.post("/api/session/start", json={
        "fullName": "Amit Verma",
        "age": 45,
        "gender": "Male",
        "language": "en"
    })
    s_id = res.json()["sessionId"]

    client.post(f"/api/session/{s_id}/document/sample/sample_printed_rx")

    fhir_res = client.get(f"/api/session/{s_id}/fhir")
    assert fhir_res.status_code == 200
    bundle = fhir_res.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert bundle["total"] > 0

    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in resource_types
    assert "MedicationStatement" in resource_types


def test_prescription_generation():
    res = client.post("/api/session/start", json={
        "fullName": "Mohua Dey",
        "age": 48,
        "gender": "Female",
        "language": "en"
    })
    s_id = res.json()["sessionId"]

    rx_payload = {
        "hospitalName": "Apollo / MediKiosk Smart Care Hospital",
        "doctorName": "Dr. A. Biswas, MBBS",
        "doctorDepartment": "General Medicine & Endocrinology",
        "diagnoses": ["Type 2 Diabetes Mellitus", "Hypothyroidism"],
        "icd10Codes": ["E11.9", "E03.9"],
        "medications": [
            {
                "name": "Tab. Azulix 2 (Glimepiride 2mg)",
                "dosage": "1 tablet",
                "frequency": "Before breakfast & dinner",
                "duration": "30 days",
                "instructions": "Take before meals"
            },
            {
                "name": "Tab. Thyronorm 75mcg",
                "dosage": "1 tablet",
                "frequency": "Daily empty stomach",
                "duration": "30 days",
                "instructions": "Early morning with water"
            }
        ],
        "investigationsAdvised": ["Fasting Blood Sugar after 1 month", "TSH after 2 months"],
        "followUpDays": 30
    }

    rx_res = client.post(f"/api/session/{s_id}/prescription", json=rx_payload)
    assert rx_res.status_code == 200
    rx_data = rx_res.json()

    assert rx_data["prescriptionId"].startswith("RX-")
    assert len(rx_data["medications"]) == 2
    assert "qrVerificationUrl" in rx_data
    assert rx_data["followUpDays"] == 30


def test_drug_fuzzy_autocomplete():
    res = client.get("/api/clinical/drugs/suggest?q=zulix")
    assert res.status_code == 200
    suggestions = res.json()
    assert len(suggestions) > 0
    assert any("Azulix" in s["brand"] for s in suggestions)

