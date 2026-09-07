// Microphone capture helpers for the kiosk.
//
// Every browser's MediaRecorder produces a different container -- Chrome gives
// WebM/Opus, Safari gives MP4/AAC, Firefox gives Ogg -- and each speech provider
// accepts a different subset. The kiosk used to record in whatever the browser
// chose and upload it labelled `audio/webm` regardless of what was actually
// inside, so on some browsers every request was rejected before a word was read.
//
// Converting here removes the guesswork: WAV is the one format every provider
// documents, 16 kHz mono is what speech models want anyway, and it is a quarter
// the size of 48 kHz stereo over a hospital connection.

const TARGET_SAMPLE_RATE = 16000;

export interface EncodedAudio {
  blob: Blob;
  durationSeconds: number;
  /** Loudest sample, 0..1. Near zero means the mic captured silence. */
  peak: number;
}

/** The best container this browser can actually record, or '' for its default. */
export function pickRecorderMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return '';
  const preferred = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  for (const type of preferred) {
    if (typeof MediaRecorder.isTypeSupported === 'function' &&
        MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return '';
}

/** Whether this page can open a microphone at all, and why not if it cannot. */
export function microphoneSupport(): { ok: boolean; reason?: string } {
  if (typeof navigator === 'undefined' ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== 'function') {
    // navigator.mediaDevices is simply absent on insecure origins, which is
    // easy to mistake for an unsupported browser when testing over a LAN IP.
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      return {
        ok: false,
        reason: 'Microphone access needs a secure (https) connection. ' +
                'Open this kiosk over https, or on localhost.',
      };
    }
    return {
      ok: false,
      reason: 'This browser cannot record audio. Please type your answer or ' +
              'tap one of the options below.',
    };
  }
  return { ok: true };
}

/** Plain-language explanation of a getUserMedia rejection. */
export function describeMicError(err: unknown): string {
  const name = (err as { name?: string })?.name || '';
  switch (name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
    case 'SecurityError':
      return 'Microphone permission is blocked. Allow microphone access from ' +
             'the icon in the browser address bar, then tap the mic again.';
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'No microphone was found on this kiosk. Please type your answer ' +
             'or tap an option below.';
    case 'NotReadableError':
    case 'TrackStartError':
      return 'The microphone is already in use by another application and ' +
             'could not be opened.';
    case 'OverconstrainedError':
      return 'The microphone does not support the required audio settings.';
    default:
      return `The microphone could not be started (${name || 'unknown error'}).`;
  }
}

/** Decodes a browser recording and re-encodes it as 16 kHz mono 16-bit WAV. */
export async function encodeToWav(recording: Blob): Promise<EncodedAudio> {
  const AudioCtor: typeof AudioContext | undefined =
    (window as any).AudioContext || (window as any).webkitAudioContext;
  if (!AudioCtor) throw new Error('This browser cannot decode audio.');

  const context = new AudioCtor();
  let decoded: AudioBuffer;
  try {
    decoded = await context.decodeAudioData(await recording.arrayBuffer());
  } finally {
    // The decoded AudioBuffer is independent of the context, so closing here
    // avoids leaving a hardware audio context open on a long-running kiosk.
    context.close().catch(() => undefined);
  }

  const { samples, sampleRate } = await toMono16k(decoded);
  let peak = 0;
  for (let i = 0; i < samples.length; i++) {
    const amplitude = Math.abs(samples[i]);
    if (amplitude > peak) peak = amplitude;
  }

  return {
    blob: new Blob([encodeWavBytes(samples, sampleRate)], { type: 'audio/wav' }),
    durationSeconds: samples.length / sampleRate,
    peak,
  };
}

async function toMono16k(
  buffer: AudioBuffer
): Promise<{ samples: Float32Array; sampleRate: number }> {
  const OfflineCtor: typeof OfflineAudioContext | undefined =
    (window as any).OfflineAudioContext || (window as any).webkitOfflineAudioContext;
  const frames = Math.ceil(buffer.duration * TARGET_SAMPLE_RATE);

  if (OfflineCtor && frames > 0) {
    try {
      const offline = new OfflineCtor(1, frames, TARGET_SAMPLE_RATE);
      const source = offline.createBufferSource();
      source.buffer = buffer;
      // Routing a multi-channel buffer into a mono destination downmixes it.
      source.connect(offline.destination);
      source.start();
      const rendered = await offline.startRendering();
      return { samples: rendered.getChannelData(0), sampleRate: TARGET_SAMPLE_RATE };
    } catch {
      // Some browsers refuse to build a context below 22.05 kHz. Keeping the
      // original rate still produces a valid WAV, which is what matters.
    }
  }
  return { samples: mixToMono(buffer), sampleRate: buffer.sampleRate };
}

function mixToMono(buffer: AudioBuffer): Float32Array {
  if (buffer.numberOfChannels === 1) return buffer.getChannelData(0);
  const mixed = new Float32Array(buffer.length);
  for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < data.length; i++) {
      mixed[i] += data[i] / buffer.numberOfChannels;
    }
  }
  return mixed;
}

function encodeWavBytes(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const bytes = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(bytes);
  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };

  ascii(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  view.setUint32(16, 16, true);                 // fmt chunk length
  view.setUint16(20, 1, true);                  // PCM
  view.setUint16(22, 1, true);                  // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);     // byte rate
  view.setUint16(32, 2, true);                  // block align
  view.setUint16(34, 16, true);                 // bits per sample
  ascii(36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return bytes;
}
