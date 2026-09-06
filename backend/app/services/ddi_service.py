"""
Drug-Drug Interaction (DDI), Contraindication, and Ayush Herb-Drug Safety Engine for MediKiosk.
Cross-checks active patient medications, diagnosed conditions, and vital biomarkers
against CDSCO, NLEM, and Integrative Medicine safety guidelines.
"""
from typing import List, Dict, Any, Optional, Tuple
import re
from app.models import (
    DrugInteractionAlert, SafetyCheckResponse, PatientSession,
    PatientVitals, PriorInvestigation
)

class DDIService:
    """
    Evaluates potential Drug-Drug, Herb-Drug, and Clinical Contraindications.
    """

    # --- Standard Clinical DDI Rule Database ---
    KNOWN_DDI_RULES = [
        {
            "pair": (r"(azulix|glimepiride|gliclazide|glibenclamide|sulfonylurea)", r"(atenolol|metoprolol|propranolol|beta.*blocker)"),
            "severity": "high",
            "type": "drug_drug",
            "mechanism": "Beta-blockers can mask early sympathetic warning signs of hypoglycemia (tachycardia, tremors) induced by sulfonylureas.",
            "recommendation": "Instruct patient on non-adrenergic hypoglycemia signs (sweating, hunger). Consider switching to DPP-4i or SGLT2i if hypoglycemic episodes occur."
        },
        {
            "pair": (r"(azulix|glimepiride|gliclazide|insulin)", r"low_blood_sugar"),
            "severity": "high",
            "type": "contraindication",
            "mechanism": "Active Sulfonylurea/Insulin therapy in the presence of low fasting sugar (< 70 mg/dL) creates high risk of severe neuroglycopenia or hypoglycemic coma.",
            "recommendation": "Immediate reduction in sulfonylurea dose required. Advise immediate fast-acting oral glucose and frequent SMBG monitoring."
        },
        {
            "pair": (r"(aspirin|ecosprin|ecospirin|clopidogrel|warfarin|apixaban|dabigatran|blood.*thinner)", r"(ibuprofen|combiflam|diclofenac|voveran|naproxen|etoricoxib|nsaid)"),
            "severity": "high",
            "type": "drug_drug",
            "mechanism": "Concurrent NSAIDs and antiplatelet/anticoagulant therapy exponentially increases the risk of major Upper GI bleeding and mucosal ulceration.",
            "recommendation": "Avoid non-selective NSAIDs. If analgesia is mandatory, prescribe Paracetamol or add a gastroprotective PPI (Pantoprazole/Rabeprazole)."
        },
        {
            "pair": (r"(atorvastatin|atorva|rosuvastatin|rosuvas|simvastatin)", r"(fenolip|stanlip|fenofibrate|gemfibrozil)"),
            "severity": "moderate",
            "type": "drug_drug",
            "mechanism": "Co-administration of statins and fibrates increases the risk of skeletal muscle toxicity, severe myopathy, and rhabdomyolysis.",
            "recommendation": "Use lowest effective doses. Monitor baseline and periodic Serum Creatine Kinase (CPK). Counsel patient to report unexplained muscle pain/weakness immediately."
        },
        {
            "pair": (r"(telmisartan|losartan|olmesartan|enalapril|ramipril|arb|acei)", r"(spironolactone|eplerenone|aldactone|potassium)"),
            "severity": "moderate",
            "type": "drug_drug",
            "mechanism": "Dual inhibition of renin-angiotensin-aldosterone system promotes potassium retention, leading to hyperkalemia and cardiac dysrhythmias.",
            "recommendation": "Check Serum Potassium and Renal Function (Creatinine/eGFR) within 1-2 weeks of initiation. Advise low potassium diet."
        },
        {
            "pair": (r"(amoxicillin|augmentin|amoxyclav|penicillin|ampicillin)", r"(penicillin.*allergy|amoxicillin.*allergy)"),
            "severity": "high",
            "type": "contraindication",
            "mechanism": "History of documented Penicillin / Beta-lactam allergy carries severe risk of Type 1 IgE-mediated anaphylaxis and bronchospasm.",
            "recommendation": "Strict contraindication. Substitute with Macrolides (Azithromycin) or Fluoroquinolones (Levofloxacin)."
        },
        {
            "pair": (r"(ciprofloxacin|cipro|levofloxacin|norfloxacin)", r"(antacid|digene|gelusil|calcium|sucralfate|iron)"),
            "severity": "minor",
            "type": "drug_drug",
            "mechanism": "Divalent and trivalent cations chelate fluoroquinolones, drastically reducing oral bioavailability and antibiotic efficacy.",
            "recommendation": "Separate administration by at least 2 hours before or 4 hours after taking antacids or iron/calcium supplements."
        }
    ]

    # --- Integrative Ayush Herb-Drug Interaction Matrix ---
    HERB_DRUG_RULES = [
        {
            "pair": (r"(guggulu|yogaraj.*guggulu|lasuna|garlic|ginger|zingiber)", r"(aspirin|ecospirin|clopidogrel|warfarin|blood.*thinner)"),
            "severity": "herb_drug",
            "type": "herb_drug",
            "mechanism": "Guggulu and concentrated Allium sativum (Lasuna) possess intrinsic platelet-aggregation inhibitory properties that potentiate allopathic anticoagulants.",
            "recommendation": "Monitor for subcutaneous bruising, epistaxis, or bleeding gums. Advise INR / bleeding time monitoring."
        },
        {
            "pair": (r"(ashwagandha|withania.*somnifera)", r"(thyronorm|eltroxin|levothyroxine)"),
            "severity": "herb_drug",
            "type": "herb_drug",
            "mechanism": "Ashwagandha stimulates endogenous thyroid gland synthesis (increases T3/T4), potentially causing additive thyrotoxic symptoms when taken with Levothyroxine.",
            "recommendation": "Monitor Serum TSH at 6 weeks. Patient may require a downward adjustment of Levothyroxine dosage."
        },
        {
            "pair": (r"(yashtimadhu|licorice|mulethi|glycyrrhiza)", r"(telmisartan|amlodipine|enalapril|atenolol|anti.*hypertensive)"),
            "severity": "herb_drug",
            "type": "herb_drug",
            "mechanism": "Glycyrrhizin inhibits 11-beta-HSD2 enzyme, leading to pseudoaldosteronism, sodium/water retention, hypokalemia, and elevated blood pressure.",
            "recommendation": "Avoid chronic high-dose licorice extracts in hypertensive patients. Monitor BP and electrolytes regularly."
        },
        {
            "pair": (r"(shankhpushpi|convolvulus|brahmi|bacopa)", r"(phenytoin|carbamazepine|levetiracetam|antiepileptic)"),
            "severity": "herb_drug",
            "type": "herb_drug",
            "mechanism": "Shankhpushpi may alter hepatic CYP450 metabolism or plasma protein binding of classic antiepileptic drugs, affecting seizure threshold.",
            "recommendation": "Maintain consistent administration timing and monitor therapeutic drug plasma levels if seizure frequency changes."
        },
        {
            "pair": (r"(karela|momordica|gurmar|gymnema|vijaysar)", r"(azulix|glimepiride|metformin|insulin|ondero)"),
            "severity": "herb_drug",
            "type": "herb_drug",
            "mechanism": "Additive hypoglycemic action between plant polypeptide-p / gymnemic acids and allopathic antidiabetic agents.",
            "recommendation": "Advise patient to monitor morning fasting sugar regularly to prevent unexpected hypoglycemia episodes."
        }
    ]

    @classmethod
    def evaluate_session_safety(cls, session: Any) -> SafetyCheckResponse:
        """
        Scans a complete patient session for DDI, contraindications, and herb-drug alerts.
        """
        def _get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        extracted_drugs: List[str] = []
        allergy_obj = _get_val(session, "drugAllergyHistory") or {}
        # DrugAllergyHistory exposes `allergies` / `currentMedications`; reading
        # `hasAllergy` / `details` here always fell back to the defaults, which left
        # allergy_text empty and made every allergy check below unreachable.
        allergy_text = str(_get_val(allergy_obj, "allergies", "") or "").lower()

        # 1. Collect all extracted & amended medications
        # (a) Medications the patient reported during the kiosk conversation.
        for med in (_get_val(allergy_obj, "currentMedications", None) or []):
            name = med if isinstance(med, str) else _get_val(med, "name", "")
            if name:
                extracted_drugs.append(str(name))

        # (b) Medications extracted from uploaded prescriptions and reports.
        prior_docs = _get_val(session, "priorInvestigations") or []
        for doc in prior_docs:
            extracted = _get_val(doc, "extracted")
            if extracted and isinstance(extracted, dict) and "medications" in extracted:
                for med in extracted["medications"]:
                    name = med.get("name", "") if isinstance(med, dict) else getattr(med, "name", "")
                    if name:
                        extracted_drugs.append(name)

        # The same drug often arrives from both sources; de-duplicate so it is not
        # paired against itself in the interaction sweep below.
        _seen: set = set()
        extracted_drugs = [
            d for d in extracted_drugs
            if not (d.strip().lower() in _seen or _seen.add(d.strip().lower()))
        ]

        # Check chief complaints and conversation turns for Ayurvedic / Homeopathic herbs mentioned
        conv_turns = _get_val(session, "conversationTurns") or []
        conv_text = " ".join([str(_get_val(turn, "patientAnswer", "")) for turn in conv_turns]).lower()
        cc_text = str(_get_val(session, "chiefComplaint", "")).lower()
        all_text = f"{cc_text} {conv_text}"

        # 2. Check for Low Fasting Sugar Marker
        has_low_fbs = False
        for doc in prior_docs:
            extracted = _get_val(doc, "extracted")
            if extracted and isinstance(extracted, dict) and "investigations" in extracted:
                for inv in extracted["investigations"]:
                    t_name = str(inv.get("test", "") if isinstance(inv, dict) else getattr(inv, "test", "")).lower()
                    flag = str(inv.get("flag", "") if isinstance(inv, dict) else getattr(inv, "flag", "")).upper()
                    val = str(inv.get("value", "") if isinstance(inv, dict) else getattr(inv, "value", ""))
                    if ("fbs" in t_name or "fasting" in t_name or "sugar" in t_name) and (flag == "LOW" or (val.isdigit() and int(val) < 70)):
                        has_low_fbs = True

        alerts: List[DrugInteractionAlert] = []
        herb_alerts: List[DrugInteractionAlert] = []
        allergy_warnings: List[str] = []
        contraindications: List[str] = []

        # Check Allergy Warnings. Skip explicit denials in any of their phrasings;
        # an unconfirmed status carries no drug name, so it matches no rule below.
        _denied = ("nkda" in allergy_text or "no known drug allerg" in allergy_text
                   or "no known allerg" in allergy_text)
        if allergy_text and not _denied:
            for drug in extracted_drugs:
                for rule in cls.KNOWN_DDI_RULES:
                    p1, p2 = rule["pair"]
                    if "allergy" in p2 and re.search(p1, drug, re.IGNORECASE) and re.search(p2.replace(".*allergy", ""), allergy_text, re.IGNORECASE):
                        allergy_warnings.append(f"⚠️ ALLERGY ALERT: {drug} prescribed to patient with documented '{allergy_text}'. High risk of anaphylaxis.")

        # Check Low Fasting Blood Sugar Contraindication
        if has_low_fbs:
            for drug in extracted_drugs:
                if re.search(r"(azulix|glimepiride|gliclazide|glibenclamide|insulin)", drug, re.IGNORECASE):
                    contraindications.append(
                        f"⚠️ HYPOGLYCEMIA WARNING: {drug} active with Low Fasting Sugar (69 mg/dL). High risk of symptomatic neuroglycopenia."
                    )
                    alerts.append(
                        DrugInteractionAlert(
                            medication1=drug,
                            medication2="Low Fasting Glucose (<70 mg/dL)",
                            severity="high",
                            interactionType="contraindication",
                            mechanism="Active insulin secretagogue in the setting of hypoglycemia (<70 mg/dL) precipitates severe neuroglycopenia.",
                            clinicalRecommendation="Advise immediate oral glucose intake. Reduce sulfonylurea dosage and review glycemic logs."
                        )
                    )

        # Check Pairwise Drug-Drug Interactions
        n_drugs = len(extracted_drugs)
        for i in range(n_drugs):
            for j in range(i + 1, n_drugs):
                d1 = extracted_drugs[i]
                d2 = extracted_drugs[j]
                
                for rule in cls.KNOWN_DDI_RULES:
                    p1, p2 = rule["pair"]
                    if (re.search(p1, d1, re.IGNORECASE) and re.search(p2, d2, re.IGNORECASE)) or \
                       (re.search(p1, d2, re.IGNORECASE) and re.search(p2, d1, re.IGNORECASE)):
                        alerts.append(
                            DrugInteractionAlert(
                                medication1=d1,
                                medication2=d2,
                                severity=rule["severity"],
                                interactionType=rule["type"],
                                mechanism=rule["mechanism"],
                                clinicalRecommendation=rule["recommendation"]
                            )
                        )

        # Check Herb-Drug Integrative Interactions
        for drug in extracted_drugs:
            for rule in cls.HERB_DRUG_RULES:
                p_herb, p_allopath = rule["pair"]
                if re.search(p_allopath, drug, re.IGNORECASE):
                    herb_match = re.search(p_herb, all_text, re.IGNORECASE)
                    if herb_match:
                        herb_name = herb_match.group(0).capitalize()
                        h_alert = DrugInteractionAlert(
                            medication1=f"{herb_name} (Ayush Herb / Food)",
                            medication2=drug,
                            severity="herb_drug",
                            interactionType="herb_drug",
                            mechanism=rule["mechanism"],
                            clinicalRecommendation=rule["recommendation"]
                        )
                        herb_alerts.append(h_alert)
                        alerts.append(h_alert)

        # Ayurvedic Dietary & Lifestyle Advice (Pathya / Apathya)
        ayurvedic_pathya = []
        if session.ayushMode or session.medicalSystem == "ayurveda":
            ayurvedic_pathya = [
                "Pathya (Beneficial): Warm, easily digestible light food (Laghu Ahara), barley (Yava), bitter gourd (Karella), boiled water (Ushnodaka).",
                "Apathya (To Avoid): Excess sweet/heavy foods (Guru Ahara), curd at night, day-sleeping (Divasvapna), sedentary posture immediately after meals."
            ]

        has_high_risk = any(a.severity == "high" for a in alerts) or len(allergy_warnings) > 0 or len(contraindications) > 0

        return SafetyCheckResponse(
            sessionId=session.sessionId,
            hasHighRiskAlerts=has_high_risk,
            alerts=alerts,
            allergyWarnings=allergy_warnings,
            contraindications=contraindications,
            herbDrugInteractions=herb_alerts,
            ayurvedicPathyaApathya=ayurvedic_pathya
        )

    @classmethod
    def check_drug_list(cls, drug_list: List[str]) -> List[DrugInteractionAlert]:
        """Standalone checker for a list of drug strings."""
        alerts: List[DrugInteractionAlert] = []
        n = len(drug_list)
        for i in range(n):
            for j in range(i + 1, n):
                d1 = drug_list[i]
                d2 = drug_list[j]
                for rule in cls.KNOWN_DDI_RULES:
                    p1, p2 = rule["pair"]
                    if (re.search(p1, d1, re.IGNORECASE) and re.search(p2, d2, re.IGNORECASE)) or \
                       (re.search(p1, d2, re.IGNORECASE) and re.search(p2, d1, re.IGNORECASE)):
                        alerts.append(
                            DrugInteractionAlert(
                                medication1=d1,
                                medication2=d2,
                                severity=rule["severity"],
                                interactionType=rule["type"],
                                mechanism=rule["mechanism"],
                                clinicalRecommendation=rule["recommendation"]
                            )
                        )
        return alerts
