"""
Formulary grounding for extracted medications.

A vision model reading a handwritten prescription produces a plausible string,
not a verified product. This checks each extracted medication against a real
Indian formulary and answers three questions the model cannot:

  1. Does this brand exist?           -- catches misreadings and hallucinations
  2. Is that strength marketed?       -- "Telmisartan 400mg" is not a product
  3. What is the generic?             -- the DDI rules are written in generics,
                                         so "Tab Telma 40" is invisible to them
                                         until it is normalised to Telmisartan

Lookup is local and in-memory: microseconds, free, offline, and reproducible.
An internet search would be none of those, and "this string appears somewhere
online" is not the same question as "this is a marketed product at this dose".
The network belongs at build time, refreshing the formulary file -- not on the
path between a patient and their consultation.
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "indian_formulary.json")

# Dose-form prefixes that are not part of the product name.
_FORM_PREFIX = re.compile(
    r'^\s*(?:tab\.?|tabs?\.?|cap\.?|caps?\.?|syp\.?|syr\.?|inj\.?|susp\.?|'
    r'oint\.?|drops?\.?|sachet|powder)\s*', re.IGNORECASE)

# Trailing strength, so "Telma 40mg" matches the brand "Telma".
_TRAILING_STRENGTH = re.compile(
    r'\s*\d[\d,]*(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|k)\b.*$', re.IGNORECASE)

# A space-separated number at the end is the strength written without its unit
# -- "Telma 40", "Pan 40", "Augmentin 625" -- which is how prescriptions are
# actually written. Requiring the space keeps names like "Uprise-D3" intact.
_TRAILING_BARE_NUMBER = re.compile(r'\s+\d[\d,]*(?:\.\d+)?\s*[kK]?\s*$')

_STRENGTH_RE = re.compile(
    r'(\d[\d,]*(?:\.\d+)?)\s*(k)?\s*(mg|mcg|g|ml|iu)', re.IGNORECASE)


def normalise_name(raw: str) -> str:
    """Strips dose form, trailing strength and punctuation noise."""
    if not raw:
        return ""
    text = _FORM_PREFIX.sub("", raw.strip())
    text = _TRAILING_STRENGTH.sub("", text)
    text = _TRAILING_BARE_NUMBER.sub("", text)
    text = re.sub(r"[^\w\s\-+/]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def phonetic_key(name: str) -> str:
    """
    Phonetic key tuned for Indian pharmaceutical brand names.

    Generic algorithms such as Soundex and Double Metaphone are built around
    English surnames and fare poorly here: they do not know that Zerodol and
    Serodol, or Cifran and Siphran, are the same sound in Indian
    transliteration. These substitutions target the confusions that actually
    occur -- c/k/s, ph/f, z/s, y/i, doubled consonants, and the trailing vowels
    that brands vary freely.
    """
    t = name.lower()
    t = re.sub(r"[^a-z]", "", t)
    if not t:
        return ""

    pairs = [
        ("ph", "f"), ("gh", "g"), ("kh", "k"), ("th", "t"), ("dh", "d"),
        ("bh", "b"), ("ck", "k"), ("qu", "k"), ("sch", "s"), ("sh", "s"),
        ("ch", "s"), ("aa", "a"), ("ee", "i"), ("oo", "u"), ("ea", "i"),
        ("ie", "i"), ("ou", "u"),
    ]
    for a, b in pairs:
        t = t.replace(a, b)

    # Soft c: 'c' before i/e/y is an s sound (Cifran), otherwise a k sound
    # (Calpol). Applying this before the leading letter is taken is what lets
    # Cifran and Siphran collapse to the same key.
    t = re.sub(r"c(?=[iey])", "s", t)
    t = t.translate(str.maketrans({"c": "k", "z": "s", "x": "ks",
                                   "y": "i", "w": "v", "j": "g"}))
    t = re.sub(r"(.)\1+", r"\1", t)          # collapse doubled letters
    if not t:
        return ""
    # The leading letter is taken after substitution, so transliteration
    # variants of the same sound share a first character.
    body = re.sub(r"[aeiou]", "", t[1:])     # keep only the leading vowel
    return (t[0] + body)[:8]


def parse_strength(text: str) -> Optional[Tuple[float, str]]:
    """Returns (value, unit) normalised to a comparable form, or None."""
    if not text:
        return None
    m = _STRENGTH_RE.search(text)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    if m.group(2):                            # "60K IU"
        value *= 1000
    unit = m.group(3).lower()
    if unit == "g":                           # normalise grams to mg
        value, unit = value * 1000, "mg"
    return value, unit


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@dataclass
class FormularyMatch:
    brand: str
    generic: str
    drug_class: str
    score: float
    method: str                     # exact | phonetic | fuzzy


@dataclass
class VerificationResult:
    """What grounding concluded about one extracted medication."""
    inputName: str
    status: str                     # verified | corrected | unverified
    matchedBrand: Optional[str] = None
    generic: Optional[str] = None
    drugClass: Optional[str] = None
    matchScore: float = 0.0
    matchMethod: Optional[str] = None
    candidates: List[str] = field(default_factory=list)
    strengthText: Optional[str] = None
    strengthKnown: Optional[bool] = None      # None when the brand lists none
    knownStrengths: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inputName": self.inputName, "status": self.status,
            "matchedBrand": self.matchedBrand, "generic": self.generic,
            "drugClass": self.drugClass, "matchScore": round(self.matchScore, 3),
            "matchMethod": self.matchMethod, "candidates": self.candidates,
            "strengthText": self.strengthText, "strengthKnown": self.strengthKnown,
            "knownStrengths": self.knownStrengths, "notes": self.notes,
        }


class FormularyService:
    """Grounds extracted medication names against a real product list."""

    # Below this, a fuzzy hit is not trustworthy enough to present as a correction.
    FUZZY_ACCEPT = 0.72

    def __init__(self, path: str = DATA_PATH):
        self._entries: List[Dict[str, Any]] = []
        self._by_exact: Dict[str, Dict[str, Any]] = {}
        self._by_phonetic: Dict[str, List[Dict[str, Any]]] = {}
        self.load(path)

    def load(self, path: str) -> int:
        """
        Loads the formulary. Swapping in a larger dataset (a CDSCO export or a
        brand-generic dump) needs no code change -- only a file with the same
        brand / generic / strengths / class shape.
        """
        self._entries, self._by_exact, self._by_phonetic = [], {}, {}
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

        for row in data.get("brands", []):
            brand = row.get("brand", "").strip()
            if not brand:
                continue
            entry = {
                "brand": brand,
                "generic": row.get("generic", ""),
                "strengths": row.get("strengths", []) or [],
                "class": row.get("class", ""),
                "norm": normalise_name(brand).lower(),
                "phon": phonetic_key(brand),
                # Prescriptions are written in generics as often as brands, so
                # the generic is indexed for matching too.
                "gnorm": normalise_name(row.get("generic", "")).lower(),
                "gphon": phonetic_key(row.get("generic", "")),
            }
            self._entries.append(entry)
            self._by_exact.setdefault(entry["norm"], entry)
            self._by_phonetic.setdefault(entry["phon"], []).append(entry)
            if entry["gphon"] and entry["gphon"] != entry["phon"]:
                self._by_phonetic.setdefault(entry["gphon"], []).append(entry)
        return len(self._entries)

    @property
    def size(self) -> int:
        return len(self._entries)

    # --- Matching --------------------------------------------------------

    def match(self, raw_name: str, limit: int = 4) -> List[FormularyMatch]:
        """Ranked formulary candidates for a possibly-misread name."""
        norm = normalise_name(raw_name).lower()
        if not norm:
            return []

        exact = self._by_exact.get(norm)
        if exact:
            return [FormularyMatch(exact["brand"], exact["generic"],
                                   exact["class"], 1.0, "exact")]

        # A prescription often writes the generic directly.
        for entry in self._entries:
            if entry["generic"] and entry["generic"].lower() == norm:
                return [FormularyMatch(entry["brand"], entry["generic"],
                                       entry["class"], 0.98, "exact")]

        scored: Dict[str, FormularyMatch] = {}
        phon = phonetic_key(norm)
        for entry in self._by_phonetic.get(phon, []):
            scored[entry["brand"]] = FormularyMatch(
                entry["brand"], entry["generic"], entry["class"], 0.92, "phonetic")

        for entry in self._entries:
            if entry["brand"] in scored:
                continue
            # Score against the brand and the generic, keeping whichever the
            # reading is closer to.
            best_form = entry["norm"]
            longest = max(len(norm), len(best_form)) or 1
            sim = 1.0 - (_levenshtein(norm, best_form) / longest)
            if entry["gnorm"]:
                glongest = max(len(norm), len(entry["gnorm"])) or 1
                gsim = 1.0 - (_levenshtein(norm, entry["gnorm"]) / glongest)
                if gsim > sim:
                    sim, best_form = gsim, entry["gnorm"]
            entry = {**entry, "norm": best_form}
            longest = max(len(norm), len(best_form)) or 1
            # Truncation boost, but only when the whole reading is a prefix of
            # the brand ("Telmisar" -> "Telmisartan"). Boosting on a shared
            # four-letter head instead rewrote Cremalax to Cremaffin -- two real
            # but different products, which is worse than no match at all.
            if len(norm) >= 5 and entry["norm"].startswith(norm):
                sim = max(sim, 0.80)
            if sim >= 0.6:
                scored[entry["brand"]] = FormularyMatch(
                    entry["brand"], entry["generic"], entry["class"], sim, "fuzzy")

        return sorted(scored.values(), key=lambda m: m.score, reverse=True)[:limit]

    # --- Verification ----------------------------------------------------

    def verify(self, raw_name: str, strength_text: str = "") -> VerificationResult:
        result = VerificationResult(inputName=raw_name,
                                    strengthText=strength_text or None,
                                    status="unverified")
        matches = self.match(raw_name)
        if not matches:
            result.notes.append(
                "Not found in the formulary. Confirm with the patient before use.")
            return result

        best = matches[0]
        result.candidates = [m.brand for m in matches]
        result.matchScore = best.score
        result.matchMethod = best.method

        if best.method == "exact":
            result.status = "verified"
        elif best.score >= self.FUZZY_ACCEPT:
            result.status = "corrected"
            result.notes.append(
                f"Read as '{raw_name.strip()}'; closest marketed product is "
                f"'{best.brand}' ({best.method} match).")
        else:
            result.notes.append(
                f"No confident formulary match. Nearest: "
                f"{', '.join(result.candidates[:3])}.")
            return result

        result.matchedBrand = best.brand
        result.generic = best.generic
        result.drugClass = best.drug_class

        entry = self._by_exact.get(normalise_name(best.brand).lower())
        known = entry.get("strengths", []) if entry else []
        result.knownStrengths = known
        if strength_text and known:
            parsed = parse_strength(strength_text)
            if parsed:
                result.strengthKnown = any(
                    parse_strength(k) == parsed for k in known)
                if not result.strengthKnown:
                    result.notes.append(
                        f"Strength '{strength_text}' is not a marketed strength for "
                        f"{best.brand} (known: {', '.join(known)}). Verify the dose.")
        return result

    def verify_many(self, medications: List[Dict[str, Any]]) -> List[VerificationResult]:
        out = []
        for med in medications:
            if not isinstance(med, dict):
                out.append(self.verify(str(med)))
                continue
            out.append(self.verify(
                med.get("name", ""),
                med.get("strength") or med.get("dosage") or ""))
        return out

    def to_generic_names(self, medications: List[Any]) -> List[str]:
        """
        Brand -> generic, so the DDI rules (written in generic names) can see
        drugs a prescription recorded only by brand.
        """
        names: List[str] = []
        for med in medications:
            raw = med if isinstance(med, str) else (
                med.get("name", "") if isinstance(med, dict) else "")
            if not raw:
                continue
            names.append(raw)
            res = self.verify(raw)
            if res.generic and res.status in ("verified", "corrected"):
                names.append(res.generic)
        return names


formulary_service = FormularyService()
