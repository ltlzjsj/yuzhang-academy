import { onBeforeUnmount, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

export interface VisemeFrame {
  start: number
  end: number
  visemes: Record<string, number>
}

/**
 * 音素对齐语音播放：调 /voice/tts/aligned 拿到音频 + viseme 时间轴，
 * 播放时按当前时间把口型权重通过回调抛给 3D 数字人。
 */
export function useAlignedSpeech(applyViseme?: (weights: Record<string, number> | null) => void) {
  const speaking = ref(false)
  const loading = ref(false)
  const error = ref('')

  let audio: HTMLAudioElement | null = null
  let url: string | null = null
  let raf = 0
  let timeline: VisemeFrame[] = []
  let stopped = false
  // 逐句播报用：正在播放时再来的句子排队，播完自动接着播
  const queue: string[] = []

  function base64ToBlob(b64: string, mime: string): Blob {
    const bin = atob(b64)
    const arr = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
    return new Blob([arr], { type: mime || 'audio/wav' })
  }

  function clearViseme() {
    applyViseme?.(null)
  }

  function loop() {
    if (!audio || stopped) return
    const t = audio.currentTime
    const frame = timeline.find((f) => t >= f.start && t < f.end)
    applyViseme?.(frame ? frame.visemes : null)
    raf = requestAnimationFrame(loop)
  }

  /** 整段朗读：打断当前播放并清空队列（回答首播、手动点「朗读」用）。 */
  async function speak(text: string, opts?: { voiceDesc?: string }) {
    const t = (text || '').trim()
    if (!t) return
    stop()
    await playOne(t, opts)
  }

  /** 逐句流式播报：正在播就排队，播完自动接着播下一句。 */
  function enqueue(text: string, opts?: { voiceDesc?: string }) {
    const t = (text || '').trim()
    if (!t) return
    if (speaking.value || loading.value) {
      queue.push(t)
      return
    }
    void playOne(t, opts)
  }

  async function playOne(text: string, opts?: { voiceDesc?: string }) {
    if (!text.trim()) return
    stopped = false
    loading.value = true
    speaking.value = true
    try {
      const auth = useAuthStore()
      const resp = await fetch('/api/v1/voice/tts/aligned', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
        },
        body: JSON.stringify({ text: text.trim(), voice_desc: opts?.voiceDesc }),
      })
      if (!resp.ok) {
        const detail = await resp.text().catch(() => '')
        throw new Error(`语音合成失败：${detail || resp.statusText}`)
      }
      const data = await resp.json()
      if (stopped) return

      timeline = data.visemes || []
      const blob = base64ToBlob(data.audio, data.mime)
      url = URL.createObjectURL(blob)
      audio = new Audio(url)
      audio.onended = () => {
        speaking.value = false
        loading.value = false
        clearViseme()
        const next = queue.shift()
        if (next) void playOne(next)
      }
      audio.onerror = () => {
        error.value = '语音播放失败'
        speaking.value = false
        loading.value = false
        clearViseme()
        queue.length = 0
      }
      await audio.play()
      loading.value = false
      loop()
    } catch (e: any) {
      if (!stopped) error.value = e?.message || '语音合成失败'
      speaking.value = false
      loading.value = false
    }
  }

  function stop() {
    stopped = true
    queue.length = 0
    if (raf) cancelAnimationFrame(raf)
    raf = 0
    clearViseme()
    if (audio) {
      audio.pause()
      audio.src = ''
      audio = null
    }
    if (url) {
      URL.revokeObjectURL(url)
      url = null
    }
    speaking.value = false
    loading.value = false
  }

  onBeforeUnmount(stop)

  return { speaking, loading, error, speak, enqueue, stop }
}
