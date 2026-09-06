import json
import re
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings
from app.models import (
    QAPair, AdaptiveQuestionResponse, HistoryOfPresentIllness, 
    DrugAllergyHistory, PersonalHistory, PatientVitals,
    DifferentialDiagnosis, SuggestedDrug, CDSSResponse
)

# Allergy status is clinically tri-state: denied, unknown, or present.
# Match on whole words only -- an unanchored "no" substring silently inverts real
# allergies whose drug name happens to contain those letters (Novamox, Norflox,
# Novalgin) and turns "I don't know" into a confident denial.
UNCERTAIN_ALLERGY_RE = re.compile(
    r"\b(don'?t know|do ?not know|not sure|unsure|unknown|can'?t remember|"
    r"cannot remember|no idea|not aware|never checked|maybe|possibly)\b",
    re.IGNORECASE,
)
DENIED_ALLERGY_RE = re.compile(
    r"\b(nkda|nil|none|no|nothing|negative)\b|no known|not allergic|denies",
    re.IGNORECASE,
)
ALLERGY_UNKNOWN_TEXT = (
    "Allergy status UNKNOWN - patient could not confirm. Verify before prescribing."
)


class LLMService:
    """
    Nurse-Grade Adaptive Conversational Clinical Intake Engine for MediKiosk.
    Conducts comprehensive, multi-step symptom-specific diagnostic interviewing 
    (7-8 sequential clinical turns) and synthesizes rich nurse triage notes for the attending physician.
    """
    
    SYSTEM_PROMPT_ALLOPATHIC = """
You are an experienced clinical triage nurse AI engine for 'MediKiosk' in an Indian hospital OPD.
Your goal is to conduct a thorough pre-consultation interview with the patient just like an experienced human OPD triage nurse would.

INTERVIEWING PROTOCOL (Ask up to 7-8 focused, specialty-specific questions):
1. Symptom Nature & Character: Exact location, pain quality (crushing/burning/sharp/dull), severity.
2. Chronology & Onset: Exact duration, sudden vs gradual onset, frequency/progression.
3. Triggers & Relieving factors: Relation to exertion/meals/posture/rest, what helps or worsens.
4. Pertinent Positives & Negatives: Associated systemic complaints, ruling out acute red flags.
5. Comorbidities & Past Medical History: Diabetes duration, Hypertension, Heart disease, TB, Asthma, prior surgeries.
6. Medication Regimen & Compliance: Current prescription tablets, frequency, adherence.
7. Drug Allergies: Specific allergic drugs (Penicillin/Sulfa/NSAIDs) and reaction type.
8. Personal / Family Context: Diet, tobacco/alcohol, relevant family illnesses.

RULES:
- Ask EXACTLY ONE high-yield, respectful question in clear language (under 20 words).
- Provide 3-4 SHORT MULTIPLE-CHOICE OPTIONS (2-5 words each) representing common patient answers.
- Once 7-8 thorough turns are recorded (or if patient requests to proceed), set `"done": true`.
- Output STRICT JSON ONLY.
"""

    SYSTEM_PROMPT_HOMEOPATHY = """
You are the AYUSH / Homeopathic OPD Triage Nurse AI engine for 'MediKiosk'.
Conduct a comprehensive Homeopathic pre-consultation intake based on classical Homeopathic principles (Dr. Hahnemann's Organon of Medicine):
1. Chief Complaint & Baseline Vitals (Height, Weight, BP)
2. Thermal State: Chilly patient (sensitive to cold, draft, wraps up) vs Hot patient (sensitive to heat, seeks cool air/fans).
3. Thirst & Appetite: Thirstlessness vs Extreme Thirst (large vs small quantities), food cravings/aversions (sweets, spicy, salt, sour, fats).
4. Modalities (Aggravation < and Amelioration >): Factors that worsen or relieve the trouble (time e.g. morning/night/3 AM, motion, rest, cold air, warm drinks, pressure, weather).
5. Mind & Emotional Generals: Restlessness, anxiety about health, irritability/anger, weepiness/mildness seeking consolation, fear.
6. Physical Generals & Side Affinity: Right-sided vs Left-sided, perspiration pattern (head, palms, night), sleep position.
7. Past History & Suppressions: Past skin eruptions, chronic suppression of discharges, family history.
8. Current Homeopathic or Allopathic Medicines & Drug Allergies.

Ask exactly ONE clear question at a time with 3-4 options. Set `"done": true` once 7-8 comprehensive turns are gathered.
Output STRICT JSON ONLY.
"""

    SYSTEM_PROMPT_AYUSH = """
You are the expert AYUSH / Ayurvedic OPD Triage AI Engine for 'MediKiosk' in an Indian Government AYUSH Hospital.
Conduct a comprehensive, classical Ayurvedic clinical history intake adhering strictly to Charaka & Sushruta Samhita standards (Roga-Rogi Pariksha, Dashavidha Pariksha, and Ashtavidha Pariksha principles):

AYURVEDIC CLINICAL PARIKSHA PROTOCOL:
1. Roga Lakshana & Doshic Presentation: Assess specific Vataja (shifting throbbing pain, dryness, numbness, cold intolerance), Pittaja (burning sensation/Daha, sour reflux/Amlapitta, sweating, inflammation), or Kaphaja (heaviness/Gaurava, excessive mucus, sluggishness, swelling/Sotha) symptoms.
2. Agni Pariksha (Jatharagni / Digestive Fire): Assess Mandagni (sluggish fire, heaviness after light meals), Tikshnagni (sharp burning hunger, hyperacidity), Vishamagni (fluctuating hunger, bloating, gas), vs Samagni (balanced on-time digestion).
3. Kostha & Mala Pariksha (Bowel Nature & Evacuation): Krura Kostha (dry, hard, infrequent stools, constipation), Mrudu Kostha (soft, loose stools 2-3 times daily, sensitive to warm milk/ghee), Madhyama Kostha (formed regular morning evacuation), and Sama vs Nirama stool character.
4. Ama & Srotorodha Lakshana (Metabolic Toxicity & Bio-Channel Obstruction): Presence of morning lethargy (Alasya), heavy coated tongue (Sama Jihva), bad breath, lack of taste (Aruchi), body stiffness upon waking.
5. Ahara & Vihara Hetu (Dietetic & Lifestyle Causative Factors): Intake of Viruddha Ahara (incompatible combinations), Katu-Amla-Lavana (excessive spicy/sour/salty food), late-night meals (Ratri-bhojana), daytime sleeping (Divaswapna), night awakening (Ratrijagarana), or suppression of natural urges (Vega-dharana).
6. Deha-Prakriti Assessment (Constitutional Phenotype): Vata-Pitta, Pitta-Kapha, Kapha-Vata, or Sannipataja constitutional traits, thermal preference (Sheeta vs Ushna Asahyata), skin texture, and stress temperament.
7. Nidra & Manasika Status: Sleep quality (Anidra/disturbed vs Atinidra/heavy sleep), mental state (Satva, Rajas/anger-anxiety, Tamas/inertia).
8. Current Ayurvedic Formulations (Kashayams, Churnas, Asava-Arishta, Guggulu, Rasayanas) & Modern Allopathic Medications, along with Pathya-Apathya (dietary restriction) compliance and herb allergies.

RULES:
- Ask EXACTLY ONE high-yield, classical Ayurvedic question in simple, patient-friendly language with bilingual Sanskrit/English clinical terms.
- Provide 4 SHORT MULTIPLE-CHOICE OPTIONS (2-5 words each) representing standard Ayurvedic clinical findings.
- Set `"done": true` once 7-8 thorough turns are gathered.
- Output STRICT JSON ONLY.
"""

    SYSTEM_PROMPT_CDSS = """
You are an expert Clinical Decision Support System (CDSS) for attending hospital OPD physicians.
Your objective is to reduce physician cognitive stress by analyzing the patient's pre-consultation intake data and providing evidence-based, actionable treatment and diagnosis recommendations.

RETURN STRICT JSON ONLY MATCHING THIS SCHEMA:
{
  "differentialDiagnoses": [
    {
      "condition": "Condition Name",
      "icd10": "ICD-10 Code (e.g. I20.9, K21.0)",
      "probability": "High" | "Moderate" | "Consider / Low",
      "rationale": "1-2 sentence evidence-based clinical reasoning based on patient's symptoms and history"
    }
  ],
  "suggestedTreatments": [
    {
      "name": "Drug Name & Strength (e.g. Tab Pantoprazole 40mg)",
      "dosage": "1 tablet",
      "frequency": "Once daily before breakfast",
      "duration": "14 days",
      "rationale": "First-line proton pump inhibitor for acid peptic relief",
      "contraindicationWarning": "None / Note any allergy contraindications"
    }
  ],
  "keyPointsToNotice": [
    "Key physical examination sign or maneuver to verify (e.g. Murphy's sign, lung wheezing, bilateral pedal pulse)",
    "Critical red flag or warning sign to check"
  ],
  "recommendedInvestigations": [
    "Recommended lab or diagnostic test (e.g. 12-lead ECG, CBC, Fasting Lipid Panel, Upper GI Endoscopy)"
  ],
  "clinicalRationale": "Concise 2-sentence clinical synthesis for attending physician review"
}

SAFETY RULES:
- Never recommend drugs that the patient is documented as allergic to. If patient is allergic to Penicillins/Amoxicillin, recommend Macrolides/Cephalosporins or note the allergy.
- Provide practical adult outpatient dosages standard in Indian hospital clinical practice.
"""

    @classmethod
    def identify_symptom_category(cls, text: str) -> str:
        """Identifies medical specialty category from patient's chief complaint."""
        t = (text or "").lower()
        if any(w in t for w in ["chest", "heart", "seene", "chaati", "chhati", "palpitation", "dhadkan", "angina"]):
            return "Cardiovascular"
        elif any(w in t for w in ["stomach", "abdom", "pet", "acidity", "vomit", "gas", "jalan", "loose motion", "diarrhea", "constipat", "jaundice", "piliya"]):
            return "Gastrointestinal"
        elif any(w in t for w in ["cough", "breath", "saans", "wheez", "asthma", "cold", "sore throat", "gala", "phlegm", "balgam", "shwaas"]):
            return "Respiratory"
        elif any(w in t for w in ["headache", "sir dard", "chakkar", "dizz", "vertigo", "weakness", "stroke", "paralysis", "numb", "sunn", "seizure", "mirgi"]):
            return "Neurological"
        elif any(w in t for w in ["joint", "knee", "ghutna", "back", "kamar", "stiff", "arthritis", "sandhivata", "swelling", "sujan", "bone"]):
            return "Musculoskeletal"
        elif any(w in t for w in ["fever", "bukhar", "jwar", "chills", "thand", "dengue", "malaria", "typhoid", "infection", "shivering"]):
            return "Infectious_Fever"
        elif any(w in t for w in ["sugar", "diabetes", "urine", "peshab", "thirst", "pyas", "weight", "thyroid", "fatigue", "kamzori"]):
            return "Endocrine_Metabolic"
        elif any(w in t for w in ["eye", "eyes", "vision", "sight", "blur", "cataract", "chashma", "power", "aankh", "aankhon", "spectacle", "reading"]):
            return "Ophthalmology"
        elif any(w in t for w in ["skin", "rash", "itch", "khujli", "pimple", "acne", "eczema", "fungal", "daag", "boil", "psoriasis"]):
            return "Dermatology"
        elif any(w in t for w in ["ear", "kaan", "hearing", "throat", "gala", "nose", "naak", "sinus", "tonsil"]):
            return "ENT"
        else:
            return "General_OPD"

    @classmethod
    async def get_next_question(
        cls,
        chief_complaint: str,
        conversation_turns: List[QAPair],
        ayush_mode: bool = False,
        homeopathy_mode: bool = False,
        medical_system: str = "allopathy",
        language: str = "en",
        red_flag_active: bool = False
    ) -> AdaptiveQuestionResponse:
        """
        Generate next adaptive question across a comprehensive 7-8 turn clinical interview.
        """
        turn_count = len(conversation_turns)
        symptom_category = cls.identify_symptom_category(chief_complaint)
        
        # If true emergency red flag is active, wrap up early for casualty transfer
        if red_flag_active and turn_count >= 2:
            return AdaptiveQuestionResponse(
                question="Emergency priority flagged. Do you have any medicine allergies before casualty transfer?",
                field="emergency_allergy_check",
                options=["No known drug allergies", "Allergic to Penicillin / Sulfa", "Allergic to Aspirin / NSAIDs", "Other allergy"],
                done=True,
                progressPercent=100,
                source="fallback",
                symptomCategory=symptom_category
            )

        # Allow full 7-8 turns for comprehensive nurse-grade intake
        if turn_count >= 7:
            return AdaptiveQuestionResponse(
                question="Thank you for providing your complete medical history. Your comprehensive nurse summary is ready. Please proceed to the Document Scan step.",
                field="completion",
                options=["Proceed to Document Scan"],
                done=True,
                progressPercent=100,
                source="fallback",
                symptomCategory=symptom_category
            )

        # Build conversation context transcript
        conv_text = f"Patient Chief Complaint: {chief_complaint} (Specialty: {symptom_category})\n"
        for i, turn in enumerate(conversation_turns, 1):
            conv_text += f"Q{i} ({turn.field}): {turn.questionText}\n"
            conv_text += f"A{i}: {turn.patientAnswer}\n"
            
        progress_estimate = min(15 + (turn_count * 12), 95)
        user_prompt = f"{conv_text}\nGenerate the next sequential nurse intake question (Turn {turn_count + 1} of 8) in JSON format. Progress: {progress_estimate}%."
        
        if homeopathy_mode or medical_system == "homeopathy":
            system_prompt = cls.SYSTEM_PROMPT_HOMEOPATHY
        elif ayush_mode or medical_system == "ayurveda":
            system_prompt = cls.SYSTEM_PROMPT_AYUSH
        else:
            system_prompt = cls.SYSTEM_PROMPT_ALLOPATHIC

        # Try Live LLM call if provider configured
        llm_response = await cls._call_llm_provider(system_prompt, user_prompt)
        if llm_response:
            try:
                cleaned = cls._extract_json(llm_response)
                data = json.loads(cleaned)
                q_text = data.get("question", "").strip()
                f_key = data.get("field", "").strip()
                
                # Verify that LLM did not repeat an already asked question
                is_duplicate = any(t.field == f_key or t.questionText.lower() == q_text.lower() for t in conversation_turns)
                if q_text and not is_duplicate:
                    return AdaptiveQuestionResponse(
                        question=q_text,
                        field=f_key or f"adaptive_turn_{turn_count + 1}",
                        options=data.get("options", ["None", "Mild symptoms", "Moderate symptoms", "Other"]),
                        done=data.get("done", False) or (turn_count >= 7),
                        progressPercent=data.get("progressPercent", progress_estimate),
                        source="llm",
                        symptomCategory=data.get("symptomCategory", symptom_category)
                    )
            except Exception as parse_err:
                print(f"[LLMService] JSON parse error: {parse_err}")

        # Comprehensive Symptom-Specific Sequential Engine
        return cls._symptom_specific_fallback(chief_complaint, conversation_turns, ayush_mode, homeopathy_mode, medical_system, turn_count, symptom_category, red_flag_active)

    @classmethod
    def _symptom_specific_fallback(
        cls,
        chief_complaint: str,
        conversation_turns: List[QAPair],
        ayush_mode: bool,
        homeopathy_mode: bool,
        medical_system: str,
        turn_count: int,
        category: str,
        red_flag_active: bool = False
    ) -> AdaptiveQuestionResponse:
        """
        Comprehensive clinical fallback with 7-8 sequential nurse-level diagnostic turns per specialty.
        Uses answered fields filtering with turn-index progression to strictly guarantee questions never repeat.
        """
        answered_fields = {t.field for t in conversation_turns}

        if homeopathy_mode or medical_system == "homeopathy":
            flow = [
                ("vitals_baseline_common", "What are your approximate Height (cm), Weight (kg), and Blood Pressure (BP)? (Standard Baseline Vitals for OPD Care)", ["Height: 168 cm, Weight: 65 kg, BP: 120/80 mmHg (Normal)", "Height: 160 cm, Weight: 75 kg, BP: 140/90 mmHg (High BP)", "Height: 172 cm, Weight: 55 kg, BP: 110/70 mmHg (Low/Normal BP)", "Prefer not to disclose / Skip this data"]),
                ("thermal_state", "How do you react to weather and temperatures (Thermal State)?", ["Chilly patient (Dislike cold air/drafts, need warm blankets)", "Hot patient (Dislike heat/stuffy rooms, want fan/cool air)", "Ambithermal / Tolerates both cold and heat equally", "Sensitive to sudden weather changes / Damp weather"]),
                ("thirst_appetite", "How is your thirst for water and appetite pattern?", ["Thirsty for large quantities at long intervals (Bryonia)", "Thirsty for small sips frequently (Arsenicum)", "Thirstless even with fever/dryness (Pulsatilla/Apis)", "Normal thirst (2-3 liters daily) with regular appetite"]),
                ("homeopathic_modalities", "What makes your trouble worse (< Aggravation) or better (> Amelioration)?", ["Worse from cold air/drafts, better from warm drinks/wraps", "Worse from slightest motion/movement, better by absolute rest", "Worse at night or early morning (2-4 AM), better by warm applications", "Worse in stuffy warm rooms, better in fresh open air"]),
                ("mind_emotional_generals", "How would you describe your mental and emotional temperament?", ["Restless, anxious, fear of disease (Arsenicum / Aconite)", "Irritable, impatient, fastidious, angry easily (Nux Vomica)", "Mild, gentle, weeps easily, likes consolation (Pulsatilla)", "Calm, cheerful, emotionally balanced"]),
                ("food_cravings_aversions", "Do you have strong cravings or aversions for specific foods?", ["Craving sweets, sugar, or warm food", "Craving spicy, pungent, or salty food", "Aversion to fatty/oily food or milk", "Normal balanced diet without strong cravings"]),
                ("side_affinity_perspiration", "Is your complaint more on one side, and how is your perspiration?", ["Right-sided complaint (Lycopodium / Belladonna)", "Left-sided complaint (Lachesis / Spigelia)", "Profuse sweating on head / palms / night", "Normal sweating, both sides affected equally"]),
                ("medications_homeopathy", "Are you currently taking any Homeopathic remedies or regular Allopathic medicines?", ["Taking Homeopathic drops/globules currently", "Taking regular Allopathic medicines for BP/Sugar", "Both Homeopathic and Allopathic", "No medications currently"])
            ]
            flow_category = "AYUSH_Homeopathy"

        elif ayush_mode or medical_system == "ayurveda":
            flow = [
                ("dosha_lakshana", "What is the primary nature of your physical discomfort and Doshic manifestation?", ["Shifting piercing pain, dryness & stiffness (Vataja Lakshana)", "Burning sensation, intense heat & sour reflux (Pittaja Lakshana)", "Heavy sluggish body, coldness & mucus/swelling (Kaphaja Lakshana)", "Mixed pain and burning symptoms (Dwandwaja / Vata-Pitta)"]),
                ("agni_digestion", "How is your digestive fire (Jatharagni), appetite strength, and food digestion speed?", ["Sluggish digestion & heavy belly after light food (Mandagni)", "Intense sharp burning hunger & excessive thirst (Tikshnagni)", "Unpredictable fluctuating hunger with gas/bloating (Vishamagni)", "Balanced healthy appetite digesting in 3-4 hours (Samagni)"]),
                ("kostha_bowel", "What is the nature of your bowel evacuation and stool consistency (Kostha Pariksha)?", ["Hard dry stools with straining / Chronic constipation (Krura Kostha)", "Soft loose stools 2-3 times daily / Sensitive to warm milk (Mrudu Kostha)", "Regular smooth formed morning evacuation (Madhyama Kostha)", "Sticky foul-smelling stools that sink in water (Sama Mala)"]),
                ("ama_srotorodha", "Do you feel morning heaviness, fatigue, or have a white-coated tongue (Ama Lakshana)?", ["Heavy coated tongue, morning fatigue & body heaviness (Sama / Ama present)", "Loss of taste (Aruchi) with sluggish heavy limbs (Alasya & Srotorodha)", "Fresh light body and clean pink tongue upon waking (Nirama / No Ama)", "Occasional morning heaviness clearing after warm water"]),
                ("ahara_vihara_hetu", "What are your common dietary habits, food cravings, and daily routine (Ahara-Vihara Hetu)?", ["Frequently eat spicy, sour, fried or late-night food (Pitta-Vata Hetu)", "Heavy, sweet, cold or dairy-rich food / Day sleep (Kapha Hetu)", "Eat dry/raw foods with irregular meal timings (Vata Hetu)", "Fresh warm home-cooked balanced diet (Sattvic Ahara)"]),
                ("prakriti_assessment", "How would you describe your natural lifelong body constitution & thermal tolerance (Prakriti)?", ["Lean frame / Dry skin / Intolerant to cold winds (Vata-Pitta Prakriti)", "Medium build / Warm body / Intolerant to sun & heat (Pitta-Kapha Prakriti)", "Broad sturdy frame / Cool smooth skin / Intolerant to damp cold (Kapha-Vata Prakriti)", "Balanced Tridosha constitution (Sama Prakriti)"]),
                ("nidra_sleep", "How is your sleep pattern (Nidra) and do you tend to hold back natural urges (Vega-Dharana)?", ["Light disturbed sleep / Racing anxious thoughts (Vata-Rajas)", "Moderate sleep with vivid dreams / Waking hot or irritable (Pitta-Rajas)", "Heavy prolonged sleep / Daytime drowsiness (Kapha-Tamas)", "Sound refreshing 7-hour sleep / Regular natural urge release"]),
                ("medications_ayush", "Are you taking any Ayurvedic formulations (Kashayam/Churna/Rasayana) or Allopathic medicines?", ["Taking Ayurvedic classical medicines (Kwathas / Churnas / Asavas)", "Taking regular Allopathic medicines for BP / Sugar / Thyroid", "Taking both Ayurvedic and Allopathic medicines", "No current medications / Following dietary guidelines (Pathya)"])
            ]
            flow_category = "AYUSH_Ayurveda"

        # --- 1. CARDIOVASCULAR ---
        elif category == "Cardiovascular":
            flow = [
                ("pain_character", "What does the chest discomfort feel like?", ["Heavy squeezing / Tight band pressure", "Sharp / Stabbing pain on deep breath", "Burning sensation behind breastbone", "Dull ache / Mild discomfort"]),
                ("radiation_site", "Does the pain spread anywhere to your arm, neck, jaw, or back?", ["Spreads to left arm and shoulder", "Spreads to neck and jaw", "Spreads between shoulder blades in back", "Stays strictly in center of chest"]),
                ("onset_duration", "When did this pain start and how long does an episode last?", ["Started suddenly today (Acute)", "Past 2 to 3 days (Intermittent episodes)", "Episodes last 5 to 15 minutes", "Continuous ongoing ache"]),
                ("triggers_relief", "What brings on the pain and what gives relief?", ["Triggered by physical exertion / climbing stairs", "Occurs at rest or during emotional stress", "Relieved within minutes by rest / Sorbitrate", "Relieved by antacids / belching"]),
                ("associated_autonomic", "Are you experiencing shortness of breath, cold sweating, or palpitations?", ["Shortness of breath on walking", "Profuse cold sweating & anxiety", "Rapid fluttering heartbeat (Palpitations)", "No breathlessness, no sweating"]),
                ("cardiac_risk_factors", "Do you have any cardiovascular risk factors or existing conditions?", ["High Blood Pressure (Hypertension)", "Type 2 Diabetes Mellitus", "History of Tobacco / Cigarette smoking", "Prior Stent / Angioplasty / Family history"]),
                ("current_cardiac_meds", "What regular daily heart, BP, or diabetes tablets do you take?", ["Taking daily BP tablets (e.g. Telmisartan)", "Taking Blood thinners / Statins (Aspirin/Atorva)", "Taking daily Sugar/Diabetes tablets", "No regular daily medications"]),
                ("drug_allergies_cardiac", "Do you have any known medicine allergies (e.g. Aspirin, Penicillin)?", ["No known drug allergies (NKDA)", "Allergic to Aspirin / NSAID painkillers", "Allergic to Penicillin / Antibiotics", "Other specific drug allergy"])
            ]
            flow_category = "Cardiovascular"

        # --- 2. GASTROINTESTINAL ---
        elif category == "Gastrointestinal":
            flow = [
                ("gi_site_character", "Where exactly is the stomach pain and what type of pain is it?", ["Upper center (Epigastrium) - Burning pain", "Right upper quadrant under ribs - Colicky", "Lower right abdomen - Sharp persistent pain", "Diffuse bloating & cramping across belly"]),
                ("onset_progression", "How long have you had this stomach complaint and is it getting worse?", ["Started 1 to 2 days ago (Acute)", "Ongoing for past 2 to 4 weeks", "Chronic / Recurrent for several months", "Occurs after specific meals"]),
                ("meals_relationship", "How is the pain related to food and meal timings?", ["Worse on empty stomach / Relieved by milk", "Worse 30 to 60 mins after spicy/fatty food", "Occurs immediately after eating anything", "Unrelated to meals"]),
                ("gi_associated_nausea", "Are you having nausea, vomiting, loss of appetite, or bloating?", ["Frequent sour belching & acid reflux", "Nausea and vomiting of food particles", "Severe abdominal bloating and feeling full quickly", "No vomiting, good appetite"]),
                ("red_flags_gi", "Have you noticed any blood in vomit, dark black stools, or yellow eyes?", ["No blood in vomit, normal stools", "Black tarry stool (Melena)", "Yellowish eyes or dark urine (Jaundice)", "Occasional fresh blood with hard stools"]),
                ("past_gi_history", "Do you have a history of Acidity, Stomach Ulcers, Gallstones, or Fatty Liver?", ["History of Gastritis / GERD / Ulcers", "History of Gallbladder stones", "Fatty Liver / High cholesterol", "No prior digestive illnesses"]),
                ("current_gi_meds", "What stomach or pain medicines do you take regularly?", ["Takes regular antacids (Pantocid/Pan-40)", "Frequently takes painkillers for body aches", "Takes home Ayurvedic remedies", "No regular medicines"]),
                ("lifestyle_diet_allergies", "How is your diet and do you have any food or medicine allergies?", ["Spicy / Fried / Non-vegetarian diet", "Vegetarian home-cooked diet", "Allergic to certain antibiotics or painkillers", "No known allergies"])
            ]
            flow_category = "Gastrointestinal"

        # --- 3. RESPIRATORY ---
        elif category == "Respiratory":
            flow = [
                ("cough_nature", "How long have you had cough and is it dry or productive?", ["Dry hacking cough without sputum", "Thick yellow / green purulent sputum", "Cough with blood spots / Hemoptysis", "Cough primarily at night / early morning"]),
                ("onset_duration_resp", "When did these breathing or cough symptoms begin?", ["Acute onset 2 to 4 days ago", "Past 1 to 2 weeks following a cold", "Chronic cough lasting > 3 to 4 weeks", "Seasonal / Recurrent allergy cough"]),
                ("dyspnea_severity", "Do you feel breathlessness and when does it occur?", ["Breathless on climbing 1 flight of stairs", "Breathless even while sitting at rest", "Difficulty breathing when lying flat in bed", "No shortness of breath"]),
                ("wheeze_fever_signs", "Do you have audible wheezing, chest tightness, or fever?", ["Audible whistling wheeze in chest", "Tightness across chest with cold air", "High fever with chills and body aches", "No fever, no wheezing"]),
                ("throat_nasal_signs", "Do you have running nose, sore throat, or hoarseness of voice?", ["Sore scratchy throat and hoarse voice", "Nasal congestion and sneezing", "Post-nasal drip feeling in throat", "No throat or nasal symptoms"]),
                ("past_respiratory_history", "Do you have a history of Asthma, Bronchitis, TB, or Diabetes?", ["Known Asthma / Uses Inhaler", "History of Tuberculosis (TB) treatment", "Diabetes / Hypertension", "No prior chronic lung diseases"]),
                ("smoking_biomass_exposure", "Do you smoke tobacco or have exposure to chulha/biomass smoke or dust?", ["Current / Former tobacco smoker", "Exposed to cooking smoke / Dust / Pollution", "Passive smoker / Family member smokes", "Non-smoker, no major dust exposure"]),
                ("respiratory_meds_allergies", "What cough syrups, inhalers, or antibiotics have you taken?", ["Using Salbutamol / Budecort Inhaler", "Took Paracetamol and cough syrup", "Started an antibiotic course", "Allergic to Penicillin / Sulfa / NKDA"])
            ]
            flow_category = "Respiratory"

        # --- 4. MUSCULOSKELETAL ---
        elif category == "Musculoskeletal":
            flow = [
                ("joint_location_pattern", "Which joints are painful and is it on one or both sides?", ["Both knees (Bilateral, Right > Left)", "Small finger joints and wrists of both hands", "Lower back radiating down leg (Sciatica)", "Single joint (Shoulder / Hip / Ankle)"]),
                ("onset_chronology_msk", "How long have you had this joint/back pain?", ["Past few days after unusual exertion", "Over last 3 to 6 months (Gradual worsening)", "Chronic long-standing for > 1 to 2 years", "Recurrent episodes coming and going"]),
                ("morning_stiffness_duration", "Do your joints feel stiff when waking up in the morning?", ["Morning stiffness lasting > 45 minutes", "Mild morning stiffness < 15 minutes", "Stiffness improves after walking/warm bath", "Pain worse in the evening after standing"]),
                ("functional_mobility_limits", "How does the pain affect your daily walking and sitting?", ["Difficulty standing up from squatting/floor", "Difficulty climbing stairs / walking 500m", "Limitation in bending back or lifting weight", "Able to walk normally without support"]),
                ("swelling_warmth_crepitus", "Have you noticed joint swelling, redness, or crunching sounds?", ["Joint creaks / clicks on movement (Crepitus)", "Visible knee swelling and mild warmth", "Severe sudden redness and hot swelling", "No swelling, no redness"]),
                ("past_joint_trauma_gout", "Do you have a history of joint injury, high Uric acid, or Osteoarthritis?", ["Known Osteoarthritis / Wear and tear", "History of High Uric Acid (Gout)", "Past fracture or twisting sports injury", "No past joint problems"]),
                ("current_pain_medications", "What painkillers or supplements do you take for relief?", ["Takes Paracetamol / Calcium / Vit D", "Takes daily NSAID painkillers (Diclofenac/Brufen)", "Uses topical pain ointment and hot fomentation", "No regular medicines taken"]),
                ("gastric_tolerance_allergies", "Do painkillers cause stomach acidity, and do you have any allergies?", ["Painkillers cause severe stomach burning", "Tolerates painkillers well with antacids", "Allergic to NSAIDs / Aspirin", "No known drug allergies (NKDA)"])
            ]
            flow_category = "Musculoskeletal"

        # --- 5. INFECTIOUS & FEVER ---
        elif category == "Infectious_Fever":
            flow = [
                ("fever_pattern_grade", "How high is the fever and how many days has it been present?", ["1 to 2 days high fever (> 102 F) with shivering chills", "3 to 5 days continuous fever", "Intermittent fever rising mainly in evenings", "Low-grade feverish feeling with body ache"]),
                ("focal_infectious_symptoms", "Do you have any burning during urination, cough, or diarrhea?", ["Burning sensation during urination (Dysuria)", "Severe joint agony and body ache (Chikungunya-like)", "Watery diarrhea and abdominal cramps", "Headache behind eyes and runny nose"]),
                ("rash_bleeding_signs", "Have you noticed any skin rash, red spots, or bleeding from gums/nose?", ["Red skin spots / Rash on body", "Bleeding from gums or nose", "Extreme weakness when standing up", "No rash, no bleeding"]),
                ("chills_rigors_pattern", "Does the fever come with teeth-chattering shivering chills (Rigors)?", ["Severe shivering rigors requiring heavy blankets", "Mild chills before fever spikes", "Profuse sweating when fever drops", "No shivering or chills"]),
                ("travel_exposure_dengue", "Are there mosquito issues in your locality, or recent travel?", ["High mosquito density / Dengue cases in area", "Recent travel to forest/rural area", "Family members also ill with fever", "No known exposure or travel"]),
                ("past_medical_infections", "Do you have Diabetes, Kidney issues, or prior Malaria/Typhoid?", ["Type 2 Diabetes Mellitus", "History of Malaria or Typhoid", "Chronic kidney or liver disease", "No prior chronic illnesses"]),
                ("antipyretics_antibiotics_taken", "What fever medicines or antibiotics have you taken in last 48 hours?", ["Took Dolo 650 / Paracetamol (Drops temporarily)", "Started an antibiotic from local clinic", "Taking oral fluids (ORS) and rest", "No medicines taken yet"]),
                ("drug_allergies_fever", "Do you have any drug allergies (e.g., Sulfa, Penicillin, Paracetamol)?", ["No known drug allergies (NKDA)", "Allergic to Sulfa / Co-trimoxazole", "Allergic to Penicillin / Amoxicillin", "Other drug allergy"])
            ]
            flow_category = "Infectious_Fever"

        # --- 6. NEUROLOGICAL ---
        elif category == "Neurological":
            flow = [
                ("headache_character_site", "Where is the headache/dizziness located and what does it feel like?", ["One side of head / Throbbing pulsating (Migraine-like)", "Tight band around entire forehead (Tension)", "Behind eyes and sinus area with congestion", "Spinning room sensation / Dizziness (Vertigo)"]),
                ("headache_onset_duration", "When did this headache or dizziness begin and how long do episodes last?", ["Acute sudden onset today", "Episodes last 4 to 24 hours (Intermittent)", "Constant daily dull ache for past 2 weeks", "Triggered by rapid head turns or standing up"]),
                ("neurological_sensory_nausea", "Do you have nausea, sensitivity to bright light, or visual flashes?", ["Sensitivity to light and loud noise (Photophobia)", "Nausea and urge to vomit", "Zigzag flashing lights or blurriness before pain", "No nausea, no visual changes"]),
                ("headache_triggers", "What brings on or worsens the headache or dizzy spells?", ["Mental stress / Lack of sleep / Excessive screen time", "Skipping meals / Fasting", "Physical exertion / Bending forward", "No specific trigger identified"]),
                ("neuro_red_flags_check", "Are you experiencing any numbness, speech difficulty, or arm/leg weakness?", ["No weakness, no numbness (Ruled out focal deficit)", "Mild tingling in scalp or neck", "Neck stiffness and shoulder muscle tightness", "Trembling in hands when anxious"]),
                ("past_neuro_history", "Do you have a past history of Migraine, High BP, or Cervical Spondylosis?", ["Known history of Migraine", "High Blood Pressure (Hypertension)", "Cervical neck pain / Spondylosis", "No prior chronic illnesses"]),
                ("current_neuro_meds", "What pain relief tablets do you take for headache?", ["Takes Paracetamol / Saridon / Combiflam", "Takes specific Migraine medication (Triptans/Vasograin)", "Takes daily BP tablets", "No regular medications taken"]),
                ("drug_allergies_neuro", "Do you have any drug allergies or sensitivities?", ["No known drug allergies (NKDA)", "Allergic to NSAID painkillers / Aspirin", "Allergic to Penicillin / Sulfa", "Other drug allergy"])
            ]
            flow_category = "Neurological"

        # --- 7. ENDOCRINE & METABOLIC ---
        elif category == "Endocrine_Metabolic":
            flow = [
                ("glycemic_symptoms", "Are you experiencing increased thirst, frequent urination, or unexpected weight changes?", ["Frequent urination, especially at night (Nocturia)", "Excessive thirst and dry mouth", "Unintentional weight loss despite good appetite", "Extreme fatigue and lack of energy"]),
                ("duration_metabolic", "How long have you noticed these symptoms or had Diabetes/Thyroid?", ["Past few weeks (New onset symptoms)", "Known Type 2 Diabetes for 1 to 5 years", "Long-standing Diabetes > 5 to 10 years", "Recently detected high sugar on routine test"]),
                ("recent_glucose_values", "What are your recent blood sugar readings if known?", ["Fasting sugar > 150 mg/dL / Post-meal > 200 mg/dL", "Well-controlled sugars (Fasting 90-120 mg/dL)", "HbA1c was above 8.0% on last test", "Have not checked blood sugar recently"]),
                ("microvascular_screen", "Have you noticed any tingling/burning in feet or blurred vision?", ["Tingling / Burning / Numbness in soles of feet (Neuropathy)", "Blurry vision when reading", "Slow healing of minor cuts or sores", "No tingling in feet, normal vision"]),
                ("associated_comorbidities", "Do you have High Blood Pressure, High Cholesterol, or Thyroid problems?", ["Both High BP and Diabetes", "High Cholesterol / Dyslipidemia", "Hypothyroidism (Taking Thyroxine)", "No other chronic diseases"]),
                ("current_diabetic_meds", "What daily diabetes tablets or insulin do you take?", ["Taking Metformin / Glimepiride / Gliptins", "Taking Insulin injections daily", "Taking Ayurvedic / Herbal sugar remedies", "Not on any diabetes medicines currently"]),
                ("compliance_diet", "How regularly do you take your medicines and follow dietary guidance?", ["Takes medicines regularly every day", "Occasionally forgets doses", "Follows low-sugar diabetic diet", "Irregular meal timings"]),
                ("drug_allergies_endocrine", "Do you have any known medicine allergies (e.g. Sulfa, Metformin)?", ["No known drug allergies (NKDA)", "Allergic to Sulphonylureas / Sulfa", "Allergic to Penicillin / Antibiotics", "Other allergy"])
            ]
            flow_category = "Endocrine_Metabolic"

        # --- 8. GENERAL OPD ---
        else:
            flow = [
                ("symptom_onset_duration", "When did this problem start and how has it progressed?", ["Started suddenly today (Acute)", "Past 2 to 4 days (Worsening)", "Over last 1 to 2 weeks", "Chronic ongoing for months"]),
                ("symptom_severity_character", "How severe is this problem on a scale of 1 to 10?", ["Severe (8-10/10) - Disrupting daily routine", "Moderate (5-7/10) - Uncomfortable but managing", "Mild (1-4/10) - Nagging discomfort", "Comes and goes intermittently"]),
                ("triggers_aggravating", "What makes your symptoms worse or brings them on?", ["Worse with physical exertion / movement", "Worse after meals or stress", "Worse at night or in cold weather", "Constant with no clear trigger"]),
                ("associated_systemic", "Are you experiencing any fever, weakness, nausea, or sleep problems?", ["Severe fatigue and body weakness", "Nausea or loss of appetite", "Disturbed sleep and restlessness", "No other systemic complaints"]),
                ("past_medical_history", "Do you have conditions like Diabetes, High BP, Thyroid, or Heart issues?", ["Type 2 Diabetes Mellitus", "High Blood Pressure (Hypertension)", "Thyroid disorder", "No prior chronic illnesses"]),
                ("current_regular_meds", "What regular prescription medicines do you take daily?", ["Taking daily BP or Diabetes tablets", "Taking Thyroid / Cholesterol tablets", "Taking painkillers as needed", "No regular daily tablets"]),
                ("drug_allergies_general", "Do you have any known drug allergies or adverse reactions?", ["No known drug allergies (NKDA)", "Allergic to Penicillin / Antibiotics", "Allergic to NSAID painkillers", "Other allergy"])
            ]
            flow_category = category or "General_OPD"

        # EMERGENCY FAST-TRACK BYPASS:
        # If an acute red flag is active, immediately bypass all routine questions and vitals!
        if red_flag_active:
            return AdaptiveQuestionResponse(
                question="🚨 PRIORITY EMERGENCY ALERT: Critical clinical symptoms detected. Standard OPD questions and vitals entry have been bypassed. Please report to the Casualty Emergency Desk immediately.",
                field="emergency_completion",
                options=["Proceed to Casualty Triage"],
                done=True,
                progressPercent=100,
                source="fallback",
                symptomCategory=flow_category or "Emergency_Casualty"
            )

        # Standard Mandatory OPD Baseline Vitals (Single Common Turn for Height, Weight & Blood Pressure)
        # Prepend to flow so vitals are collected at OPD triage baseline (Turn 1 right after chief complaint)
        vitals_turns = [
            ("vitals_baseline_common", "What are your approximate Height (cm), Weight (kg), and Blood Pressure (BP)? (Standard Baseline Vitals for OPD Care)", [
                "Normal: Weight ~65 kg, Height ~168 cm, BP ~120/80 mmHg",
                "High BP (> 140/90), Weight ~75 kg, Height ~172 cm",
                "Diabetes / High BP, Weight ~80 kg, Height ~165 cm",
                "Weight ~55 kg, Height ~158 cm, Normal BP",
                "Prefer not to disclose / Skip this data"
            ])
        ]
        flow = vitals_turns + flow

        # Find first unasked question in the specialized flow
        unasked = [item for item in flow if item[0] not in answered_fields]
        if unasked:
            f_key, q_text, opts = unasked[0]
            return AdaptiveQuestionResponse(
                question=q_text,
                field=f_key,
                options=opts,
                done=False,
                progressPercent=min(15 + (turn_count * 10), 95),
                source="fallback",
                symptomCategory=flow_category
            )
        elif turn_count < len(flow):
            f_key, q_text, opts = flow[turn_count]
            return AdaptiveQuestionResponse(
                question=q_text,
                field=f_key,
                options=opts,
                done=False,
                progressPercent=min(15 + (turn_count * 10), 95),
                source="fallback",
                symptomCategory=flow_category
            )

        return AdaptiveQuestionResponse(
            question="Thank you for providing your detailed symptoms and baseline health data. Your clinical summary is ready. Please proceed to the Document Scan step.",
            field="completion",
            options=["Proceed to Document Scan"],
            done=True,
            progressPercent=100,
            source="fallback",
            symptomCategory=flow_category
        )

    @classmethod
    async def _call_llm_provider(cls, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Calls active LLM provider (Gemini or Groq) if configured."""
        provider = settings.LLM_PROVIDER
        
        if provider == "gemini" and settings.GEMINI_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                print(f"[Gemini Call Failed]: {e}")

        if (provider == "groq" or (not settings.GEMINI_API_KEY and settings.GROQ_API_KEY)) and settings.GROQ_API_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": settings.GROQ_MODEL,
                    "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[Groq Call Failed]: {e}")

        return None

    @classmethod
    def _extract_json(cls, text: str) -> str:
        """Extract clean JSON substring from model response."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        return text

    @classmethod
    def structure_history_summary(
        cls,
        chief_complaint: str,
        conversation_turns: List[QAPair],
        ayush_mode: bool = False,
        homeopathy_mode: bool = False,
        medical_system: str = "allopathy"
    ) -> Dict[str, Any]:
        """
        Structures collected conversation Q&A pairs into a rich, nurse-grade clinical intake report.
        Generates narrative nurse summary, pertinent positives, pertinent negatives, triage acuity, 
        and recommended clinical workup for the attending physician.
        """
        category = cls.identify_symptom_category(chief_complaint)
        hpi = HistoryOfPresentIllness(symptomCategory=category)
        past_history = []
        drug_history = DrugAllergyHistory()
        personal_history = PersonalHistory()
        vitals = PatientVitals()
        ros_items = []
        ayush_details = {}
        homeopathic_details = {}
        pertinent_positives = []
        pertinent_negatives = []
        red_flags_checked = []

        # Parse every turn
        for turn in conversation_turns:
            ans = turn.patientAnswer
            f = turn.field.lower()
            ans_lower = ans.lower()

            # Detect negative / denied responses
            is_negative = any(w in ans_lower for w in ["no ", "none", "without", "normal", "denies", "no known", "no prior"])

            if any(k in f for k in ["onset", "duration", "chronology"]):
                hpi.onset = ans
                pertinent_positives.append(f"Onset: {ans}")
            elif any(k in f for k in ["character", "severity", "type", "nature"]):
                hpi.character = ans
                pertinent_positives.append(f"Nature: {ans}")
            elif any(k in f for k in ["site", "location", "radiation"]):
                if "radiation" in ans_lower or "spread" in ans_lower or "arm" in ans_lower or "jaw" in ans_lower:
                    hpi.radiation = ans
                    pertinent_positives.append(f"Radiation: {ans}")
                else:
                    hpi.site = ans
                    pertinent_positives.append(f"Site: {ans}")
            elif any(k in f for k in ["triggers", "relief", "meals", "exertion"]):
                hpi.aggravating = ans
                pertinent_positives.append(f"Triggers/Relief: {ans}")
            elif any(k in f for k in ["associated", "autonomic", "nausea", "wheeze", "signs", "focal"]):
                if is_negative:
                    pertinent_negatives.append(f"Denies {ans.replace('No ', '').replace('no ', '')}")
                else:
                    hpi.associatedSymptoms.append(ans)
                    pertinent_positives.append(f"Associated: {ans}")
            elif any(k in f for k in ["red_flags", "bleeding", "rash", "jaundice"]):
                red_flags_checked.append(turn.questionText)
                if is_negative:
                    pertinent_negatives.append(f"Ruled out acute signs ({ans})")
                else:
                    pertinent_positives.append(f"Flagged sign: {ans}")
            elif any(k in f for k in ["past", "risk", "comorbidities", "trauma"]):
                if not is_negative:
                    past_history.append(ans)
                    pertinent_positives.append(f"Comorbidity: {ans}")
                else:
                    pertinent_negatives.append("No prior chronic hospitalizations")
            elif any(k in f for k in ["meds", "medications", "tablets", "compliance"]):
                if not is_negative:
                    drug_history.currentMedications.append(ans)
                    pertinent_positives.append(f"Current Rx: {ans}")
            elif any(k in f for k in ["allerg", "allergy", "reactions"]):
                # Order matters: uncertainty is checked first, because phrases like
                # "no idea" would otherwise be read as an allergy denial.
                if UNCERTAIN_ALLERGY_RE.search(ans):
                    drug_history.allergies = ALLERGY_UNKNOWN_TEXT
                    pertinent_positives.append(f"Allergy status unconfirmed: {ans}")
                elif DENIED_ALLERGY_RE.search(ans):
                    drug_history.allergies = "No known drug allergies (NKDA)"
                    pertinent_negatives.append("No known drug allergies (NKDA)")
                else:
                    drug_history.allergies = ans
                    pertinent_positives.append(f"Drug Allergy: {ans}")
            elif "prakriti" in f:
                ayush_details["prakritiDeha"] = ans
                ayush_details["prakriti"] = ans
                pertinent_positives.append(f"Prakriti: {ans}")
            elif "agni" in f:
                ayush_details["agniPariksha"] = ans
                ayush_details["agni"] = ans
                pertinent_positives.append(f"Jatharagni: {ans}")
            elif "kostha" in f:
                ayush_details["kosthaMala"] = ans
                ayush_details["kostha"] = ans
                pertinent_positives.append(f"Kostha: {ans}")
            elif "ama" in f or "srotorodha" in f:
                ayush_details["amaLakshana"] = ans
                ayush_details["ama"] = ans
                if "no ama" in ans_lower or "nirama" in ans_lower:
                    pertinent_negatives.append(f"Ama Status: Nirama (No metabolic toxicity)")
                else:
                    pertinent_positives.append(f"Ama Status: {ans}")
            elif "dosha" in f:
                ayush_details["doshaLakshana"] = ans
                ayush_details["dosha"] = ans
                pertinent_positives.append(f"Doshic Manifestation: {ans}")
            elif "ahara" in f or "vihara" in f or "hetu" in f:
                ayush_details["aharaViharaHetu"] = ans
                pertinent_positives.append(f"Ahara-Vihara: {ans}")
            elif "nidra" in f or "manasika" in f:
                ayush_details["nidraManasika"] = ans
                ayush_details["nidra"] = ans
                pertinent_positives.append(f"Nidra/Manasika: {ans}")
            elif "thermal" in f:
                homeopathic_details["thermalState"] = ans
                pertinent_positives.append(f"Thermal State: {ans}")
            elif "thirst" in f:
                homeopathic_details["thirst"] = ans
                pertinent_positives.append(f"Thirst Pattern: {ans}")
            elif "modalit" in f:
                homeopathic_details["modalitiesAggravation"] = ans
                homeopathic_details["modalities"] = ans
                pertinent_positives.append(f"Homeopathic Modalities: {ans}")
            elif "mind" in f or "emotional" in f:
                homeopathic_details["mindGenerals"] = ans
                pertinent_positives.append(f"Mind Generals: {ans}")
            elif "cravings" in f or "aversions" in f or "food" in f:
                homeopathic_details["foodCravingsAversions"] = ans
                homeopathic_details["physicalGenerals"] = ans
                pertinent_positives.append(f"Food Cravings/Aversions: {ans}")
            elif "side_affinity" in f or "perspiration" in f:
                homeopathic_details["sideAffinity"] = ans
                homeopathic_details["perspiration"] = ans
                pertinent_positives.append(f"Physical Generals & Side Affinity: {ans}")
            elif "vitals" in f or "weight" in f or "height" in f or "blood_pressure" in f or "bp" in f:
                if any(w in ans_lower for w in ["prefer not", "skip", "decline", "withheld"]):
                    vitals.disclosureStatus = "declined"
                    vitals.nonDisclosureReason = ans
                    pertinent_negatives.append(f"Vitals: Patient chose not to disclose baseline vitals ({ans})")
                else:
                    vitals.weightKg = ans
                    vitals.heightCm = ans
                    vitals.bloodPressure = ans
                    vitals.disclosureStatus = "disclosed"
                    pertinent_positives.append(f"Baseline OPD Vitals: {ans}")
            else:
                ros_items.append(f"{turn.questionText}: {ans}")

        allopathic_details = {
            "anatomicalSite": hpi.site if hpi.site else f"{category.replace('_', ' ')} Primary Region",
            "socratesChronology": hpi.onset if hpi.onset else "Acute / Subacute presentation captured during OPD intake",
            "painCharacterSeverity": hpi.character if hpi.character else "Symptom intensity and pattern documented",
            "radiationDermatome": hpi.radiation if hpi.radiation else "Localized presentation (No distant radiation reported)",
            "aggravatingRelieving": hpi.aggravating if hpi.aggravating else "Related to daily exertion and diurnal routine",
            "autonomicAssociated": ", ".join(hpi.associatedSymptoms) if hpi.associatedSymptoms else "No acute autonomic symptoms reported",
            "comorbidityRiskStratification": ", ".join(past_history) if past_history != ["No prior chronic hospital admissions reported"] else "Low cardiovascular / metabolic risk profile",
            "activePharmacotherapyReconciliation": ", ".join(drug_history.currentMedications) if drug_history.currentMedications else "No active daily prescription medications",
            "allergyAdverseAlert": drug_history.allergies if drug_history.allergies else "No known drug allergies (NKDA)"
        }
        hpi.allopathicDetails = allopathic_details

        # Populate Ayurvedic classical intake details
        if ayush_mode or medical_system == "ayurveda" or ayush_details:
            if not ayush_details:
                ayush_details = {
                    "doshaLakshana": "Vata-Pitta / Kapha constitutional manifestation recorded",
                    "agniPariksha": "Samagni / Vishamagni presentation",
                    "kosthaMala": "Madhyama Kostha",
                    "amaLakshana": "Nirama (No severe metabolic toxicity)",
                    "prakritiDeha": "Dwandvaja (Pitta-Kapha / Vata-Pitta)",
                    "aharaViharaHetu": "Ahara-Vihara related to diurnal routine and intake",
                    "nidraManasika": "Prakrita Nidra / Rajasika Manasika state",
                    "ayurvedicMedicationsPathya": "Pathya Ahara & Ahara Niyama advised"
                }
            hpi.ayushDetails = ayush_details
            hpi.ayurvedicDetails = ayush_details

        # Populate Homeopathic classical intake details
        if homeopathy_mode or medical_system == "homeopathy" or homeopathic_details:
            if not homeopathic_details:
                homeopathic_details = {
                    "thermalState": "Ambi-thermal / Chilly vs Hot disposition documented",
                    "thirst": "Normal thirst for fluids / Thirstless presentation",
                    "modalitiesAggravation": "Aggravation with exertion / change of weather",
                    "mindGenerals": "Mild anxiety, disposition documented",
                    "foodCravingsAversions": "General dietary preferences noted",
                    "sideAffinity": "Bilateral / Symmetric presentation",
                    "miasmaticTendency": "Psora-Sycosis predominance"
                }
            hpi.homeopathicDetails = homeopathic_details
        hpi.clinicalRedFlagsChecked = red_flags_checked

        if not hpi.onset:
            hpi.onset = "Acute presentation captured during triage intake"
        if not hpi.character:
            hpi.character = "Symptom intensity and pattern documented via structured responses"
        if not past_history:
            past_history = ["No prior chronic hospital admissions reported"]

        # Synthesize Nurse-Grade Narrative Summary Paragraph
        positives_text = ", ".join(pertinent_positives[:4]) if pertinent_positives else "symptom presentation recorded"
        negatives_text = "; ".join(pertinent_negatives[:3]) if pertinent_negatives else "no acute alarm signs reported"
        meds_text = ", ".join(drug_history.currentMedications) if drug_history.currentMedications else "no regular daily prescription tablets"
        past_text = ", ".join(past_history) if past_history != ["No prior chronic hospital admissions reported"] else "no major chronic illnesses"

        if ayush_mode or medical_system == "ayurveda" or "ayush" in category.lower():
            dosha_val = ayush_details.get("doshaLakshana") or "Doshic imbalance present"
            agni_val = ayush_details.get("agniPariksha") or "Agni assessment recorded"
            kostha_val = ayush_details.get("kosthaMala") or "Kostha evaluated"
            ama_val = ayush_details.get("amaLakshana") or "Ama status assessed"
            prakriti_val = ayush_details.get("prakritiDeha") or ayush_details.get("prakriti") or "Mixed Prakriti"
            hetu_val = ayush_details.get("aharaViharaHetu") or "Ahara-Vihara documented"
            
            nurse_summary_narrative = (
                f"Patient presents with {chief_complaint} in AYUSH Ayurvedic OPD. "
                f"Roga-Rogi & Dashavidha Pariksha reveals {dosha_val} with {agni_val} and {kostha_val}. "
                f"Metabolic status: {ama_val}. "
                f"Etiological inquiry (Ahara-Vihara Hetu): {hetu_val}. "
                f"Deha-Prakriti: {prakriti_val}. "
                f"Current Medications: {meds_text}. "
                f"Prepared for Ayurvedic Medical Officer (Vaidya / BAMS) review."
            )
            recommendations = [
                "Perform Nadi Pariksha & Jihva / Ashtavidha Pariksha clinical verification",
                "Prescribe Deepana-Pachana Aushadhi for Ama pachana and Agni deepana",
                "Advise Pathya-Apathya Ahara & Dinacharya (warm water, avoid Viruddha Ahara)",
                "Evaluate for Sodhana Chikitsa (Panchakarma / Basti / Virechana) if chronic"
            ]
        elif homeopathy_mode or medical_system == "homeopathy":
            thermal_val = homeopathic_details.get("thermalState") or "Thermal tolerance documented"
            thirst_val = homeopathic_details.get("thirst") or "Thirst pattern assessed"
            mind_val = homeopathic_details.get("mindGenerals") or "Mind & emotional disposition recorded"
            modalities_val = homeopathic_details.get("modalitiesAggravation") or homeopathic_details.get("modalities") or "Modalities (< & >) documented"
            cravings_val = homeopathic_details.get("foodCravingsAversions") or homeopathic_details.get("physicalGenerals") or "Food cravings evaluated"
            side_val = homeopathic_details.get("sideAffinity") or "Side affinity recorded"
            
            nurse_summary_narrative = (
                f"Patient presents with {chief_complaint} in AYUSH Homeopathic OPD. "
                f"Classical Totality of Symptoms intake demonstrates {thermal_val} with {thirst_val}. "
                f"Mind & Emotional Generals: {mind_val}. "
                f"Key Modalities & Triggers (< / >): {modalities_val}. "
                f"Physical Generals & Food Cravings: {cravings_val}. "
                f"Lateral & Perspiration Affinity: {side_val}. "
                f"Current Medications: {meds_text}. "
                f"Synthesized for Homeopathic Medical Officer (BHMS / MD Homeopathy) review."
            )
            recommendations = [
                "Perform Kent / Boenninghausen repertorization on Totality of Characteristic Generals & Modalities",
                "Select Single Simillimum Constitutional Remedy in optimal potency (30C / 200C / 1M / LM)",
                "Check for Miasmatic Block / Anti-miasmatic intercurrent remedy (Psoric/Sycotic/Syphilitic) if indicated",
                "Advise standard homeopathic dietary rules (Avoid strong raw camphor, eucalyptus, raw onion with doses)",
                "Schedule follow-up review in 2-4 weeks to assess direction of cure (Hering's Law)"
            ]
        else:
            nurse_summary_narrative = (
                f"Patient presents with {chief_complaint} in Modern Allopathic OPD ({category.replace('_', ' ')}). "
                f"SOCRATES exploration reveals {hpi.character} localized to {hpi.site or 'primary anatomical region'} with onset {hpi.onset}. "
                f"Radiation: {hpi.radiation or 'None'}. Triggers/Relief: {hpi.aggravating or 'None specified'}. "
                f"Pertinent positives: {positives_text}. "
                f"Pertinent negatives & ruled-out alarm signs: {negatives_text}. "
                f"Comorbidity risk profile: {past_text}. "
                f"Active pharmacotherapy reconciliation: {meds_text}. "
                f"Allergy status: {drug_history.allergies}. "
                f"Synthesized for Attending Medical Officer / Consultant Physician review."
            )
            recommendations = []
            if category == "Cardiovascular":
                recommendations = ["Check 12-lead ECG stat", "Assess vitals & bilateral BP", "Review Lipid & Blood Glucose panel"]
            elif category == "Gastrointestinal":
                recommendations = ["Abdominal palpation for epigastric / RUQ tenderness", "Evaluate for H. pylori / Gastritis", "Advise dietary modification"]
            elif category == "Respiratory":
                recommendations = ["Check resting SpO2 & chest auscultation", "Assess for wheezing / bronchodilator response", "Consider Chest X-Ray if cough > 3 weeks"]
            elif category == "Musculoskeletal":
                recommendations = ["Inspect joint range of motion & crepitus", "Review standing knee / spinal X-Rays", "Check Serum Uric Acid if inflammatory"]
            elif category == "Infectious_Fever":
                recommendations = ["Record temperature & vitals", "Order Complete Blood Count (CBC) with Platelets", "Check Rapid Dengue / Malarial smear if indicated"]
            elif category == "Endocrine_Metabolic":
                recommendations = ["Check Fasting Blood Sugar & HbA1c", "Examine feet for sensory neuropathy / pulses", "Review current antidiabetic dosages"]
        return {
            "chiefComplaint": chief_complaint,
            "historyOfPresentIllness": hpi,
            "pastMedicalHistory": past_history,
            "drugAllergyHistory": drug_history,
            "familyHistory": ["Non-contributory for early familial illness unless noted"],
            "personalHistory": personal_history,
            "vitals": vitals,
            "reviewOfSystems": "; ".join(ros_items) if ros_items else f"{category} systems reviewed. Vital clinical parameters recorded.",
            "nurseSummary": nurse_summary_narrative,
            "pertinentPositives": pertinent_positives,
            "pertinentNegatives": pertinent_negatives,
            "triageAcuity": "Routine",
            "nurseRecommendations": recommendations
        }

    @classmethod
    async def generate_clinical_decision_support(
        cls,
        session_data: Dict[str, Any]
    ) -> CDSSResponse:
        """
        Generates structured evidence-based Clinical Decision Support (CDSS):
        Differential Diagnoses, Suggested Treatment/Drug Regimens, Key Points to Notice,
        and Recommended Investigations for attending physician review.
        """
        chief = session_data.get("chiefComplaint", "General Consultation")
        hpi = session_data.get("historyOfPresentIllness", {})
        if isinstance(hpi, dict):
            hpi_text = f"Onset: {hpi.get('onset', '')}, Character: {hpi.get('character', '')}, Radiation: {hpi.get('radiation', '')}, Associated: {hpi.get('associatedSymptoms', '')}, Aggravating: {hpi.get('aggravating', '')}"
        else:
            hpi_text = str(hpi)

        past_hx = session_data.get("pastMedicalHistory", [])
        if isinstance(past_hx, list):
            past_text = ", ".join(past_hx)
        else:
            past_text = str(past_hx)

        drug_hx = session_data.get("drugAllergyHistory", {})
        if isinstance(drug_hx, dict):
            allergies = drug_hx.get("allergies", "No known drug allergies")
            current_meds = drug_hx.get("currentMedications", [])
            if isinstance(current_meds, list):
                meds_text = ", ".join(current_meds)
            else:
                meds_text = str(current_meds)
        else:
            allergies = "No known drug allergies"
            meds_text = "None"

        red_flag = session_data.get("redFlag", {})
        red_flag_text = red_flag.get("reason", "None") if isinstance(red_flag, dict) and red_flag.get("triggered") else "None"
        category = cls.identify_symptom_category(chief)
        is_ayush = bool(session_data.get("ayushMode", False)) or session_data.get("medicalSystem") == "ayurveda"
        is_homeopathy = bool(session_data.get("homeopathyMode", False)) or session_data.get("medicalSystem") == "homeopathy"
        

        user_prompt = f"""
PATIENT PRE-CONSULTATION CLINICAL PROFILE:
- Age / Gender: {session_data.get('age', 45)} Yrs / {session_data.get('gender', 'Male')}
- Chief Complaint: {chief}
- Category: {category} (AYUSH Mode: {is_ayush})
- History of Present Illness (SOCRATES): {hpi_text}
- Comorbidities & Past Medical History: {past_text or 'None reported'}
- Current Medications: {meds_text or 'None'}
- Known Drug Allergies: {allergies}
- Emergency Red Flag Status: {red_flag_text}

Generate comprehensive evidence-based Differential Diagnoses, practical Indian OPD Drug Regimens, Key Points to Notice (Physical exam signs to check), and Recommended Investigations. Output STRICT JSON ONLY.
"""

        # Try Live LLM provider if configured
        llm_response = await cls._call_llm_provider(cls.SYSTEM_PROMPT_CDSS, user_prompt)
        if llm_response:
            try:
                cleaned = cls._extract_json(llm_response)
                data = json.loads(cleaned)
                
                diffs = []
                for d in data.get("differentialDiagnoses", []):
                    diffs.append(DifferentialDiagnosis(
                        condition=d.get("condition", "Clinical Syndrome"),
                        icd10=d.get("icd10", None),
                        probability=d.get("probability", "Moderate"),
                        rationale=d.get("rationale", "")
                    ))

                treatments = []
                for t in data.get("suggestedTreatments", []):
                    treatments.append(SuggestedDrug(
                        name=t.get("name", "Standard Regimen"),
                        dosage=t.get("dosage", "As prescribed"),
                        frequency=t.get("frequency", "Once daily"),
                        duration=t.get("duration", "5-7 days"),
                        rationale=t.get("rationale", "Evidence-based standard of care"),
                        contraindicationWarning=t.get("contraindicationWarning", None)
                    ))

                if diffs and treatments:
                    return CDSSResponse(
                        differentialDiagnoses=diffs,
                        suggestedTreatments=treatments,
                        keyPointsToNotice=data.get("keyPointsToNotice", ["Verify vital signs & perform targeted physical examination"]),
                        recommendedInvestigations=data.get("recommendedInvestigations", ["Routine baseline evaluation as indicated"]),
                        clinicalRationale=data.get("clinicalRationale", "AI clinical decision support synthesized for attending physician review."),
                        source=settings.LLM_PROVIDER if getattr(settings, 'LLM_PROVIDER', None) in ["gemini", "groq", "openrouter"] else "guideline_rules",
                        disclaimer="AI Clinical Decision Support for doctor guidance only. Prescriptions and diagnoses are subject to attending physician's clinical discretion."
                    )
            except Exception as parse_err:
                print(f"[LLMService] CDSS JSON parse error: {parse_err}")

        # Fallback Guideline Engine
        return cls._guideline_cdss_fallback(category, is_ayush, is_homeopathy, allergies, past_text, chief, hpi_text)

    @classmethod
    def _guideline_cdss_fallback(
        cls,
        category: str,
        is_ayush: bool,
        is_homeopathy: bool,
        allergies: str,
        past_text: str,
        chief: str,
        hpi_text: str
    ) -> CDSSResponse:
        """
        High-fidelity, guideline-aligned clinical decision support fallback.
        Provides realistic differential diagnoses, Indian OPD drug regimens, critical examination points,
        and recommended diagnostic workup across specialties.
        """
        has_penicillin_allergy = "penicillin" in allergies.lower() or "amox" in allergies.lower()

        if is_homeopathy:
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Constitutional / Acute Homeopathic Case Totality", icd10="U70.0", probability="High", rationale="Totality of thermal reaction, thirst characteristics, mental disposition, and symptom modalities indicate high similimum correspondence."),
                    DifferentialDiagnosis(condition="Psoric / Sycotic Chronic Diathesis", icd10="U70.1", probability="Moderate", rationale="Underlying susceptibility with recurrent functional disturbances exacerbated by environmental modalities."),
                    DifferentialDiagnosis(condition="Secondary Functional Pathological Disturbance", icd10="R69", probability="Consider / Low", rationale="Somatic functional expression corresponding to selected keynotes.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Arsenicum Album", dosage="4 globules / 2 drops in water", frequency="Twice daily before food", duration="5 days", potency="30C", repetition="TDS in acute phase", rationale="Indicated for intense restlessness, burning sensation relieved by warmth, and frequent thirst for small sips"),
                    SuggestedDrug(name="Nux Vomica", dosage="4 globules", frequency="Once daily at bedtime", duration="7 days", potency="30C", repetition="Night dose", rationale="Keynote remedy for sedentary stress, digestive irritability, and oversensitivity from rich spicy foods"),
                    SuggestedDrug(name="Bryonia Alba", dosage="4 globules", frequency="Twice daily after food", duration="5 days", potency="200C", repetition="Twice daily", rationale="Indicated when symptoms are sharply aggravated by the slightest motion and relieved by absolute rest and firm pressure")
                ],
                keyPointsToNotice=[
                    "Assess mental disposition: Restless anxiety (Arsenicum) vs irritable fastidious (Nux Vomica) vs mild/weepy (Pulsatilla)",
                    "Verify exact modalities: Time of aggravation (< morning, < night 2-3 AM), temperature (< cold air, < stuffy room)",
                    "Check food desires/aversions: Craving sweets/warm food vs fatty food intolerance"
                ],
                recommendedInvestigations=[
                    "Comprehensive Homeopathic Repertorization & Miasmatic Assessment",
                    "Routine Baseline Vitals & OPD Clinical Examination"
                ],
                clinicalRationale="Patient exhibits characteristic Homeopathic keynote totality; individual Similimum selected based on modalities, thermals, and mental generals for gentle, rapid restoration of health.",
                source="guideline_rules"
            )

        if is_ayush:
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Vata-Kapha Prakopa / Sandhigata Vata", icd10="U69.0", probability="High", rationale="Predominance of pain, stiffness, and digestive irregularity matching Vata-Kapha imbalance."),
                    DifferentialDiagnosis(condition="Amlapitta with Agnimandya", icd10="K21.0", probability="Moderate", rationale="Digestive sluggishness, post-meal heaviness, and mild burning symptoms."),
                    DifferentialDiagnosis(condition="Pranavaha Srotas Dusti", icd10="J45.9", probability="Consider / Low", rationale="Upper respiratory irritability triggered by cold or seasonal change.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Yogaraj Guggulu", dosage="2 tablets", frequency="Twice daily after food with warm water", duration="30 days", rationale="Classical Ayurvedic formulation for joint mobility and Vata pacification"),
                    SuggestedDrug(name="Avipattikar Churna", dosage="3 to 5 grams", frequency="Twice daily before meals with honey or warm water", duration="14 days", rationale="Pitta-pacifying digestive stimulant for acidity and Agni balancing"),
                    SuggestedDrug(name="Ashwagandha Ghanvati", dosage="1 tablet", frequency="Once daily at bedtime with warm milk", duration="30 days", rationale="Rasayana adaptogen for restorative sleep and muscle strength")
                ],
                keyPointsToNotice=[
                    "Assess Ashta Sthana Pariksha (Nadi, Jihva, Mala, Mutra, Shabda, Sparsha, Druk, Aakruti)",
                    "Inquire into dietary habits (Ahara) and mental stress levels (Manasika status)",
                    "Advise Pathya-Apathya regimen (avoiding heavy, cold, or excessively sour/spicy meals)"
                ],
                recommendedInvestigations=[
                    "Nadi Pariksha Assessment",
                    "Routine Complete Blood Count & Fasting Metabolic Screen (if integrative monitoring needed)"
                ],
                clinicalRationale="Ayurvedic clinical profile suggestive of dual Dosha aggravation; targeted Sodhana and Samana Dravyas recommended under physician discretion.",
                source="guideline_rules"
            )

        if category == "Cardiovascular":
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Angina Pectoris / Acute Coronary Syndrome (ACS)", icd10="I20.9", probability="High", rationale="Exertional chest discomfort with possible autonomic features warrants immediate rule-out of myocardial ischemia."),
                    DifferentialDiagnosis(condition="Gastroesophageal Reflux Disease (GERD) with Non-Cardiac Chest Pain", icd10="K21.9", probability="Moderate", rationale="Retrosternal burning sensation frequently mimics cardiac angina."),
                    DifferentialDiagnosis(condition="Costochondritis / Musculoskeletal Chest Wall Strain", icd10="M94.0", probability="Consider / Low", rationale="Localized chest wall tenderness worsened by deep inspiration or palpation.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Tab Aspirin (Ecosprin) 75mg", dosage="1 tablet", frequency="Once daily post lunch", duration="Ongoing / 30 days", rationale="Antiplatelet therapy for cardiovascular protection (Ensure no active bleeding/ulcer)"),
                    SuggestedDrug(name="Tab Atorvastatin 20mg", dosage="1 tablet", frequency="Once daily at bedtime", duration="Ongoing / 30 days", rationale="HMG-CoA reductase inhibitor for lipid stabilization and plaque protection"),
                    SuggestedDrug(name="Tab Pantoprazole 40mg", dosage="1 tablet", frequency="Once daily before breakfast", duration="14 days", rationale="Proton pump inhibitor for gastroprotection alongside antiplatelet therapy"),
                    SuggestedDrug(name="S/L Sorbitrate (Isosorbide Dinitrate) 5mg", dosage="1 tablet", frequency="SOS sublingually for acute chest pain", duration="PRN", rationale="Rapid coronary vasodilation (Avoid if BP < 90/60 mmHg)")
                ],
                keyPointsToNotice=[
                    "Check 12-lead ECG immediately and compare with any baseline tracings",
                    "Auscultate for cardiac murmurs, S3/S4 gallop, and bilateral basal lung crepitations",
                    "Measure bilateral brachial blood pressure and assess radial pulse symmetry",
                    "⚠️ RED FLAG: Immediate emergency casualty transfer if crushing pain > 20 mins, diaphoresis, or ST elevation."
                ],
                recommendedInvestigations=[
                    "12-Lead Electrocardiogram (ECG) Stat",
                    "High-Sensitivity Serum Troponin-I / T",
                    "Fasting Lipid Profile, HbA1c, and Serum Creatinine",
                    "2D Echocardiography with Doppler"
                ],
                clinicalRationale="Patient exhibits cardiovascular symptoms requiring urgent ECG and cardiac biomarker evaluation while initiating cardioprotective and gastroprotective therapy.",
                source="guideline_rules"
            )

        elif category == "Gastrointestinal":
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Gastroesophageal Reflux Disease (GERD) / Acid Peptic Disease", icd10="K21.0", probability="High", rationale="Epigastric burning/discomfort related to meals, acid regurgitation, or fasting intervals."),
                    DifferentialDiagnosis(condition="Acute Gastritis / Peptic Ulcer Disease", icd10="K29.7", probability="Moderate", rationale="Localized epigastric tenderness with variable meal-related triggers."),
                    DifferentialDiagnosis(condition="Biliary Colic / Cholelithiasis", icd10="K80.2", probability="Consider / Low", rationale="Right upper quadrant discomfort exacerbated by fatty/oily foods.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Cap Pantoprazole 40mg + Domperidone 30mg SR (Pantocid-DSR)", dosage="1 capsule", frequency="Once daily before breakfast", duration="14 days", rationale="Proton pump inhibitor + prokinetic for rapid acid suppression and upper GI motility"),
                    SuggestedDrug(name="Syp Sucralfate 1000mg / 5ml (Sucrafil)", dosage="10 ml", frequency="Thrice daily 1 hour before meals", duration="7 days", rationale="Mucosal cytoprotective agent for ulcer and mucosal coating"),
                    SuggestedDrug(name="Tab Drotaverine 40mg (Drotin)", dosage="1 tablet", frequency="SOS for severe abdominal spasmodic cramps", duration="PRN (Max 3/day)", rationale="Smooth muscle antispasmodic for visceral cramp relief")
                ],
                keyPointsToNotice=[
                    "Palpate abdomen for epigastric tenderness, Murphy's sign, guarding, or rigidity",
                    "Screen for alarm symptoms: Melena (black tarry stools), hematemesis, dysphagia, or unexplained weight loss",
                    "Advise lifestyle measures: Avoid spicy/fried foods, caffeine, and maintain 2-hour gap between dinner and sleeping"
                ],
                recommendedInvestigations=[
                    "Ultrasound Whole Abdomen (to assess gallbladder, liver, and biliary tree)",
                    "Upper GI Endoscopy (if symptoms persist > 2 weeks or alarm features exist)",
                    "Complete Blood Count (CBC) and Serum Amylase/Lipase (if severe upper quadrant pain)",
                    "Stool for Occult Blood / H. pylori stool antigen"
                ],
                clinicalRationale="Features consistent with acid peptic disease / reflux gastritis; prompt high-dose PPI therapy combined with mucosal protection and dietary counseling advised.",
                source="guideline_rules"
            )

        elif category == "Respiratory":
            abx = SuggestedDrug(
                name="Tab Azithromycin 500mg (Azee)",
                dosage="1 tablet",
                frequency="Once daily after food",
                duration="3 days",
                rationale="Broad-spectrum macrolide covering atypical and common respiratory pathogens",
                contraindicationWarning="⚠️ Patient has documented Macrolide allergy" if "azithro" in allergies.lower() else None
            )
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Acute Bronchitis / Viral Upper Respiratory Infection", icd10="J20.9", probability="High", rationale="Cough with variable sputum production and throat/chest discomfort."),
                    DifferentialDiagnosis(condition="Bronchial Asthma / Reactive Airway Disease Exacerbation", icd10="J45.9", probability="Moderate", rationale="Nocturnal cough bouts, wheezing, or chest tightness triggered by dust/cold."),
                    DifferentialDiagnosis(condition="Community-Acquired Pneumonia (CAP)", icd10="J18.9", probability="Consider / Low", rationale="Consider if persistent high fever, purulent sputum, or localized crackles.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Inhaler Budesonide 200mcg + Formoterol 6mcg (Budecort-F)", dosage="2 puffs", frequency="Twice daily with spacer, rinse mouth after use", duration="14 days", rationale="Inhaled corticosteroid + LABA for airway anti-inflammatory and bronchodilator control"),
                    SuggestedDrug(name="Tab Levocetirizine 5mg + Montelukast 10mg (Montair-LC)", dosage="1 tablet", frequency="Once daily at bedtime", duration="10 days", rationale="Antihistamine and leukotriene receptor antagonist for nocturnal cough and allergic airway control"),
                    SuggestedDrug(name="Syp Dextromethorphan + Chlorpheniramine + Phenylephrine (Ascoril-D)", dosage="10 ml", frequency="Thrice daily after food", duration="5 days", rationale="Antitussive for dry irritating cough"),
                    abx
                ],
                keyPointsToNotice=[
                    "Check resting pulse oximetry (SpO2) on room air and respiratory rate",
                    "Auscultate bilateral lung fields for wheezing, rhonchi, or crepitations",
                    "Rule out hemoptysis, pleuritic chest pain, and severe tachypnea"
                ],
                recommendedInvestigations=[
                    "Chest X-Ray PA View",
                    "Complete Blood Count (CBC) with Absolute Eosinophil Count (AEC)",
                    "Peak Expiratory Flow Rate (PEFR) / Spirometry",
                    "Sputum examination for Gram stain / AFB (if cough > 2 weeks)"
                ],
                clinicalRationale="Clinical presentation indicates acute tracheobronchial inflammation with reactive airway component; combination inhaled anti-inflammatory and oral antihistamine recommended.",
                source="guideline_rules"
            )

        elif category == "Musculoskeletal":
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Primary Osteoarthritis of Knee / Spine", icd10="M17.9", probability="High", rationale="Weight-bearing joint ache, crepitus, and stiffness related to movement and standing."),
                    DifferentialDiagnosis(condition="Lumbar Spondylosis with Radiculopathy", icd10="M47.8", probability="Moderate", rationale="Lower back ache exacerbated by prolonged sitting or bending."),
                    DifferentialDiagnosis(condition="Inflammatory Arthropathy / Gouty Arthritis", icd10="M10.9", probability="Consider / Low", rationale="Acute joint swelling, warmth, or morning stiffness > 30 minutes.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Tab Paracetamol 650mg (Dolo-650)", dosage="1 tablet", frequency="Thrice daily after meals as needed", duration="5-7 days", rationale="First-line simple analgesic for joint ache (Safest for GI/renal profile)"),
                    SuggestedDrug(name="Tab Aceclofenac 100mg + Paracetamol 325mg + Serratiopeptidase 15mg (Zerodol-SP)", dosage="1 tablet", frequency="Twice daily after food with Pantoprazole", duration="5 days", rationale="Potent anti-inflammatory analgesic for acute joint flare (Use with caution if elderly/peptic history)"),
                    SuggestedDrug(name="Tab Calcium Carbonate 500mg + Vitamin D3 250IU (Shelcal-500)", dosage="1 tablet", frequency="Once daily post lunch", duration="30 days", rationale="Bone mineral density and joint structural support"),
                    SuggestedDrug(name="Topical Diclofenac Diethylamine Gel 1.16% (Volini)", dosage="Local application", frequency="Thrice daily gently over affected joint", duration="14 days", rationale="Targeted local anti-inflammatory without systemic side effects")
                ],
                keyPointsToNotice=[
                    "Examine joint for effusion, erythema, joint-line tenderness, and range of motion",
                    "Assess gait, quadriceps muscle bulk, and leg alignment (genu varum/valgum)",
                    "Advise physical therapy: Isometric quadriceps exercises and weight management"
                ],
                recommendedInvestigations=[
                    "Digital X-Ray Bilateral Knees (Standing AP and Lateral views)",
                    "Serum Uric Acid & Serum Calcium",
                    "ESR & C-Reactive Protein (CRP) to rule out inflammatory arthritis",
                    "Serum 25-Hydroxy Vitamin D Level"
                ],
                clinicalRationale="Degenerative musculoskeletal joint syndrome; multimodal therapy incorporating topical anti-inflammatories, paracetamol, and physical exercise advised.",
                source="guideline_rules"
            )

        elif category == "Infectious_Fever":
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition="Acute Febrile Viral Illness / Viral Syndrome", icd10="B34.9", probability="High", rationale="Acute onset fever with constitutional myalgia, headache, and chills."),
                    DifferentialDiagnosis(condition="Dengue Fever / Vector-Borne Infection", icd10="A90", probability="Moderate", rationale="High-grade fever with retro-orbital pain and body ache in endemic setting."),
                    DifferentialDiagnosis(condition="Typhoid / Enteric Fever", icd10="A01.0", probability="Consider / Low", rationale="Step-ladder pyrexia with gastrointestinal disturbance.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Tab Paracetamol 650mg (Calpol/Dolo)", dosage="1 tablet", frequency="Every 6 hours SOS for fever > 100°F (Max 4/day)", duration="5 days", rationale="First-line antipyretic (Strictly avoid NSAIDs/Aspirin due to dengue platelet bleeding risk)"),
                    SuggestedDrug(name="ORS (Oral Rehydration Salts) Solution (Electral)", dosage="1-2 liters", frequency="Sip continuously throughout the day", duration="5 days", rationale="Maintenance of adequate intravascular volume and electrolyte balance"),
                    SuggestedDrug(name="Tab Multivitamin + Zinc (Becozinc)", dosage="1 tablet", frequency="Once daily after lunch", duration="10 days", rationale="Micronutrient and immune support during acute febrile recovery")
                ],
                keyPointsToNotice=[
                    "Inspect skin for petechiae, spontaneous purpura, or maculopapular rash",
                    "Palpate abdomen for hepatosplenomegaly and epigastric tenderness",
                    "⚠️ RED FLAGS: Warn patient to return immediately if persistent vomiting, abdominal pain, mucosal bleeding, or severe lethargy occurs."
                ],
                recommendedInvestigations=[
                    "Complete Blood Count (CBC) with Platelet Count & Hematocrit",
                    "Dengue NS1 Antigen & IgM/IgG Rapid Kit",
                    "Peripheral Blood Smear for Malarial Parasite (MP) / Rapid Antigen Test",
                    "Urine Routine & Microscopy"
                ],
                clinicalRationale="Acute febrile illness requiring close hematological monitoring (platelets/hematocrit) and aggressive oral hydration with paracetamol antipyresis.",
                source="guideline_rules"
            )

        else:
            return CDSSResponse(
                differentialDiagnoses=[
                    DifferentialDiagnosis(condition=f"Clinical Evaluation for {chief}", icd10="R69", probability="High", rationale="Symptom complex reported during pre-consultation OPD intake."),
                    DifferentialDiagnosis(condition="Metabolic / Systemic Comorbidity Consideration", icd10="Z00.0", probability="Moderate", rationale="Underlying chronic health parameters warrant comprehensive review.")
                ],
                suggestedTreatments=[
                    SuggestedDrug(name="Tab Paracetamol 650mg", dosage="1 tablet", frequency="SOS for pain or fever", duration="5 days", rationale="General symptomatic pain/fever relief"),
                    SuggestedDrug(name="Tab Pantoprazole 40mg", dosage="1 tablet", frequency="Once daily before breakfast", duration="7 days", rationale="Proton pump inhibitor for gastroprotection"),
                    SuggestedDrug(name="Tab Multivitamin / Antioxidants", dosage="1 tablet", frequency="Once daily post lunch", duration="15 days", rationale="General nutritional and restorative support")
                ],
                keyPointsToNotice=[
                    "Conduct detailed systemic examination (CVS, RS, PA, CNS)",
                    "Record baseline vital signs: Pulse, Blood Pressure, Respiratory Rate, SpO2, Temperature",
                    "Correlate with past prescription history and patient comorbidity profile"
                ],
                recommendedInvestigations=[
                    "Complete Blood Count (CBC)",
                    "Fasting Blood Sugar & Serum Creatinine",
                    "Routine Urine Examination"
                ],
                clinicalRationale="General clinical presentation; holistic physical examination and baseline investigations suggested under attending physician direction.",
                source="guideline_rules"
            )

llm_service = LLMService()

