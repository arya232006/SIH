import re
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from app.config import settings
from app.models import (
    ExtractedMedicationItem, MedicationConfidence,
    MedicationClarificationPlan, MedicationClarificationAnswerResponse
)

class MedicationClarificationService:
    """
    Dynamic LLM-Based Medication Clarification Engine for MediKiosk.
    - Extracts maximum evidence first & analyzes field-level confidence.
    - Deterministic escalation: 0 unclear -> continue; 1-2 unclear -> ask minimal patient questions; >2 -> staff queue.
    - Optimizes: Max useful information ÷ Min patient questions.
    - Multi-field natural language resolution (e.g., patient voice resolves name, frequency, timing simultaneously).
    - Multi-language support (English, Hindi, Bengali, Tamil, Telugu) with child & elderly friendly simplicity.
    """

    NLEM_LEXICON = {
        "amoxyclav": {"generic": "Amoxicillin + Clavulanic Acid", "common_strength": "625 mg", "type": "Antibiotic"},
        "augmentin": {"generic": "Amoxicillin + Clavulanic Acid", "common_strength": "625 mg", "type": "Antibiotic"},
        "paracetamol": {"generic": "Paracetamol", "common_strength": "650 mg", "type": "Antipyretic / Analgesic"},
        "dolo": {"generic": "Paracetamol", "common_strength": "650 mg", "type": "Antipyretic / Analgesic"},
        "calpol": {"generic": "Paracetamol", "common_strength": "500 mg", "type": "Antipyretic / Analgesic"},
        "pantoprazole": {"generic": "Pantoprazole", "common_strength": "40 mg", "type": "Proton Pump Inhibitor (Antacid)"},
        "pan": {"generic": "Pantoprazole", "common_strength": "40 mg", "type": "Antacid"},
        "pan-d": {"generic": "Pantoprazole + Domperidone", "common_strength": "40 mg / 30 mg", "type": "Antacid & Antiemetic"},
        "telmisartan": {"generic": "Telmisartan", "common_strength": "40 mg", "type": "Antihypertensive"},
        "metformin": {"generic": "Metformin Hydrochloride", "common_strength": "500 mg", "type": "Antidiabetic"},
        "glycomet": {"generic": "Metformin Hydrochloride", "common_strength": "500 mg", "type": "Antidiabetic"},
        "atorvastatin": {"generic": "Atorvastatin", "common_strength": "20 mg", "type": "Lipid Lowering / Statin"},
        "atorva": {"generic": "Atorvastatin", "common_strength": "20 mg", "type": "Statin"},
        "ascoril": {"generic": "Terbutaline + Bromhexine + Guaiphenesin", "common_strength": "Syrup 100ml", "type": "Cough Formula"},
        "cetirizine": {"generic": "Cetirizine", "common_strength": "10 mg", "type": "Antihistamine / Antiallergic"},
        "montair-lc": {"generic": "Montelukast + Levocetirizine", "common_strength": "10 mg / 5 mg", "type": "Antiallergic"},
        "azithromycin": {"generic": "Azithromycin", "common_strength": "500 mg", "type": "Antibiotic"},
        "azithral": {"generic": "Azithromycin", "common_strength": "500 mg", "type": "Antibiotic"},
        "ciprofloxacin": {"generic": "Ciprofloxacin", "common_strength": "500 mg", "type": "Antibiotic"},
        "amlodipine": {"generic": "Amlodipine", "common_strength": "5 mg", "type": "Antihypertensive"},
        "thyronorm": {"generic": "Levothyroxine Sodium", "common_strength": "50 mcg", "type": "Thyroid Supplement"}
    }

    QUESTION_TEMPLATES = {
        "en": {
            "frequency_timing": "How do you usually take this medicine?",
            "medicine_name": "We could not read this medicine clearly. What do you call this medicine?",
            "frequency_only": "How many times a day do you take this medicine?",
            "timing_only": "Do you take this medicine before or after food?",
            "child_friendly": "How many times do you take this medicine?",
            "elderly_friendly": "How do you take this medicine each day?",
            "options_freq_timing": [
                "Twice a day after food (Morning & Night)",
                "Once a day in the morning",
                "3 times a day after meals",
                "As needed for pain or fever (SOS)",
                "I don't know"
            ],
            "options_freq_only": [
                "Once a day (1 time)",
                "Twice a day (2 times)",
                "Three times a day (3 times)",
                "As needed (SOS)",
                "I don't know"
            ],
            "options_timing_only": [
                "After meals (Post-food)",
                "Empty stomach / Before food",
                "At bedtime (Night)",
                "I don't know"
            ]
        },
        "hi": {
            "frequency_timing": "आप यह दवा दिन में कितनी बार और कब लेते हैं?",
            "medicine_name": "इस दवा का नाम साफ़ नहीं दिख रहा। आप इसे किस नाम से जानते हैं?",
            "frequency_only": "आप यह दवा दिन में कितनी बार लेते हैं?",
            "timing_only": "क्या आप यह दवा खाने से पहले लेते हैं या खाने के बाद?",
            "child_friendly": "आप यह दवा दिन में कितनी बार लेते हैं?",
            "elderly_friendly": "आप यह दवा रोज़ कैसे लेते हैं?",
            "options_freq_timing": [
                "दिन में 2 बार खाने के बाद (सुबह और रात)",
                "दिन में 1 बार सुबह",
                "दिन में 3 बार खाने के बाद",
                "ज़रूरत पड़ने पर दर्द या बुखार के लिए (SOS)",
                "मुझे याद नहीं / पता नहीं"
            ],
            "options_freq_only": [
                "दिन में 1 बार",
                "दिन में 2 बार (सुबह-शाम)",
                "दिन में 3 बार",
                "ज़रूरत पड़ने पर (SOS)",
                "पता नहीं"
            ],
            "options_timing_only": [
                "खाने के बाद",
                "खाली पेट / खाने से पहले",
                "रात को सोते समय",
                "पता नहीं"
            ]
        },
        "bn": {
            "frequency_timing": "আপনি এই ওষুধটি দিনে কতবার এবং কীভাবে খান?",
            "medicine_name": "এই ওষুধের নামটি পরিষ্কার নয়। আপনি এটিকে কী ওষুধ বলেন?",
            "frequency_only": "আপনি এই ওষুধটি দিনে কতবার খান?",
            "timing_only": "ওষুধটি কি খাবারের আগে না পরে খান?",
            "child_friendly": "ওষুধটি দিনে কতবার খাও?",
            "elderly_friendly": "আপনি এই ওষুধটি কীভাবে খান?",
            "options_freq_timing": [
                "দিনে ২ বার খাবার পর (সকাল ও রাত)",
                "দিনে ১ বার সকালে",
                "দিনে ৩ বার খাবার পর",
                "প্রয়োজন অনুযায়ী জ্বর বা ব্যথায় (SOS)",
                "মনে নেই / জানি না"
            ],
            "options_freq_only": [
                "দিনে ১ বার",
                "দিনে ২ বার",
                "দিনে ৩ বার",
                "প্রয়োজনে",
                "জানি না"
            ],
            "options_timing_only": [
                "খাবারের পর",
                "খালি পেটে / খাবারের আগে",
                "রাতে শোবার আগে",
                "জানি না"
            ]
        },
        "ta": {
            "frequency_timing": "இந்த மருந்தை நீங்கள் ஒரு நாளில் எத்தனை முறை மற்றும் எப்போது எடுத்துக்கொள்கிறீர்கள்?",
            "medicine_name": "இந்த மருந்தின் பெயர் தெளிவாக இல்லை. இதை நீங்கள் என்னவென்று அழைக்கிறீர்கள்?",
            "frequency_only": "இந்த மருந்தை ஒரு நாளில் எத்தனை முறை எடுத்துக்கொள்கிறீர்கள்?",
            "timing_only": "இந்த மருந்தை உணவுக்கு முன்னா அல்லது பின்னா சாப்பிடுகிறீர்களா?",
            "child_friendly": "இந்த மருந்தை எத்தனை முறை சாப்பிடுகிறாய்?",
            "elderly_friendly": "இந்த மருந்தை நீங்கள் எவ்வாறு சாப்பிடுகிறீர்கள்?",
            "options_freq_timing": [
                "உணவுக்குப் பின் 2 முறை (காலை & இரவு)",
                "காலையில் 1 முறை",
                "உணவுக்குப் பின் 3 முறை",
                "தேவைப்படும்போது மட்டும் (SOS)",
                "எனக்குத் தெரியவில்லை"
            ],
            "options_freq_only": [
                "நாளுக்கு 1 முறை",
                "நாளுக்கு 2 முறை",
                "நாளுக்கு 3 முறை",
                "தேவைப்படும்போது",
                "தெரியவில்லை"
            ],
            "options_timing_only": [
                "உணவுக்குப் பின்",
                "வெறும் வயிற்றில் / உணவுக்கு முன்",
                "இரவு படுக்கைக்கு முன்",
                "தெரியவில்லை"
            ]
        },
        "te": {
            "frequency_timing": "ఈ మందును మీరు రోజుకు ఎన్నిసార్లు మరియు ఎప్పుడు తీసుకుంటారు?",
            "medicine_name": "ఈ మందు పేరు స్పష్టంగా లేదు. ఈ మందును మీరు ఏమని పిలుస్తారు?",
            "frequency_only": "ఈ మందును రోజుకు ఎన్నిసార్లు తీసుకుంటారు?",
            "timing_only": "ఈ మందును భోజనానికి ముందా లేక తిన్న తర్వాత తీసుకుంటారా?",
            "child_friendly": "ఈ మందును రోజుకు ఎన్నిసార్లు తీసుకుంటావు?",
            "elderly_friendly": "ఈ మందును మీరు ఎలా తీసుకుంటారు?",
            "options_freq_timing": [
                "భోజనం తర్వాత రోజుకు 2 సార్లు (ఉదయం & రాత్రి)",
                "ఉదయం 1 సారి",
                "భోజనం తర్వాత రోజుకు 3 సార్లు",
                "అవసరమైనప్పుడు మాత్రమే (SOS)",
                "నాకు తెలియదు"
            ],
            "options_freq_only": [
                "రోజుకు 1 సారి",
                "రోజుకు 2 సార్లు",
                "రోజుకు 3 సార్లు",
                "అవసరమైనప్పుడు",
                "తెలియదు"
            ],
            "options_timing_only": [
                "భోజనం తర్వాత",
                "ఖాళీ కడుపుతో / భోజనానికి ముందు",
                "రాత్రి పడుకునే ముందు",
                "తెలియదు"
            ]
        }
    }

    @classmethod
    def normalize_extracted_medications(
        cls,
        raw_meds: List[Dict[str, Any]],
        doc_type: str = "handwritten_prescription",
        doc_confidence: float = 0.70
    ) -> List[ExtractedMedicationItem]:
        """
        Transforms raw OCR/heuristic medication items into typed ExtractedMedicationItem instances
        with granular field-level confidence analysis and unreliable field flagging.
        """
        items: List[ExtractedMedicationItem] = []
        is_handwritten = (doc_type == "handwritten_prescription")

        for idx, m in enumerate(raw_meds):
            m_id = f"med_{idx + 1:02d}"
            name = m.get("name") or m.get("medicine") or "Unidentified Medication"
            dosage = m.get("dosage") or m.get("dose") or ""
            frequency = m.get("frequency") or ""
            duration = m.get("duration") or ""
            instructions = m.get("instructions") or m.get("timing") or ""

            # Extract strength from name if embedded (e.g. Amoxyclav 625mg)
            strength = ""
            str_match = re.search(r'(\d[\d,]*(?:\.\d+)?\s*[kK]?\s*(?:mg|g|mcg|ml|iu))', name, re.IGNORECASE)
            if str_match:
                strength = str_match.group(1).strip()
            elif str_match := re.search(r'(\d[\d,]*(?:\.\d+)?\s*[kK]?\s*(?:mg|g|mcg|ml|iu))', dosage, re.IGNORECASE):
                strength = str_match.group(1).strip()

            # Analyze field-level confidences
            name_clean = re.sub(r'^(?:tab\.?|cap\.?|syp\.?|inj\.?)\s*', '', name, flags=re.IGNORECASE).strip().lower()
            fuzzy_matched = any(k in name_clean for k in cls.NLEM_LEXICON.keys())

            conf_med = 0.94 if (fuzzy_matched or not is_handwritten) else (0.50 if "unidentified" in name_clean else 0.70)
            conf_str = 0.95 if strength else (0.80 if dosage else 0.40)
            conf_freq = 0.92 if (frequency and not is_handwritten) else (0.75 if (frequency and ("1-" in frequency or "bid" in frequency.lower() or "tid" in frequency.lower() or "sos" in frequency.lower())) else (0.35 if not frequency else 0.65))
            conf_dur = 0.88 if duration else 0.45
            timing_val = instructions or ("After food" if "after" in frequency.lower() else ("Empty stomach" if "empty" in frequency.lower() else ""))
            conf_tim = 0.85 if timing_val else 0.35

            overall_conf = round((conf_med + conf_str + conf_freq + conf_dur + conf_tim) / 5.0, 2)
            
            confidence = MedicationConfidence(
                medicine=conf_med,
                strength=conf_str,
                dosage=0.85 if dosage else 0.40,
                frequency=conf_freq,
                duration=conf_dur,
                timing=conf_tim,
                overall=overall_conf
            )

            # Identify missing or unreliable fields
            unreliable = []
            if conf_med < 0.60 or "unidentified" in name_clean:
                unreliable.append("medicine")
            if conf_freq < 0.60 or not frequency:
                unreliable.append("frequency")
            if conf_tim < 0.60 and not timing_val:
                unreliable.append("timing")

            status = "reliable"
            if len(unreliable) > 0:
                status = "needs_clarification"

            # Ground the reading against the formulary. A name the vision model
            # produced confidently may still not be a marketed product, and a
            # brand-only reading is invisible to the DDI rules until it carries
            # its generic.
            from app.services.formulary_service import formulary_service
            check = formulary_service.verify(name, strength or dosage or "")
            if check.status == "unverified":
                # Not a known product: downgrade rather than present it as read.
                if status == "reliable":
                    status = "needs_clarification"
                if "medicine" not in unreliable:
                    unreliable.append("medicine")
                confidence.medicine = min(confidence.medicine, 0.45)
                confidence.overall = min(confidence.overall, 0.55)
            elif check.strengthKnown is False:
                # Name is real but the dose is not marketed -- a dosing error is
                # more dangerous than a misread name.
                if status == "reliable":
                    status = "needs_clarification"
                if "strength" not in unreliable:
                    unreliable.append("strength")
                confidence.strength = min(confidence.strength, 0.40)
                confidence.overall = min(confidence.overall, 0.60)

            items.append(ExtractedMedicationItem(
                id=m_id,
                name=name,
                strength=strength or None,
                dosage=dosage or None,
                frequency=frequency or None,
                duration=duration or None,
                timing=timing_val or None,
                instructions=instructions or None,
                source="fuzzy-nlem-matched" if fuzzy_matched else ("handwritten-prescription" if is_handwritten else "printed-prescription"),
                confidence=confidence,
                status=status,
                unreliableFields=unreliable,
                cropUrl=None,
                verificationStatus=check.status,
                matchedBrand=check.matchedBrand,
                genericName=check.generic,
                drugClass=check.drugClass,
                strengthPlausible=check.strengthKnown,
                formularyCandidates=check.candidates,
                verificationNotes=check.notes,
            ))

        return items

    @classmethod
    def plan_next_question(
        cls,
        medications: List[ExtractedMedicationItem],
        patient_age: int = 40,
        language: str = "en"
    ) -> MedicationClarificationPlan:
        """
        Dynamically determines what clarification question to ask the patient.
        Follows the optimization: (Max Useful Information) ÷ (Min Questions).
        Enforces deterministic escalation:
        - 0 unclear -> continue immediately
        - 1-2 unclear -> ask minimal simple question
        - >2 unclear -> escalate to staff queue
        """
        lang = language if language in cls.QUESTION_TEMPLATES else "en"
        t_dict = cls.QUESTION_TEMPLATES[lang]
        total_meds = len(medications)
        
        unclear_items = [m for m in medications if m.status == "needs_clarification"]
        unclear_count = len(unclear_items)
        resolved_count = len([m for m in medications if m.status in ("reliable", "verified_by_patient")])

        # Case 1: 0 Unclear -> Continue Immediately
        if unclear_count == 0:
            return MedicationClarificationPlan(
                shouldAskPatient=False,
                question=None,
                language=lang,
                reason="All extracted medications are clinically reliable. No patient clarification needed.",
                stopAfterAnswer=True,
                escalateToStaff=False,
                unclearMedicationCount=0,
                totalMedicationCount=total_meds,
                resolvedCount=resolved_count
            )

        # Case 2: > 2 Unclear -> Deterministic Staff Escalation
        if unclear_count > 2:
            return MedicationClarificationPlan(
                shouldAskPatient=False,
                question=None,
                language=lang,
                reason=f"Multiple medications ({unclear_count}) have unreadable handwriting. Escrowed to Hospital Staff Desk for quick pharmacist verification.",
                stopAfterAnswer=True,
                escalateToStaff=True,
                unclearMedicationCount=unclear_count,
                totalMedicationCount=total_meds,
                resolvedCount=resolved_count
            )

        # Case 3: 1 to 2 Unclear -> Dynamically Plan ONE minimal question for target medication
        target_med = unclear_items[0]
        missing_fields = target_med.unreliableFields

        is_child = patient_age < 12
        is_elderly = patient_age >= 60

        # Plan the single simplest question based on what is missing
        if "medicine" in missing_fields:
            question_text = t_dict["medicine_name"]
            options = ["Amoxyclav 625 (Augmentin)", "Paracetamol / Dolo 650", "Pan-40 (Gas / Acidity tablet)", "Metformin 500 (Sugar tablet)", "Telmisartan 40 (BP tablet)", "I don't know"]
        elif "frequency" in missing_fields and "timing" in missing_fields:
            if is_child:
                question_text = t_dict["child_friendly"]
            elif is_elderly:
                question_text = t_dict["elderly_friendly"]
            else:
                question_text = t_dict["frequency_timing"]
            options = t_dict["options_freq_timing"]
        elif "frequency" in missing_fields:
            question_text = t_dict["frequency_only"]
            options = t_dict["options_freq_only"]
        elif "timing" in missing_fields:
            question_text = t_dict["timing_only"]
            options = t_dict["options_timing_only"]
        else:
            question_text = t_dict["frequency_timing"]
            options = t_dict["options_freq_timing"]

        # Quality Check: Validate that question has no medical jargon
        clean_question = cls._quality_check_question(question_text, lang)

        # Next stop condition check: if this is the last unclear medication, stop after this answer
        stop_after = (unclear_count == 1)

        return MedicationClarificationPlan(
            shouldAskPatient=True,
            question=clean_question,
            language=lang,
            targetMedicationId=target_med.id,
            targetMedicationName=target_med.name,
            informationNeeded=missing_fields,
            options=options,
            reason=f"Clarifying {', '.join(missing_fields)} for {target_med.name}",
            stopAfterAnswer=stop_after,
            escalateToStaff=False,
            unclearMedicationCount=unclear_count,
            totalMedicationCount=total_meds,
            resolvedCount=resolved_count
        )

    @classmethod
    def _quality_check_question(cls, text: str, lang: str) -> str:
        """
        Validates that patient-facing question uses plain everyday language with zero medical jargon.
        """
        forbidden_jargon = [
            "dosage frequency", "route of administration", "treatment duration",
            "posology", "pharmacotherapy", "administration route", "prescribed regimen"
        ]
        text_lower = text.lower()
        for jargon in forbidden_jargon:
            if jargon in text_lower:
                return cls.QUESTION_TEMPLATES.get(lang, cls.QUESTION_TEMPLATES["en"])["frequency_timing"]
        return text

    @classmethod
    def interpret_patient_answer(
        cls,
        answer: str,
        target_med: ExtractedMedicationItem,
        language: str = "en"
    ) -> Tuple[ExtractedMedicationItem, List[str]]:
        """
        Interprets natural language answers (voice or text) to simultaneously resolve multiple fields.
        Example: 'It is Amoxyclav 625, 1 morning and 1 night after food'
        -> resolves name, strength, frequency, and timing simultaneously.
        """
        ans_lower = answer.lower().strip()
        resolved_fields = []

        # Handle 'I don't know' / 'I don't remember' / 'pata nahi' / 'jani na' / 'theriyavillai'
        if any(w in ans_lower for w in ["don't know", "dont know", "don't remember", "pata nahi", "jani na", "theriyavillai", "teliyadu", "not sure"]):
            target_med.status = "uncertain"
            target_med.instructions = (target_med.instructions or "") + " (Patient uncertain of schedule)"
            target_med.unreliableFields = []
            return target_med, ["patient_marked_uncertain"]

        # 1. Resolve Medicine Name & Strength if mentioned
        for key, lex in cls.NLEM_LEXICON.items():
            if key in ans_lower or lex["generic"].lower() in ans_lower:
                target_med.name = f"{lex['generic']} ({key.capitalize()})"
                target_med.confidence.medicine = 0.95
                target_med.source = "patient-voice"
                if "medicine" in target_med.unreliableFields:
                    target_med.unreliableFields.remove("medicine")
                resolved_fields.append("medicine")
                if not target_med.strength and lex.get("common_strength"):
                    target_med.strength = lex["common_strength"]
                    target_med.confidence.strength = 0.95
                    resolved_fields.append("strength")
                break

        # Check explicit strength in answer (e.g. 625mg, 500, 40mg, 650)
        str_match = re.search(r'(\d+\s*(?:mg|g|mcg|ml))\b', ans_lower)
        if str_match:
            target_med.strength = str_match.group(1).upper()
            target_med.confidence.strength = 0.96
            if "strength" not in resolved_fields:
                resolved_fields.append("strength")

        # 2. Resolve Frequency (1-0-1, twice daily, subah aur raat, 3 times, SOS)
        if any(w in ans_lower for w in ["twice", "2 times", "subah aur raat", "morning and night", "1-0-1", "sokal o rat", "kaalai & iravu", "udayam & rathri", "morning & night"]):
            target_med.frequency = "Twice daily (Morning & Night / 1-0-1)"
            target_med.confidence.frequency = 0.95
            if "frequency" in target_med.unreliableFields:
                target_med.unreliableFields.remove("frequency")
            resolved_fields.append("frequency")
        elif any(w in ans_lower for w in ["thrice", "3 times", "teen baar", "tin bar", "1-1-1", "three times"]):
            target_med.frequency = "Thrice daily (TID / 1-1-1)"
            target_med.confidence.frequency = 0.95
            if "frequency" in target_med.unreliableFields:
                target_med.unreliableFields.remove("frequency")
            resolved_fields.append("frequency")
        elif any(w in ans_lower for w in ["once", "1 time", "ek baar", "morning only", "1-0-0", "once daily"]):
            target_med.frequency = "Once daily (Morning / 1-0-0)"
            target_med.confidence.frequency = 0.95
            if "frequency" in target_med.unreliableFields:
                target_med.unreliableFields.remove("frequency")
            resolved_fields.append("frequency")
        elif any(w in ans_lower for w in ["bedtime", "night only", "0-0-1", "sone se pehle", "sobar age", "iravu matrum"]):
            target_med.frequency = "Once daily at bedtime (HS / 0-0-1)"
            target_med.confidence.frequency = 0.95
            if "frequency" in target_med.unreliableFields:
                target_med.unreliableFields.remove("frequency")
            resolved_fields.append("frequency")
        elif any(w in ans_lower for w in ["as needed", "sos", "jab dard ho", "fever", "proyojon"]):
            target_med.frequency = "SOS / As needed for pain or fever"
            target_med.confidence.frequency = 0.95
            if "frequency" in target_med.unreliableFields:
                target_med.unreliableFields.remove("frequency")
            resolved_fields.append("frequency")

        # 3. Resolve Timing (before food, after food, empty stomach)
        if any(w in ans_lower for w in ["after food", "after meal", "khane ke baad", "khabar por", "unavukku pin", "bhojanam tharuvatha", "post-food"]):
            target_med.timing = "After food (Post-meal)"
            target_med.confidence.timing = 0.95
            if "timing" in target_med.unreliableFields:
                target_med.unreliableFields.remove("timing")
            resolved_fields.append("timing")
        elif any(w in ans_lower for w in ["before food", "empty stomach", "khali pet", "khabar age", "verum vayitril", "khali kadupukho"]):
            target_med.timing = "Empty stomach (Before breakfast / food)"
            target_med.confidence.timing = 0.95
            if "timing" in target_med.unreliableFields:
                target_med.unreliableFields.remove("timing")
            resolved_fields.append("timing")

        # 4. Resolve Dosage quantity if stated (e.g. 'one tablet', '1 goli', '10ml')
        if any(w in ans_lower for w in ["1 tablet", "one tablet", "1 goli", "ek goli", "1 cap", "one capsule"]):
            target_med.dosage = "1 tablet/capsule"
            target_med.confidence.dosage = 0.95
            resolved_fields.append("dosage")
        elif any(w in ans_lower for w in ["2 tablets", "two tablets", "2 goli", "do goli"]):
            target_med.dosage = "2 tablets"
            target_med.confidence.dosage = 0.95
            resolved_fields.append("dosage")
        elif "10ml" in ans_lower or "10 ml" in ans_lower:
            target_med.dosage = "10 ml"
            target_med.confidence.dosage = 0.95
            resolved_fields.append("dosage")

        # Update status
        if len(target_med.unreliableFields) == 0:
            target_med.status = "verified_by_patient"
            target_med.source = "patient-voice"

        return target_med, resolved_fields

