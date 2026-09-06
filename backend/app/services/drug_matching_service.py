"""
Phonetic & Levenshtein Drug Matcher Service for MediKiosk.
Provides fast fuzzy searching and auto-completion across CDSCO Indian pharmaceutical formulary.
"""
from typing import List, Dict, Any

class DrugMatchingService:
    """
    Indian pharmaceutical drug directory and phonetic matcher.
    """

    INDIAN_DRUG_LEXICON = [
        {"brand": "Azulix 2", "generic": "Glimepiride 2mg", "category": "Antidiabetic (Sulfonylurea)"},
        {"brand": "Ondero-D 10", "generic": "Linagliptin 5mg + Dapagliflozin 10mg", "category": "Antidiabetic (DPP-4i + SGLT2i)"},
        {"brand": "Thyronorm 75mcg", "generic": "Levothyroxine Sodium 75mcg", "category": "Thyroid Hormone"},
        {"brand": "Uprise D3 60K", "generic": "Cholecalciferol 60,000 IU", "category": "Vitamin D3 Supplement"},
        {"brand": "Lubrijoint Plus", "generic": "Glucosamine + Chondroitin", "category": "Joint Care / Cartilage"},
        {"brand": "Fenolip 145", "generic": "Fenofibrate 145mg", "category": "Lipid Lowering (Fibrate)"},
        {"brand": "Stanlip 145", "generic": "Fenofibrate 145mg", "category": "Lipid Lowering (Fibrate)"},
        {"brand": "Trinerve Plus", "generic": "Methylcobalamin + Alpha Lipoic Acid", "category": "Neuropathy / B-Complex"},
        {"brand": "Nurokind Plus", "generic": "Mecobalamin + Pyridoxine + Folic Acid", "category": "Neuropathy / B-Complex"},
        {"brand": "Augmentin 625", "generic": "Amoxicillin 500mg + Clavulanic Acid 125mg", "category": "Antibiotic (Beta-Lactam)"},
        {"brand": "Dolo 650", "generic": "Paracetamol 650mg", "category": "Analgesic / Antipyretic"},
        {"brand": "Calpol 500", "generic": "Paracetamol 500mg", "category": "Analgesic / Antipyretic"},
        {"brand": "Pan 40", "generic": "Pantoprazole 40mg", "category": "Proton Pump Inhibitor (Gastro)"},
        {"brand": "Pan-D", "generic": "Pantoprazole 40mg + Domperidone 30mg", "category": "Antacid / Antiemetic"},
        {"brand": "Ascoril-D", "generic": "Dextromethorphan + Phenylephrine + Chlorpheniramine", "category": "Cough Formula"},
        {"brand": "Telma 40", "generic": "Telmisartan 40mg", "category": "Antihypertensive (ARB)"},
        {"brand": "Telmikem AM", "generic": "Telmisartan 40mg + Amlodipine 5mg", "category": "Antihypertensive Combination"},
        {"brand": "Glycomet GP 1", "generic": "Metformin 500mg + Glimepiride 1mg", "category": "Antidiabetic"},
        {"brand": "Glycomet SR 500", "generic": "Metformin 500mg (Sustained Release)", "category": "Antidiabetic (Biguanide)"},
        {"brand": "Atorva 20", "generic": "Atorvastatin 20mg", "category": "Lipid Lowering (Statin)"},
        {"brand": "Rosuvas 10", "generic": "Rosuvastatin 10mg", "category": "Lipid Lowering (Statin)"},
        {"brand": "Cremalax", "generic": "Bisacodyl 10mg", "category": "Laxative / Bowel Prep"},
        {"brand": "Azithral 500", "generic": "Azithromycin 500mg", "category": "Antibiotic (Macrolide)"},
        {"brand": "Cefix 200", "generic": "Cefixime 200mg", "category": "Antibiotic (Cephalosporin)"},
        {"brand": "Montair LC", "generic": "Montelukast 10mg + Levocetirizine 5mg", "category": "Antiallergic / Respiratory"},
        {"brand": "Ecosprin 75", "generic": "Aspirin 75mg", "category": "Antiplatelet / Cardiovascular"},
        {"brand": "Clopilet 75", "generic": "Clopidogrel 75mg", "category": "Antiplatelet / Cardiovascular"},
        {"brand": "Yogaraj Guggulu", "generic": "Classical Ayurvedic Formulation", "category": "Ayush Vata / Joint Care"},
        {"brand": "Ashwagandharishta", "generic": "Withania Somnifera Fermented Extract", "category": "Ayush Rasayana / Adaptogen"}
    ]

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return DrugMatchingService._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    @classmethod
    def search_drugs(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fuzzy searches against Indian drug database.
        """
        if not query or len(query.strip()) < 2:
            return cls.INDIAN_DRUG_LEXICON[:limit]

        q = query.lower().strip()
        scored = []
        for item in cls.INDIAN_DRUG_LEXICON:
            b = item["brand"].lower()
            g = item["generic"].lower()
            
            # Exact or prefix match gets top score
            if b.startswith(q) or g.startswith(q):
                score = 0
            elif q in b or q in g:
                score = 1
            else:
                dist_b = cls._levenshtein(q, b[:len(q) + 2])
                dist_g = cls._levenshtein(q, g[:len(q) + 2])
                score = min(dist_b, dist_g) + 2

            if score <= 5:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0])
        return [item for _, item in scored[:limit]]

