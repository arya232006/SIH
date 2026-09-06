import re
from typing import List, Optional, Tuple, Dict, Any
from app.models import DepartmentRouting, QAPair

class DepartmentRoutingService:
    """
    Automated, explainable department and specialist doctor triage engine.
    Matches chief complaints and conversational history to specialist departments,
    room numbers, floor locations, and attending consultants.
    Identifies ambiguous/non-specific complaints for manual staff triage takeover.
    """

    DEPARTMENT_DIRECTORY: Dict[str, Dict[str, str]] = {
        "Ophthalmology": {
            "departmentCode": "OPHTH",
            "doctorName": "Dr. Radhika Nair",
            "doctorTitle": "Senior Consultant Ophthalmologist",
            "roomNumber": "Room 102",
            "floorLocation": "Ground Floor (Central OPD Wing)",
            "defaultReason": "Ocular acuity screening, slit-lamp assessment and visual refraction examination."
        },
        "Cardiology": {
            "departmentCode": "CARDIO",
            "doctorName": "Dr. A. K. Banerjee",
            "doctorTitle": "Senior Interventional Cardiologist",
            "roomNumber": "Room 204",
            "floorLocation": "First Floor (East Wing - Cardiovascular Center)",
            "defaultReason": "ECG, hemodynamic triage, troponin review and cardiovascular evaluation."
        },
        "Gastroenterology": {
            "departmentCode": "GASTRO",
            "doctorName": "Dr. Manisha Kulkarni",
            "doctorTitle": "Senior Gastroenterologist & Hepatologist",
            "roomNumber": "Room 208",
            "floorLocation": "First Floor (West Wing - Digestive Care)",
            "defaultReason": "Abdominal palpation, dyspepsia protocol and digestive tract assessment."
        },
        "Orthopedics": {
            "departmentCode": "ORTHO",
            "doctorName": "Dr. Vikram Sethi",
            "doctorTitle": "Senior Orthopedic and Joint Replacement Surgeon",
            "roomNumber": "Room 112",
            "floorLocation": "Ground Floor (North Wing - Bone & Joint Clinic)",
            "defaultReason": "Musculoskeletal assessment, weight-bearing joint inspection and mobility evaluation."
        },
        "Pulmonology": {
            "departmentCode": "PULMO",
            "doctorName": "Dr. Farooq Ahmed",
            "doctorTitle": "Senior Pulmonologist and Chest Physician",
            "roomNumber": "Room 304",
            "floorLocation": "Second Floor (North Wing - Respiratory Care)",
            "defaultReason": "Chest auscultation, peak expiratory flow and respiratory history evaluation."
        },
        "Neurology": {
            "departmentCode": "NEURO",
            "doctorName": "Dr. Debabrata Sen",
            "doctorTitle": "Senior Consultant Neurologist",
            "roomNumber": "Room 310",
            "floorLocation": "Second Floor (East Wing - Neurosciences)",
            "defaultReason": "Neurological screening, cranial nerve and cephalalgia evaluation."
        },
        "Endocrinology": {
            "departmentCode": "ENDO",
            "doctorName": "Dr. Meera Nambiar",
            "doctorTitle": "Senior Endocrinologist and Diabetologist",
            "roomNumber": "Room 220",
            "floorLocation": "First Floor (South Wing - Metabolic Care)",
            "defaultReason": "Glycemic control profile, HbA1c review and diabetic metabolic screen."
        },
        "Dermatology": {
            "departmentCode": "DERMA",
            "doctorName": "Dr. Shalini Verma",
            "doctorTitle": "Consultant Dermatologist and Dermatosurgeon",
            "roomNumber": "Room 114",
            "floorLocation": "Ground Floor (South Wing - Skin Clinic)",
            "defaultReason": "Dermatological lesion inspection and allergy evaluation."
        },
        "ENT": {
            "departmentCode": "ENT",
            "doctorName": "Dr. Rajesh Kulkarni",
            "doctorTitle": "Senior ENT and Head-Neck Surgeon",
            "roomNumber": "Room 116",
            "floorLocation": "Ground Floor (South Wing - ENT Suite)",
            "defaultReason": "Otolaryngological examination, otoscopy and throat evaluation."
        },
        "Pediatrics": {
            "departmentCode": "PEDIA",
            "doctorName": "Dr. Ananya Sengupta",
            "doctorTitle": "Senior Consultant Pediatrician",
            "roomNumber": "Room 105",
            "floorLocation": "Ground Floor (West Wing - Children OPD)",
            "defaultReason": "Pediatric vital assessment, developmental and pediatric clinical triage."
        },
        "AYUSH_Ayurveda": {
            "departmentCode": "AYUSH",
            "doctorName": "Vaidya Raghavan Sharma",
            "doctorTitle": "Ayurvedic Physician (BAMS, MD Ayu)",
            "roomNumber": "AYUSH-01",
            "floorLocation": "Ground Floor (AYUSH Holistic Care Annex)",
            "defaultReason": "Dashavidha Pariksha, Prakriti-Dosha analysis and holistic lifestyle prescription."
        },
        "AYUSH_Homeopathy": {
            "departmentCode": "HOMEO",
            "doctorName": "Dr. S. K. Roy",
            "doctorTitle": "Homeopathic Physician (BHMS, MD Hom)",
            "roomNumber": "HOMEO-01",
            "floorLocation": "Ground Floor (AYUSH Homeopathy OPD Wing)",
            "defaultReason": "Classical Totality evaluation, Thermals, Modalities analysis and Similimum repertorization."
        },
        "General_Medicine": {
            "departmentCode": "GEN_MED",
            "doctorName": "Dr. Subhash Chandra",
            "doctorTitle": "Senior Consultant Physician (Internal Medicine)",
            "roomNumber": "Room 101",
            "floorLocation": "Ground Floor (Main Central OPD Wing)",
            "defaultReason": "Complete general medical evaluation and vitals assessment."
        },
        "Emergency": {
            "departmentCode": "EMERG",
            "doctorName": "Casualty Medical Officer & Code Team",
            "doctorTitle": "Emergency Medicine and Acute Resuscitation Unit",
            "roomNumber": "ER Bay-1",
            "floorLocation": "Ground Floor (Emergency Trauma Center - Red Zone)",
            "defaultReason": "STAT Priority Emergency Triage: Immediate resuscitation, vitals stabilization and monitoring."
        }
    }

    # Specialty keyword matching rules
    RULES = [
        ("Ophthalmology", [
            r"\b(eye|eyes|vision|sight|blur|blurry|cataract|chashma|power|aankh|aankhon|aankhe|conjunctiv|spectacle|lens|retina|cornea|glaucoma|watery\s*eye|eye\s*strain|reading\s*difficulty)\b"
        ]),
        ("Cardiology", [
            r"\b(chest|heart|seene|chaati|chhati|palpitation|dhadkan|angina|cardio|bp|blood\s*pressure|hypertension|cholesterol|stent|coronary)\b"
        ]),
        ("Gastroenterology", [
            r"\b(stomach|abdomen|pet|acidity|gas|constipat|kabz|loose\s*motion|diarrhea|ulcer|vomit|vomiting|nausea|gerd|reflux|burning|heartburn|liver|piles|bawasir|jaundice|peeliya)\b"
        ]),
        ("Orthopedics", [
            r"\b(bone|bones|joint|joints|knee|knees|haddi|haddiyan|ghutna|ghutne|kamar|back|backache|fracture|sprain|arthritis|gathiya|ligament|shoulder|spine|disc|heel|ankylosing|osteoporosis)\b"
        ]),
        ("Pulmonology", [
            r"\b(lung|lungs|cough|khansi|breath|breathing|saans|asthma|copd|phlegm|balgham|wheez|wheezing|bronchitis|tuberculosis|tb|pneumonia|shortness\s*of\s*breath)\b"
        ]),
        ("Neurology", [
            r"\b(headache|migraine|sir\s*dard|sar\s*dard|dizz|dizziness|chakkar|vertigo|weakness|stroke|paralysis|numb|numbness|sunn|seizure|mirgi|tremor|epilepsy|brain)\b"
        ]),
        ("Endocrinology", [
            r"\b(sugar|diabetes|diabetic|thirst|pyas|peshab|frequent\s*urination|polyuria|weight\s*loss|thyroid|hypothyroid|goitre|fatigue|hba1c|endocrine)\b"
        ]),
        ("Dermatology", [
            r"\b(skin|rash|rashes|itch|itching|khujli|pimple|pimples|acne|eczema|fungal|ringworm|daag|boil|boils|psoriasis|allergy|urticaria|derma|scabies)\b"
        ]),
        ("ENT", [
            r"\b(ear|ears|kaan|hearing|throat|sore\s*throat|gala|tonsil|tonsils|nose|naak|sinus|sinusitis|cold|rhinitis|hoarseness|voice|ear\s*pain|ear\s*discharge)\b"
        ])
    ]

    # Non-specific / ambiguous phrases that indicate patient needs staff nurse guidance
    AMBIGUOUS_PATTERNS = [
        r"\b(not\s*feeling\s*well|overall\s*unwell|body\s*hurting\s*everywhere|sub\s*kuch\s*dard|kuch\s*samajh\s*nahi\s*aaraha|don'?t\s*know|just\s*checkup|general\s*checkup|unclear|multiple\s*problems|sar\s*se\s*paon\s*tak\s*dard|weak\s*all\s*over)\b",
        r"^(general|checkup|regular|normal|feeling\s*unwell|weakness|body\s*pain|tabiyat\s*kharab|kamzori|dard|pain|help|not\s*well|asustho)$",
        r"^(sirf\s*checkup|doctor\s*dikhao|kuch\s*theek\s*nahi\s*hai|shorir\s*kharap)$"
    ]

    @classmethod
    def determine_routing(
        cls,
        chief_complaint: str,
        conversation_turns: List[QAPair],
        age: int = 30,
        ayush_mode: bool = False,
        homeopathy_mode: bool = False,
        medical_system: str = "allopathy",
        red_flag_active: bool = False,
        red_flag_triggered: bool = False,
        **kwargs
    ) -> DepartmentRouting:
        """
        Computes the most appropriate hospital department and specialist doctor.
        Flagged as ambiguous if the condition cannot be confidently assigned to a single specialist.
        """
        # 1. Immediate Emergency Red Flag Priority
        if red_flag_active or red_flag_triggered:
            meta = cls.DEPARTMENT_DIRECTORY["Emergency"]
            return DepartmentRouting(
                department="Emergency Casualty",
                departmentCode=meta["departmentCode"],
                doctorName=meta["doctorName"],
                doctorTitle=meta["doctorTitle"],
                roomNumber=meta["roomNumber"],
                floorLocation=meta["floorLocation"],
                isAmbiguous=False,
                assignedBy="emergency-protocol",
                routingReason="Priority acute clinical red-flag detected. Immediate casualty resuscitation transfer.",
                confidence=1.0
            )

        # 2. AYUSH Homeopathy Mode
        if homeopathy_mode or medical_system == "homeopathy":
            meta = cls.DEPARTMENT_DIRECTORY["AYUSH_Homeopathy"]
            return DepartmentRouting(
                department="AYUSH Homeopathy",
                departmentCode=meta["departmentCode"],
                doctorName=meta["doctorName"],
                doctorTitle=meta["doctorTitle"],
                roomNumber=meta["roomNumber"],
                floorLocation=meta["floorLocation"],
                isAmbiguous=False,
                assignedBy="ai-triage",
                routingReason=meta["defaultReason"],
                confidence=0.98
            )

        # 3. AYUSH Ayurveda Mode Active
        if ayush_mode or medical_system == "ayurveda":
            meta = cls.DEPARTMENT_DIRECTORY["AYUSH_Ayurveda"]
            return DepartmentRouting(
                department="AYUSH Ayurveda",
                departmentCode=meta["departmentCode"],
                doctorName=meta["doctorName"],
                doctorTitle=meta["doctorTitle"],
                roomNumber=meta["roomNumber"],
                floorLocation=meta["floorLocation"],
                isAmbiguous=False,
                assignedBy="ai-triage",
                routingReason=meta["defaultReason"],
                confidence=0.98
            )

        # 4. Pediatric Demographics (< 12 years)
        if age < 12 and not any("eye" in chief_complaint.lower() or "chashma" in chief_complaint.lower() for _ in [0]):
            meta = cls.DEPARTMENT_DIRECTORY["Pediatrics"]
            return DepartmentRouting(
                department="Pediatrics",
                departmentCode=meta["departmentCode"],
                doctorName=meta["doctorName"],
                doctorTitle=meta["doctorTitle"],
                roomNumber=meta["roomNumber"],
                floorLocation=meta["floorLocation"],
                isAmbiguous=False,
                assignedBy="ai-triage",
                routingReason=f"Patient is {age} years of age. Routed to Senior Consultant Pediatrician for specialized pediatric care.",
                confidence=0.95
            )

        # Aggregate text for analysis
        all_text = chief_complaint.lower()
        for turn in conversation_turns:
            all_text += " " + turn.patientAnswer.lower()

        # Check for ambiguity
        for amb_pat in cls.AMBIGUOUS_PATTERNS:
            if re.search(amb_pat, all_text, re.IGNORECASE):
                meta = cls.DEPARTMENT_DIRECTORY["General_Medicine"]
                return DepartmentRouting(
                    department="General Medicine (Triage Review)",
                    departmentCode="TRIAGE_REQ",
                    doctorName="Triage Medical Officer / Sister Incharge",
                    doctorTitle="OPD Intake & Triage Assessment Unit",
                    roomNumber="Room 101 / Triage Desk",
                    floorLocation="Ground Floor (Main Central Reception)",
                    isAmbiguous=True,
                    assignedBy="ai-triage",
                    routingReason="Symptoms appear multi-system or non-specific. OPD Staff Nurse alerted for physical guidance.",
                    confidence=0.45
                )

        # Specialty pattern matching
        scores: Dict[str, int] = {}
        for dept, patterns in cls.RULES:
            score = 0
            for pat in patterns:
                matches = re.findall(pat, all_text, re.IGNORECASE)
                score += len(matches)
            if score > 0:
                scores[dept] = score

        if not scores:
            # Fallback to General Medicine
            meta = cls.DEPARTMENT_DIRECTORY["General_Medicine"]
            return DepartmentRouting(
                department="General Medicine",
                departmentCode=meta["departmentCode"],
                doctorName=meta["doctorName"],
                doctorTitle=meta["doctorTitle"],
                roomNumber=meta["roomNumber"],
                floorLocation=meta["floorLocation"],
                isAmbiguous=False,
                assignedBy="ai-triage",
                routingReason=meta["defaultReason"],
                confidence=0.75
            )

        # Pick highest scoring specialty
        top_dept = max(scores, key=scores.get)
        meta = cls.DEPARTMENT_DIRECTORY[top_dept]

        return DepartmentRouting(
            department=top_dept,
            departmentCode=meta["departmentCode"],
            doctorName=meta["doctorName"],
            doctorTitle=meta["doctorTitle"],
            roomNumber=meta["roomNumber"],
            floorLocation=meta["floorLocation"],
            isAmbiguous=False,
            assignedBy="ai-triage",
            routingReason=meta["defaultReason"],
            confidence=0.92
        )

routing_service = DepartmentRoutingService()
