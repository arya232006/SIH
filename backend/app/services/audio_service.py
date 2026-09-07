import os
import base64
import json
import re
from typing import Dict, Any, Optional, List
import httpx

from app.config import settings
from app.models import AudioTranscriptionResponse

class AudioService:
    """
    Multilingual Audio Transcription & Accent Normalization Service for Indian Hospital OPDs.
    Supports Whisper Large-v3, Gemini Multimodal Audio, and an Indic Clinical Colloquial Normalizer.
    """

    ACCENT_MAPPINGS = {
        "en-IN": "Indian English (Standard OPD Dialect)",
        "hi-IN": "Hindi / Hinglish (North / Central India)",
        "bn-IN": "Bengali / Benglish (Eastern India)",
        "ta-IN": "Tamil / Tanglish (Southern India)",
        "te-IN": "Telugu (Southern India)",
        "mr-IN": "Marathi (Western India)",
        "gu-IN": "Gujarati (Western India)",
        "kn-IN": "Kannada (Southern India)",
        "ml-IN": "Malayalam (Southern India)"
    }

    # Common Indian OPD colloquial phrases to standard medical concepts
    COLLOQUIAL_LEXICON = [
        (r"(seene\s*me\s*jalan|chhati\s*me\s*jalan|chaati\s*me\s*jalan)", "Retrosternal burning / Dyspepsia"),
        (r"(gas\s*chad\s*gayi|gas\s*ki\s*problem|pet\s*me\s*gas|pet\s*me\s*jalan|pete\s*jalan|acidity|vayiru\s*erichal|kadupulo\s*manta)", "Dyspepsia / Acid Reflux"),
        (r"(left\s*haath\s*me\s*dard|haath\s*sunn|baayein\s*haath)", "Left arm radiation / Paresthesia"),
        (r"(ghabrahat\s*ho\s*rahi|dil\s*dhadak\s*raha)", "Palpitations / Anxiety"),
        (r"(saans\s*phool\s*rahi|saans\s*lene\s*me\s*takleef|dam\s*ghutna|breathlessness)", "Exertional dyspnea / Shortness of breath"),
        (r"(chakkar\s*aa\s*rahe|sir\s*ghoom\s*raha|dizziness)", "Vertigo / Presyncope"),
        (r"(sugar\s*badh\s*gaya|sugar\s*ki\s*bimaari|diabetes)", "Type 2 Diabetes Mellitus"),
        (r"(bp\s*badh\s*gaya|bp\s*ki\s*goli|high\s*pressure|blood\s*pressure|bp\s*tablet|bp\s*maathirai)", "Essential Hypertension"),
        (r"(ghutne\s*me\s*dard|subah\s*akad\s*jaate|sandhivata|joint\s*pain)", "Knee joint pain / Morning stiffness"),
        (r"(bukhar\s*ke\s*saath\s*thand|tharthari|kapkapi|bukhar|fever)", "Fever with chills and rigors"),
        (r"(khoon\s*ki\s*ulti|ulti\s*me\s*khoon|hematemesis)", "Hematemesis (Acute GI bleed)"),
        (r"(gale\s*me\s*kharash|sukhi\s*khansi|cough)", "Pharyngitis / Dry cough")
    ]

    @classmethod
    async def transcribe_audio(
        cls,
        audio_bytes: bytes,
        filename: str = "recording.webm",
        content_type: str = "audio/webm",
        language_hint: str = "en-IN",
        accent_hint: Optional[str] = None
    ) -> AudioTranscriptionResponse:
        """
        Transcribes patient speech and produces an English rendering for the
        clinical engines.

        Two things matter here beyond getting words out of audio:

        1. The transcript must be verbatim and in the language spoken -- it goes
           on the record and is read back to the patient for confirmation.
        2. Red-flag detection, routing and symptom categorisation all match
           romanised/English keywords. A correct Devanagari transcript matches
           none of them, so a patient describing crushing chest pain in Hindi
           would raise no red flag at all. Whatever the patient speaks, the rules
           need English, so a translation is produced alongside the verbatim.
        """
        if not audio_bytes:
            return cls._failed("No audio was received.")

        lang = (language_hint or "en-IN").split("-")[0].lower()

        if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY and not settings.GEMINI_API_KEY:
            print("[Audio] No speech provider is configured on this server.")
            return cls._failed(
                "Voice input is not available: this server has no speech "
                "recognition service configured. Please type your answer or "
                "tap an option, and tell the help desk. "
                "(Set OPENAI_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY.)")

        # Provider outages are recorded separately from "heard nothing". They are
        # different problems with different remedies: one is a billing or key
        # issue for the operator, the other is genuinely worth asking the patient
        # to repeat. Telling someone to speak more clearly when the account is
        # out of quota just makes them try, and fail, again.
        outages: List[str] = []

        if settings.OPENAI_API_KEY:
            try:
                transcript, detected, confidence, problem = await cls._openai_transcribe(
                    audio_bytes, filename, content_type, lang)
                if transcript:
                    clinical = transcript
                    # Only pay for a second call when the speech was not English.
                    if detected and detected != "en":
                        clinical = await cls._openai_translate(
                            audio_bytes, filename, content_type) or transcript
                    return AudioTranscriptionResponse(
                        transcript=transcript,
                        clinicalText=clinical if clinical != transcript else None,
                        detectedLanguage=f"{detected or lang}-IN",
                        accent=accent_hint or cls.ACCENT_MAPPINGS.get(
                            language_hint, "Indian English / Hinglish"),
                        confidence=confidence,
                        source="openai_whisper",
                        normalizedMedicalTerms=cls._extract_normalized_concepts(clinical),
                    )
                if problem:
                    outages.append(f"OpenAI Whisper: {problem}")
            except Exception as e:
                outages.append(f"OpenAI Whisper unreachable ({type(e).__name__})")
                print(f"[OpenAI Whisper Transcribe Error] {type(e).__name__}: {e}")

        if settings.GROQ_API_KEY:
            try:
                transcript, detected, confidence, problem = await cls._groq_transcribe(
                    audio_bytes, filename, content_type, lang)
                if transcript:
                    clinical = transcript
                    # Only pay for a second call when the speech was not English.
                    if detected and detected != "en":
                        clinical = await cls._groq_translate(
                            audio_bytes, filename, content_type) or transcript
                    return AudioTranscriptionResponse(
                        transcript=transcript,
                        clinicalText=clinical if clinical != transcript else None,
                        detectedLanguage=f"{detected or lang}-IN",
                        accent=accent_hint or cls.ACCENT_MAPPINGS.get(
                            language_hint, "Indian English / Hinglish"),
                        confidence=confidence,
                        source="whisper",
                        normalizedMedicalTerms=cls._extract_normalized_concepts(clinical),
                    )
                if problem:
                    outages.append(f"Whisper: {problem}")
            except Exception as e:
                outages.append(f"Whisper unreachable ({type(e).__name__})")
                print(f"[Whisper Transcribe Error] {type(e).__name__}: {e}")

        if settings.GEMINI_API_KEY:
            try:
                result, problem = await cls._gemini_transcribe(
                    audio_bytes, content_type, language_hint, accent_hint)
                if result:
                    return result
                if problem:
                    outages.append(f"Gemini: {problem}")
            except Exception as e:
                outages.append(f"Gemini unreachable ({type(e).__name__})")
                print(f"[Gemini Audio Error] {type(e).__name__}: {e}")

        # No fabricated transcript. This previously returned a canned sentence
        # with 0.91 confidence, so a patient describing chest pain could be
        # recorded as having acid reflux -- and that text became the chief
        # complaint driving red flags, routing and the whole downstream summary.
        if outages:
            detail = "; ".join(outages)
            print(f"[Audio] Every speech provider failed -- {detail}")
            return cls._failed(
                "The speech service is unavailable right now, so nothing was "
                "recorded. Please type your answer or tap an option, and tell "
                f"the help desk. ({detail})")

        print("[Audio] Providers responded but no speech was recognised.")
        return cls._failed(
            "No words could be made out in the recording. Please speak a little "
            "closer to the microphone and try again, or tap an answer instead.")

    @classmethod
    def _failed(cls, message: str) -> AudioTranscriptionResponse:
        return AudioTranscriptionResponse(
            transcript="", clinicalText=None, detectedLanguage="unknown",
            accent=None, confidence=0.0, source="transcription_failed",
            normalizedMedicalTerms=[], error=message,
        )

    @staticmethod
    def _describe_http(status: int, body: str) -> str:
        """
        Turns a provider's HTTP failure into something an operator can act on.

        The distinction that matters is billing/credentials versus a bad request:
        the first needs somebody to log into a console, the second is our bug.
        """
        lowered = (body or "").lower()
        if status in (401, 403):
            return "the API key was rejected"
        if status == 429 or "quota" in lowered or "rate limit" in lowered:
            return "the account is out of quota or rate limited"
        if "restricted" in lowered:
            return "the account has been restricted by the provider"
        if status == 400:
            return f"the request was rejected ({body[:80].strip()})"
        return f"HTTP {status}"

    @classmethod
    async def _openai_transcribe(cls, audio_bytes, filename, content_type, lang):
        """
        Verbatim transcription via OpenAI Whisper.
        """
        data = {
            "model": settings.OPENAI_AUDIO_MODEL,
            "prompt": ("Indian OPD hospital intake: chest pain, blood pressure, sugar, "
                       "cough, fever, vomiting, jalan, ghabrahat, saans, seene mein dard, "
                       "bukhar, dolo 650, metformin, telma."),
            "response_format": "verbose_json",
        }
        if lang and lang != "auto":
            data["language"] = lang

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                files={"file": (filename, audio_bytes, content_type)},
                data=data)
            if resp.status_code != 200:
                print(f"[OpenAI Audio] HTTP {resp.status_code}: {resp.text[:200]}")
                return "", "", 0.0, cls._describe_http(resp.status_code, resp.text)
            body = resp.json()
            text = (body.get("text") or "").strip()
            detected = (body.get("language") or "").lower()[:2]
            return text, detected, cls._confidence_from(body), None

    @classmethod
    async def _openai_translate(cls, audio_bytes, filename, content_type) -> str:
        """
        English rendering via OpenAI Whisper translation endpoint.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/translations",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                files={"file": (filename, audio_bytes, content_type)},
                data={"model": settings.OPENAI_AUDIO_MODEL})
            if resp.status_code != 200:
                print(f"[OpenAI Audio translate] HTTP {resp.status_code}: {resp.text[:200]}")
                return ""
            return (resp.json().get("text") or "").strip()

    @classmethod
    async def _groq_transcribe(cls, audio_bytes, filename, content_type, lang):
        """
        Verbatim transcription.

        Returns (text, detected_language, confidence, problem), where `problem`
        is set only when the provider itself failed rather than simply hearing
        nothing worth transcribing.
        """
        data = {
            "model": "whisper-large-v3",
            # Priming the decoder with terms it would otherwise mangle.
            "prompt": ("Indian OPD hospital intake: chest pain, blood pressure, sugar, "
                       "cough, fever, vomiting, jalan, ghabrahat, saans, seene mein dard, "
                       "bukhar, dolo 650, metformin, telma."),
            "temperature": "0.0",
            # verbose_json returns the language Whisper actually detected and
            # per-segment scores, instead of us echoing back our own guess and
            # a hardcoded confidence.
            "response_format": "verbose_json",
        }
        # Telling Whisper the expected language measurably improves short clips.
        if lang and lang != "auto":
            data["language"] = lang

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                files={"file": (filename, audio_bytes, content_type)},
                data=data)
            if resp.status_code != 200:
                print(f"[Whisper] HTTP {resp.status_code}: {resp.text[:200]}")
                return "", "", 0.0, cls._describe_http(resp.status_code, resp.text)
            body = resp.json()
            text = (body.get("text") or "").strip()
            detected = (body.get("language") or "").lower()[:2]
            return text, detected, cls._confidence_from(body), None

    @classmethod
    async def _groq_translate(cls, audio_bytes, filename, content_type) -> str:
        """
        English rendering via Whisper's translation endpoint. Purpose-built for
        this and cheaper than transcribing then translating with a text model.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/translations",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                files={"file": (filename, audio_bytes, content_type)},
                data={"model": "whisper-large-v3", "temperature": "0.0"})
            if resp.status_code != 200:
                print(f"[Whisper translate] HTTP {resp.status_code}: {resp.text[:200]}")
                return ""
            return (resp.json().get("text") or "").strip()

    @staticmethod
    def _confidence_from(body: dict) -> float:
        """
        Derived from Whisper's own segment scores rather than asserted. avg_logprob
        near 0 is confident, -1 and below is poor; no_speech_prob high means it
        probably heard nothing worth keeping.
        """
        segments = body.get("segments") or []
        if not segments:
            return 0.75
        import math
        logprobs, no_speech = [], []
        for seg in segments:
            if "avg_logprob" in seg:
                logprobs.append(float(seg["avg_logprob"]))
            if "no_speech_prob" in seg:
                no_speech.append(float(seg["no_speech_prob"]))
        if not logprobs:
            return 0.75
        score = math.exp(sum(logprobs) / len(logprobs))          # 0..1
        if no_speech:
            score *= (1.0 - min(0.9, sum(no_speech) / len(no_speech)))
        return round(max(0.05, min(0.99, score)), 2)

    # Audio containers Gemini accepts as inline data. A browser recording is
    # WebM or MP4, neither of which is on this list, so the kiosk converts to
    # WAV before uploading -- but a stray content type must not be forwarded
    # blindly, because the rejection looks identical to silence.
    GEMINI_AUDIO_MIME = {
        "audio/wav": "audio/wav", "audio/x-wav": "audio/wav",
        "audio/wave": "audio/wav", "audio/vnd.wave": "audio/wav",
        "audio/mp3": "audio/mp3", "audio/mpeg": "audio/mp3",
        "audio/aiff": "audio/aiff", "audio/aac": "audio/aac",
        "audio/ogg": "audio/ogg", "audio/flac": "audio/flac",
    }

    @classmethod
    async def _gemini_transcribe(cls, audio_bytes, content_type, language_hint,
                                 accent_hint):
        """
        Fallback when Groq is unavailable. Asked for the verbatim words and an
        English rendering in one response, so the clinical engines still have
        something to match on for non-English speech.

        Returns (response, problem); `problem` is set only for provider failures.
        """
        mime = cls.GEMINI_AUDIO_MIME.get(
            (content_type or "").split(";")[0].strip().lower())
        if not mime:
            return None, (f"cannot read {content_type or 'unknown'} audio "
                          f"(supported: {', '.join(sorted(set(cls.GEMINI_AUDIO_MIME.values())))})")

        spoken = cls.ACCENT_MAPPINGS.get(language_hint, "an Indian language")
        prompt = f"""You are a multilingual Indian medical speech recogniser for a hospital intake kiosk.
The audio is a patient describing symptoms. The kiosk is set to {spoken}, but the
patient may speak any of Indian English, Hindi, Bengali, Tamil, Telugu or Hinglish.

Return STRICT JSON only:
{{
  "transcript": "exact words spoken, in the language spoken",
  "english": "faithful English rendering of the same words",
  "detected_language": "en | hi | bn | ta | te",
  "confidence": 0.0 to 1.0
}}
Transcribe only what was said. Never guess at symptoms that were not spoken.
If the audio is unintelligible or silent, return an empty transcript."""

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}")
        payload = {
            "contents": [{"role": "user", "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime,
                                 "data": base64.b64encode(audio_bytes).decode("utf-8")}},
            ]}],
            "generationConfig": {"temperature": 0.0, "response_mime_type": "application/json"},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                print(f"[Gemini Audio] HTTP {resp.status_code}: {resp.text[:200]}")
                return None, cls._describe_http(resp.status_code, resp.text)
            try:
                raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
            except (KeyError, IndexError, ValueError) as e:
                print(f"[Gemini Audio] unparseable response: {type(e).__name__}: {e}")
                return None, "the response could not be read"

        transcript = (data.get("transcript") or "").strip()
        if not transcript:
            return None, None          # heard nothing; not a provider failure
        english = (data.get("english") or "").strip()
        detected = (data.get("detected_language") or "en").lower()[:2]
        return AudioTranscriptionResponse(
            transcript=transcript,
            clinicalText=english if english and english != transcript else None,
            detectedLanguage=f"{detected}-IN",
            accent=accent_hint or cls.ACCENT_MAPPINGS.get(language_hint, "Indian English"),
            confidence=float(data.get("confidence", 0.8)),
            source="gemini_audio",
            normalizedMedicalTerms=cls._extract_normalized_concepts(english or transcript),
        ), None

    @classmethod
    async def synthesize_speech(cls, text: str, language: str = "en") -> bytes:
        """
        Synthesizes high-clarity spoken audio for Indian languages (Bengali, Tamil, Telugu, Hindi,
        Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, English) using neural audio synthesis.
        """
        lang_map = {
            "bn": "bn",
            "bn-in": "bn",
            "bn-bd": "bn",
            "hi": "hi",
            "hi-in": "hi",
            "ta": "ta",
            "ta-in": "ta",
            "te": "te",
            "te-in": "te",
            "mr": "mr",
            "mr-in": "mr",
            "gu": "gu",
            "gu-in": "gu",
            "kn": "kn",
            "kn-in": "kn",
            "ml": "ml",
            "ml-in": "ml",
            "pa": "pa",
            "pa-in": "pa",
            "or": "or",
            "or-in": "or",
            "en": "en-in",
            "en-in": "en-in",
            "en-us": "en",
            "en-gb": "en-gb",
        }
        clean_lang = lang_map.get((language or "en").lower().strip(), "en-in")
        
        # Clean text of markdown, json symbols, redundant spaces
        clean_text = re.sub(r'[\*\_\[\]\(\)\{\}\#\<\>]', ' ', text or "")
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        if not clean_text:
            clean_text = "Medical intake ready."

        # Break text into small natural sentences/clauses under 180 chars for Google TTS
        delimiters = r'([।\.\?\!\,;\n])'
        parts = [p.strip() for p in re.split(delimiters, clean_text) if p.strip()]
        chunks: List[str] = []
        curr = ""
        for p in parts:
            if len(curr) + len(p) + 1 < 170:
                curr = (curr + " " + p).strip() if curr else p
            else:
                if curr:
                    chunks.append(curr)
                curr = p
        if curr:
            chunks.append(curr)
            
        if not chunks:
            chunks = [clean_text[:170]]

        audio_chunks = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for chunk in chunks:
                try:
                    resp = await client.get(
                        "https://translate.google.com/translate_tts",
                        params={
                            "ie": "UTF-8",
                            "tl": clean_lang,
                            "client": "tw-ob",
                            "q": chunk
                        },
                        headers=headers
                    )
                    if resp.status_code == 200 and len(resp.content) > 0:
                        audio_chunks.append(resp.content)
                except Exception as e:
                    print(f"[TTS Synthesize Error on '{chunk[:20]}...']: {e}")
                    
        if audio_chunks:
            return b"".join(audio_chunks)
            
        return b""

    @classmethod
    def _extract_normalized_concepts(cls, text: str) -> List[str]:
        """Maps colloquial words in transcript to standardized medical terminology."""
        found = []
        for pattern, concept in cls.COLLOQUIAL_LEXICON:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(concept)
        return found



audio_service = AudioService()
