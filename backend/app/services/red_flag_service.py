import re
from typing import List
from app.models import RedFlag, QAPair

class RedFlagDetector:
    """
    Deterministic, high-specificity rule-based clinical emergency red flag detector.
    Engineered with robust clause-level negation filtering to prevent false positives on
    non-emergency symptoms (e.g. acidity, routine cough, osteoarthritis, standard headache,
    isolated limb soreness, or denied alarm signs).
    """

    NEGATION_WORDS = [
        "no", "not", "denies", "denied", "without", "never", "none",
        "nahi", "nehi", "kono nei", "kono na", "illa", "ledu", "nkda",
        "negative for", "ruled out", "no known", "no history of"
    ]

    # 1. Acute Coronary Syndrome (ACS) / True Cardiac Emergency
    #
    # These patterns have to match how a patient's words actually arrive, not
    # only how a clinician would write them up. Speech from the kiosk reaches
    # here as an English rendering of what was spoken, and "pain in my chest
    # going into my left arm" -- a textbook presentation -- matched nothing,
    # because the rules required the literal adjacent words "chest pain" and
    # the single preposition "to". Specificity is preserved by the rule below
    # still demanding radiation or diaphoresis alongside the pain.
    CARDIAC_CHEST_PAIN = re.compile(
        r"(crushing\s*chest\s*pain|squeezing\s*chest|heavy\s*squeezing\s*pressure"
        r"|severe\s*retrosternal\s*chest|elephant\s*sitting\s*on\s*chest"
        r"|crushing\s*heavy\s*chest|acute\s*chest\s*pain|chest\s*pain\s*since|chest\s*pain"
        # How it is spoken rather than charted.
        r"|chest\s*(pain|discomfort|tightness|pressure|heaviness|burning)"
        r"|(pain|discomfort|tightness|pressure|heaviness)\s*(in|on|over)\s*"
        r"(my\s*|the\s*|his\s*|her\s*)?chest"
        # Romanised Hindi/Bengali, for speech that is not translated at all.
        r"|seene\s*me\s*tez\s*dard|chaati\s*me\s*bhari\s*dard|chaati\s*me\s*dard"
        r"|seene\s*me\s*dard|buke\s*byatha)",
        re.IGNORECASE
    )
    _RADIATION_TARGET = (r"(left\s*arm|left\s*shoulder|left\s*hand|jaw|neck|back)")
    CARDIAC_RADIATION_LEFT = re.compile(
        # "Radiating"/"spreading" are directional on their own; vaguer verbs
        # must carry an explicit preposition so that merely mentioning an arm
        # does not read as radiation.
        rf"((radiat\w*|spread\w*)\s*(down|to|into|towards|in\s*to)?\s*"
        rf"(my\s*|the\s*)?{_RADIATION_TARGET}"
        rf"|(go\w*|mov\w*|travel\w*|shoot\w*|run\w*|extend\w*)\s*(down\s*|up\s*)?"
        rf"(to|into|towards|in\s*to|down)\s*(my\s*|the\s*)?{_RADIATION_TARGET}"
        rf"|pain\s*in\s*(my\s*)?left\s*arm\s*and\s*(chest|shoulder)"
        rf"|baayein\s*haath\s*me\s*dard\s*jaa\s*raha"
        rf"|left\s*haath\s*me\s*dard\s*jaa\s*raha)",
        re.IGNORECASE
    )
    CARDIAC_DIAPHORESIS_DYSPNEA = re.compile(
        r"(cold\s*diaphoresis|profuse\s*cold\s*sweat|heavy\s*cold\s*sweating|cold\s*sweat\w*|cold\s*sweat|paseena.*ghabrahat.*dard|sweat\w*.*breathless.*chest)",
        re.IGNORECASE
    )

    # 2. Acute Stroke / Code Stroke (FAST criteria - sudden focal deficit)
    STROKE_FOCAL = re.compile(
        r"(sudden\s*(facial\s*droop|face\s*droop|paralysis|one-sided\s*weakness|hemiparesis|slurr\w*\s*speech)|acute\s*slurr\w*\s*speech|slurred\s*speech|facial\s*droop|face\s*droop|one-sided\s*paralysis|weakness\s*in\s*one\s*arm\s*and\s*leg|munh\s*tedha|awaz\s*ladkharana|ek\s*taraf\s*ka\s*hissa\s*sunn)",
        re.IGNORECASE
    )

    # 3. Severe Acute Airway / Respiratory Failure (Not mild cold/cough/exertional asthma)
    RESPIRATORY_FAILURE = re.compile(
        r"(cannot\s*breathe\s*at\s*all|severe\s*gasping\s*for\s*air|blue\s*lips|cyanosis|acute\s*asphyxia|dam\s*ghut\s*raha\s*hai|saans\s*bilkul\s*nahi\s*aarahi|choking\s*and\s*cannot\s*breathe)",
        re.IGNORECASE
    )

    # 4. Active Massive Hemorrhage / Upper GI Bleed
    ACTIVE_BLEEDING = re.compile(
        r"(vomiting\s*(fresh\s*|large\s*amount\s*of\s*)?blood|blood\s*in\s*vomit|hematemesis|tarry\s*stools|dark\s*black\s*tarry|melena|coughing\s*up\s*(cups\s*of\s*)?fresh\s*blood|massive\s*hemoptysis|khoon\s*ki\s*ulti|khoon\s*nikal\s*raha\s*gale)",
        re.IGNORECASE
    )

    # 5. Systemic Anaphylaxis / Airway Angioedema
    ANAPHYLAXIS_SEVERE = re.compile(
        r"(throat\s*closing\s*up|swelling\s*in\s*throat|throat\s*swelling|tongue\s*swelling|facial\s*hives|inability\s*to\s*breathe.*(nuts|peanut|food|sting)|severe\s*anaphylaxis|airway\s*angioedema)",
        re.IGNORECASE
    )

    # 6. Sepsis / Severe Meningitis
    CNS_SEPSIS = re.compile(
        r"(high\s*fever.*(neck\s*stiffness|stiff\s*neck|unconscious|altered\s*sensorium|convulsion)|fever.*altered\s*sensorium|fever.*convulsion|gardhan\s*akad.*behosh)",
        re.IGNORECASE
    )

    # 7. Acute Psychiatric Crisis / Self-Harm
    PSYCHIATRIC_CRISIS = re.compile(
        r"(thoughts\s*of\s*suicide|suicidal\s*ideation|self\s*harm|want\s*to\s*kill\s*myself|end\s*my\s*life|suicide\s*and\s*self\s*harm|overdose)",
        re.IGNORECASE
    )

    @classmethod
    def _clean_denials(cls, text: str) -> str:
        """
        Robust clause-level negation cleaner.
        Splits text by punctuation/clauses and replaces any clause containing
        a negation word (e.g. 'no breathlessness', 'no blood in vomit', 'denies chest pain')
        with a sanitized marker to eliminate false positive triggers.
        """
        if not text:
            return ""

        # Break text into separate clauses by punctuation and major clause conjunctions
        clauses = re.split(r"[,.;:\n\r()!?/\-\\]+|\band\s+no\b|\bbut\s+no\b|\bwith\s+no\b|\bwithout\b", text, flags=re.IGNORECASE)
        sanitized_clauses = []

        for clause in clauses:
            cl = clause.strip()
            if not cl:
                continue

            cl_lower = cl.lower()
            # Check if this clause begins with or contains a negation phrase
            is_negated = any(re.search(rf"\b{re.escape(neg)}\b", cl_lower) for neg in cls.NEGATION_WORDS)
            
            # Specific explicit exclusions
            if is_negated or "normal" in cl_lower or "nkda" in cl_lower or "denies" in cl_lower:
                sanitized_clauses.append(" [DENIED_OR_NORMAL] ")
            else:
                sanitized_clauses.append(cl)

        return " . ".join(sanitized_clauses)

    @classmethod
    def evaluate(cls, chief_complaint: str, conversation_turns: List[QAPair]) -> RedFlag:
        # Build comprehensive patient statements text
        raw_text = (chief_complaint or "") + " " + " ".join(t.patientAnswer for t in conversation_turns)
        cleaned_text = cls._clean_denials(raw_text)

        # 1. Check for genuine Acute Coronary Syndrome
        # Requires acute cardiac chest pain + (explicit radiation to left arm/shoulder/jaw OR acute cold diaphoresis)
        has_cardiac_pain = bool(cls.CARDIAC_CHEST_PAIN.search(cleaned_text))
        has_left_radiation = bool(cls.CARDIAC_RADIATION_LEFT.search(cleaned_text))
        has_diaphoresis = bool(cls.CARDIAC_DIAPHORESIS_DYSPNEA.search(cleaned_text))

        if has_cardiac_pain and (has_left_radiation or has_diaphoresis):
            return RedFlag(
                triggered=True,
                reason="Potential Acute Coronary Syndrome Warning (Severe chest pain with left arm/jaw radiation or cold diaphoresis)",
                action="IMMEDIATE CASUALTY TRIAGE: Urgent 12-lead ECG, Troponin, and direct physician assessment.",
                urgency="emergency",
                category="cardiac"
            )

        # 2. Check for True Acute Stroke
        if cls.STROKE_FOCAL.search(cleaned_text):
            return RedFlag(
                triggered=True,
                reason="Potential Acute Stroke Warning (Sudden focal neurological deficit / speech or facial impairment)",
                action="URGENT CODE STROKE: Immediate non-contrast head CT and emergency neurological consult.",
                urgency="emergency",
                category="neurological"
            )

        # 3. Check for Severe Respiratory Failure
        if cls.RESPIRATORY_FAILURE.search(cleaned_text):
            return RedFlag(
                triggered=True,
                reason="Severe Acute Airway/Respiratory Distress Warning",
                action="IMMEDIATE TRIAGE: High-flow oxygen, SpO2 monitoring, rapid airway evaluation.",
                urgency="emergency",
                category="respiratory"
            )

        # 4. Check for Active Massive Hemorrhage / Upper GI Bleed
        if cls.ACTIVE_BLEEDING.search(cleaned_text):
            return RedFlag(
                triggered=True,
                reason="Acute Active Hemorrhage Warning (Hematemesis / Melena / Hemoptysis)",
                action="URGENT EVALUATION: Hemodynamic stabilization, IV access, emergency GI/Pulmonary assessment.",
                urgency="emergency",
                category="hemorrhage"
            )

        # 5. Check for Anaphylaxis
        if cls.ANAPHYLAXIS_SEVERE.search(cleaned_text):
            return RedFlag(
                triggered=True,
                reason="Severe Anaphylaxis / Airway Swelling Warning",
                action="EMERGENCY PROTOCOL: Intramuscular Epinephrine preparation and immediate casualty transfer.",
                urgency="emergency",
                category="anaphylaxis"
            )

        # 6. Check for Psychiatric Crisis / Self-Harm
        if cls.PSYCHIATRIC_CRISIS.search(cleaned_text):
            return RedFlag(
                triggered=True,
                reason="High-Acuity Psychiatric Crisis / Suicide Risk Alert",
                action="IMMEDIATE PSYCHIATRIC SAFETY PROTOCOL: Continuous direct observation and urgent psychiatric consult.",
                urgency="emergency",
                category="psychiatric"
            )

        # 7. Check for Sepsis / Meningismus
        if cls.CNS_SEPSIS.search(cleaned_text):
            return RedFlag(
                triggered=True,
                reason="High Fever with Altered Sensorium or Meningismus Warning",
                action="URGENT EVALUATION: Blood cultures, prompt casualty clinical workup.",
                urgency="emergency",
                category="sepsis"
            )

        # Otherwise: Routine OPD Consultation
        return RedFlag(
            triggered=False,
            reason="",
            action="",
            urgency="routine",
            category="general"
        )

red_flag_detector = RedFlagDetector()
