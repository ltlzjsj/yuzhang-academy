import { onBeforeUnmount, ref } from 'vue'

/**
 * 麦克风录音封装（基于 MediaRecorder）。
 *
 * 浏览器原生录音多为 webm/opus；MiMo ASR 文档目前明确支持 wav/mp3。
 * 骨架阶段先把 webm 原样上传，由后端/MiMo 处理；若识别失败，后续可在此
 * 接入 wav 转码（如 OfflineAudioContext 重采样为 16k PCM WAV）。TODO。
 */
export function useVoiceRecorder() {
  const recording = ref(false)
  const error = ref('')
  let media: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let chunks: Blob[] = []
  let resolveStop: ((b: Blob | null) => void) | null = null

  function pickMime(): string {
    const prefs = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg']
    for (const m of prefs) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(m)) return m
    }
    return ''
  }

  async function start(): Promise<boolean> {
    error.value = ''
    if (recording.value) return false
    if (!navigator.mediaDevices?.getUserMedia) {
      error.value = '当前浏览器不支持录音。'
      return false
    }
    try {
      // 开启浏览器侧降噪/回声消除/自动增益，单声道 —— 对识别准确率影响很大。
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    } catch {
      error.value = '无法访问麦克风，请检查权限。'
      return false
    }
    chunks = []
    const mime = pickMime()
    media = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
    media.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data)
    }
    media.onstop = () => {
      const type = media?.mimeType || 'audio/webm'
      const blob = chunks.length ? new Blob(chunks, { type }) : null
      cleanup()
      resolveStop?.(blob)
      resolveStop = null
    }
    media.start()
    recording.value = true
    return true
  }

  /** 停止录音，返回录得的音频 Blob（无数据时返回 null）。 */
  function stop(): Promise<Blob | null> {
    if (!media || !recording.value) return Promise.resolve(null)
    recording.value = false
    return new Promise((resolve) => {
      resolveStop = resolve
      media?.stop()
    })
  }

  /** 取消录音并丢弃数据。 */
  function cancel() {
    resolveStop = null
    if (media && recording.value) media.stop()
    recording.value = false
    cleanup()
  }

  function cleanup() {
    stream?.getTracks().forEach((t) => t.stop())
    stream = null
    media = null
  }

  onBeforeUnmount(cancel)

  return { recording, error, start, stop, cancel }
}
