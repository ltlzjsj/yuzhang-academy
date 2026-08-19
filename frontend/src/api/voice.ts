import { http } from './http'
import { blobToWav } from '@/utils/audio'
import { useAuthStore } from '@/stores/auth'

/** 语音识别：上传录音 Blob，返回识别文本。 */
export async function transcribe(audio: Blob, language = 'zh'): Promise<string> {
  // MiMo ASR 只认 wav/mp3；浏览器录音通常是 webm/opus，先转成 16k 单声道 WAV。
  let upload = audio
  const t = audio.type.toLowerCase()
  if (!t.includes('wav') && !t.includes('mpeg') && !t.includes('mp3')) {
    upload = await blobToWav(audio)
  }
  const form = new FormData()
  const ext = upload.type.includes('mpeg') ? 'mp3' : upload.type.includes('wav') ? 'wav' : 'webm'
  form.append('file', upload, `speech.${ext}`)
  form.append('language', language)
  const { data } = await http.post<{ text: string }>('/voice/asr', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
  return data.text
}

export interface SynthOpts {
  voice?: string
  voiceStyle?: string
  voiceDesc?: string // 古风音色描述；传了就走声音设计模型
  format?: string
}

/** 语音合成：文字 → 可播放的 audio Blob。 */
export async function synthesize(text: string, opts: SynthOpts = {}): Promise<Blob> {
  const { data } = await http.post(
    '/voice/tts',
    {
      text,
      voice: opts.voice,
      voice_style: opts.voiceStyle,
      voice_desc: opts.voiceDesc,
      format: opts.format,
    },
    { responseType: 'blob', timeout: 60000 },
  )
  return data as Blob
}

export interface TtsPcmStream {
  reader: ReadableStreamDefaultReader<Uint8Array>
  sampleRate: number
}

/** 低延迟语音合成：返回 24kHz mono PCM16LE 字节流，供 Web Audio 边收边播。 */
export async function synthesizeStream(text: string, opts: SynthOpts = {}): Promise<TtsPcmStream> {
  const auth = useAuthStore()
  const resp = await fetch('/api/v1/voice/tts/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
    },
    body: JSON.stringify({
      text,
      voice: opts.voice,
      voice_style: opts.voiceStyle,
      voice_desc: opts.voiceDesc,
      format: 'pcm16',
    }),
  })
  if (!resp.ok || !resp.body) {
    const detail = await resp.text().catch(() => '')
    throw new Error(`语音合成失败：${detail || resp.statusText}`)
  }
  return {
    reader: resp.body.getReader(),
    sampleRate: Number(resp.headers.get('X-Audio-Sample-Rate')) || 24000,
  }
}

export interface VoiceList {
  voices: string[]
  default: string
}

export async function listVoices(): Promise<VoiceList> {
  return (await http.get<VoiceList>('/voice/voices')).data
}
