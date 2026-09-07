// High-Fidelity Audio and Text-to-Speech Controller for MediKiosk
// Uses a strict singleton pattern to ensure exactly ONE clear, natural voice plays without overlapping.

// Relative, so it resolves against whatever host is serving the kiosk. Pointing
// at localhost meant every deployed browser asked its own machine for speech --
// and being http:// on an https:// page, it was blocked as mixed content before
// the request was even attempted, silencing text-to-speech everywhere but the
// developer's laptop.
const API_BASE = '/api';

let activeAudioElement: HTMLAudioElement | null = null;
let currentPlaybackId = 0;

/**
 * Stops all ongoing speech immediately (both audio stream and browser speech synthesis).
 */
export function stopTextToSpeech() {
  currentPlaybackId++;

  if (activeAudioElement) {
    try {
      activeAudioElement.pause();
      activeAudioElement.currentTime = 0;
      activeAudioElement.src = '';
    } catch (e) {
      // ignore
    }
    activeAudioElement = null;
  }

  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
    } catch (e) {
      // ignore
    }
  }
}

/**
 * Plays text aloud using the high-fidelity Google Neural TTS backend stream (natural, human-like voice).
 * Guarantees single-voice playback across all 5 Indian languages.
 */
export function playTextToSpeech(text: string, language: string = 'en', rate: number = 0.95) {
  if (!text || !text.trim()) return;

  // 1. Immediately cancel any currently playing voice
  stopTextToSpeech();

  const playbackId = ++currentPlaybackId;
  const langCode = language.toLowerCase().split('-')[0] || 'en';
  const validLang = ['bn', 'hi', 'ta', 'te', 'en'].includes(langCode) ? langCode : 'en';

  // 2. Primary: High-fidelity natural voice streamed from backend TTS endpoint
  try {
    const ttsUrl = `${API_BASE}/audio/tts?text=${encodeURIComponent(text.trim())}&lang=${validLang}`;
    const audio = new Audio(ttsUrl);
    audio.playbackRate = Math.max(0.6, Math.min(1.5, rate));
    activeAudioElement = audio;

    audio.onended = () => {
      if (activeAudioElement === audio) {
        activeAudioElement = null;
      }
    };

    audio.onerror = () => {
      // Only fallback to browser local synthesis if backend stream fails AND this is still the active speech request
      if (playbackId === currentPlaybackId) {
        playBrowserSpeechFallback(text, validLang, rate, playbackId);
      }
    };

    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {
        // If audio autoplay or network error occurs, fallback to browser synthesis
        if (playbackId === currentPlaybackId) {
          playBrowserSpeechFallback(text, validLang, rate, playbackId);
        }
      });
    }
  } catch (err) {
    playBrowserSpeechFallback(text, validLang, rate, playbackId);
  }
}

/**
 * Fallback browser SpeechSynthesis (only used if backend stream is offline).
 */
function playBrowserSpeechFallback(text: string, langCode: string, rate: number, playbackId: number) {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
  if (playbackId !== currentPlaybackId) return;

  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const matchingVoice = voices.find(v => v.lang.toLowerCase().startsWith(langCode));

    if (matchingVoice) {
      utterance.voice = matchingVoice;
      utterance.lang = matchingVoice.lang;
    } else {
      utterance.lang = langCode === 'hi' ? 'hi-IN' : langCode === 'bn' ? 'bn-IN' : langCode === 'ta' ? 'ta-IN' : langCode === 'te' ? 'te-IN' : 'en-IN';
    }

    utterance.rate = Math.max(0.6, Math.min(1.5, rate));
    utterance.pitch = 1.0;

    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn('Speech synthesis fallback notice:', e);
  }
}

// Multilingual audio explanation for DPDP / Consent
export function playConsentAudio(language: string = 'en', rate: number = 0.95) {
  const explanation = language === 'hi' 
    ? "नमस्ते। मेडीकियोस्क में आपकी आवाज, लक्षण और पुराने पर्चे सुरक्षित रूप से दर्ज किए जाते हैं ताकि डॉक्टर को आपका पूरा विवरण तुरंत मिल सके और आपका समय बचे।"
    : language === 'bn'
    ? "নমস্কার। মেডিকিয়স্কে আপনার লক্ষণ, কণ্ঠস্বর ও পুরনো প্রেসক্রিপশন নিরাপদে রেকর্ড করা হয় যাতে ডাক্তারবাবু আপনার সম্পূর্ণ তথ্য সহজে পর্যালোচনা করতে পারেন।"
    : language === 'ta'
    ? "வணக்கம். மெடிகியோஸ்கில் உங்கள் அறிகுறிகள் மற்றும் ஆவணங்கள் பாதுகாப்பாக பதிவு செய்யப்படுகின்றன."
    : language === 'te'
    ? "నమస్కారం. మెడికియోస్క్‌లో మీ లక్షణాలు మరియు పత్రాలు సురక్షితంగా రికార్డ్ చేయబడతాయి."
    : "Welcome to MediKiosk. We securely record your symptoms, voice, and medical documents to prepare a structured clinical summary for your OPD doctor, saving your valuable consultation time.";
  playTextToSpeech(explanation, language, rate);
}

// Multilingual audio announcement when staff assistance is requested
export function playStaffAssistanceAudio(language: string = 'en', rate: number = 0.95) {
  const msg = language === 'hi'
    ? "सहायता अनुरोध भेज दिया गया है। अस्पताल स्टाफ नर्स आपकी मदद के लिए जल्द ही आ रही हैं।"
    : language === 'bn'
    ? "সহায়তার জন্য জানানো হয়েছে। হাসপাতালের স্টাফ নার্স শীঘ্রই আপনার কাছে আসছেন।"
    : language === 'ta'
    ? "பணியாளர் உதவி கோரப்பட்டுள்ளது. மருத்துவமனை ஊழியர் விரைவில் வருவார்."
    : language === 'te'
    ? "సిబ్బంది సహాయం కోసం తెలియజేయబడింది. ఆసుపత్రి సిబ్బంది త్వరలోనే వస్తారు."
    : "Help has been requested. A hospital staff nurse has been notified and will assist you shortly.";
  playTextToSpeech(msg, language, rate);
}
