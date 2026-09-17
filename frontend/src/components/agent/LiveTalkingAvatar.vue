<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  avatarId?: string
  /** 该人物的动作编排（自定义待机视频），透传给 LiveTalking 的 custom_config */
  customConfig?: string | null
  voiceId?: string | null
  voiceStyle?: string | null
  voiceDesc?: string | null
  /**
   * 画面等比放大倍数：1 = 原样铺满画面。
   * >1 时以「横向居中、纵向偏上」为基准放大，优先保住头顶留白、两侧不裁人物，
   * 多余部分由父级容器的 overflow: hidden 裁掉，视觉上人物更饱满。
   */
  zoom?: number
}>()

const zoomScale = computed(() => {
  const z = Number(props.zoom)
  return Number.isFinite(z) && z > 0 ? z : 1
})

const emit = defineEmits<{
  ready: [sessionid: string]
  error: [message: string]
  speaking: [active: boolean]
}>()

const LIVETALKING = 'http://127.0.0.1:8010'

const auth = useAuthStore()
const video = ref<HTMLVideoElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const loading = ref(true)
const error = ref('')
const sessionId = ref('')

let pc: RTCPeerConnection | null = null
let stream: MediaStream | null = null
let destroyed = false
let speakPoll: number | undefined
let drawRaf = 0

/**
 * 把 WebRTC 视频逐帧画到 canvas 上显示，video 本身缩成不可见的小块。
 * 这样浏览器就不会在鼠标移到人物上时弹出「画中画 / 增强 / 翻译音频」等原生控件。
 */
function drawFrame() {
  if (destroyed) return
  const v = video.value
  const c = canvas.value
  if (v && c && v.videoWidth > 0) {
    if (c.width !== v.videoWidth || c.height !== v.videoHeight) {
      c.width = v.videoWidth
      c.height = v.videoHeight
    }
    const ctx = c.getContext('2d')
    if (ctx) ctx.drawImage(v, 0, 0, c.width, c.height)
  }
  drawRaf = requestAnimationFrame(drawFrame)
}

function stopSpeakPoll() {
  if (speakPoll !== undefined) {
    clearInterval(speakPoll)
    speakPoll = undefined
  }
}

/**
 * 浏览器默认会拦截“带声音的自动播放”，拦截后画面会一直是黑的。
 * 这里先静音播放把人物显示出来，等用户第一次点击页面再恢复声音。
 */
let resumeAudioBound = false
let detachResumeAudio: (() => void) | null = null

async function startPlayback(el: HTMLVideoElement) {
  try {
    await el.play()
    return
  } catch {
    /* 被自动播放策略拦截，走下面的静音兜底 */
  }
  el.muted = true
  try {
    await el.play()
  } catch {
    return
  }
  if (resumeAudioBound || destroyed) return
  resumeAudioBound = true
  const resumeAudio = async () => {
    document.removeEventListener('pointerdown', resumeAudio, true)
    document.removeEventListener('keydown', resumeAudio, true)
    detachResumeAudio = null
    if (destroyed || !video.value) return
    video.value.muted = false
    try {
      await video.value.play()
    } catch {
      /* 仍然失败就保持静音，画面不受影响 */
    }
  }
  detachResumeAudio = () => {
    document.removeEventListener('pointerdown', resumeAudio, true)
    document.removeEventListener('keydown', resumeAudio, true)
    detachResumeAudio = null
  }
  document.addEventListener('pointerdown', resumeAudio, true)
  document.addEventListener('keydown', resumeAudio, true)
}

/** 轮询 LiveTalking 的播报状态，让 speaking 事件覆盖整段讲解时长。 */
function startSpeakPoll() {
  stopSpeakPoll()
  const sid = sessionId.value
  if (!sid) return
  let started = false
  let ticks = 0
  speakPoll = window.setInterval(async () => {
    ticks += 1
    try {
      const r = await fetch(`${LIVETALKING}/is_speaking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionid: sid }),
      })
      const data = await r.json().catch(() => null)
      if (data?.data) {
        started = true
        return
      }
      if (started || ticks >= 10) {
        stopSpeakPoll()
        emit('speaking', false)
      }
    } catch {
      if (ticks >= 10) {
        stopSpeakPoll()
        emit('speaking', false)
      }
    }
  }, 500)
}

async function connect() {
  if (destroyed) return
  error.value = ''
  loading.value = true

  try {
    const peer = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.freeswitch.org:3478' }],
    })
    pc = peer

    peer.addTransceiver('video', { direction: 'recvonly' })
    peer.addTransceiver('audio', { direction: 'recvonly' })

    stream = new MediaStream()
    const trackReady = new Promise<void>((resolve) => {
      peer.ontrack = (event) => {
        stream?.addTrack(event.track)
        resolve()
      }
    })

    const offer = await peer.createOffer()
    await peer.setLocalDescription(offer)

    const params = new URLSearchParams({ avatar: props.avatarId || 'jiangwanli_lt' })
    if (props.customConfig) params.set('custom_config', props.customConfig)
    const resp = await fetch(`${LIVETALKING}/whep?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/sdp' },
      body: peer.localDescription?.sdp || '',
    })

    if (!resp.ok) throw new Error(`LiveTalking 信令失败（${resp.status}）`)

    const answerSdp = await resp.text()
    sessionId.value = resp.headers.get('X-Session-ID') || ''
    await peer.setRemoteDescription({ type: 'answer', sdp: answerSdp })

    await Promise.race([
      trackReady,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('等待视频流超时')), 20000),
      ),
    ])

    if (video.value && stream) {
      video.value.srcObject = stream
      await startPlayback(video.value)
    }
    drawRaf = requestAnimationFrame(drawFrame)

    loading.value = false
    emit('ready', sessionId.value)
  } catch (e: any) {
    if (destroyed) return
    error.value = e?.message || '数字人连接失败'
    loading.value = false
    emit('error', error.value)
    cleanup()
  }
}

/** 让数字人说话；返回这段语音的时长（秒），供上层按说话速度逐字显示。 */
async function speak(text: string): Promise<number> {
  if (!text.trim() || !sessionId.value) return 0

  try {
    emit('speaking', true)
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
    }
    const resp = await fetch('/api/v1/avatar/livetalking-talk', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        sessionid: sessionId.value,
        text: text.trim(),
        voice: props.voiceId || undefined,
        voice_style: props.voiceStyle || undefined,
        voice_desc: props.voiceDesc || undefined,
      }),
    })

    if (!resp.ok) {
      const detail = await resp.text().catch(() => '')
      throw new Error(detail || `驱动数字人失败（${resp.status}）`)
    }
    const data = await resp.json().catch(() => null)
    startSpeakPoll()
    return Number(data?.duration) || 0
  } catch (e: any) {
    emit('error', e?.message || '驱动数字人失败')
    emit('speaking', false)
    return 0
  }
}

function cleanup() {
  stopSpeakPoll()
  detachResumeAudio?.()
  // 离开页面时主动通知服务端释放会话，避免会话残留占满上限
  const sid = sessionId.value
  if (sid) {
    fetch(`${LIVETALKING}/api/session/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionid: sid }),
      keepalive: true,
    }).catch(() => {})
    sessionId.value = ''
  }
  if (drawRaf) {
    cancelAnimationFrame(drawRaf)
    drawRaf = 0
  }
  if (pc) {
    pc.close()
    pc = null
  }
  if (stream) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
  if (video.value) video.value.srcObject = null
}

onMounted(connect)
onBeforeUnmount(() => {
  destroyed = true
  cleanup()
})

defineExpose({ speak, sessionId, loading, error })
</script>

<template>
  <div class="lta">
    <canvas ref="canvas" class="lta__canvas" :style="{ '--lta-zoom': zoomScale }" />
    <video
      ref="video"
      class="lta__video"
      autoplay
      playsinline
      disablepictureinpicture
      controlslist="nodownload noplaybackrate noremoteplayback"
    />
    <div v-if="loading" class="lta__hint">数字人连接中…</div>
    <div v-if="error" class="lta__hint lta__hint--error">{{ error }}</div>
  </div>
</template>

<style scoped>
.lta {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 22px;
  background: transparent;
}

.lta__canvas {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  height: 100%;
  /* 铺满整张卡片：卡片已按 480:854 比例，cover 只在窄窗口裁掉两侧绿幕，不会切到人物 */
  object-fit: cover;
  object-position: center center;
  /* 等比放大（默认 1 = 原样）：基准点取「横向居中 + 纵向 25%」，
     放大时优先保住头顶留白（原片取景偏松的人物也够放大余量），
     两侧不裁人物，收紧的主要是画面下缘 */
  transform: scale(var(--lta-zoom, 1));
  transform-origin: center 25%;
}

/* video 只作为解码与音频来源，缩到不可见且不接收鼠标事件，
   避免浏览器悬停时弹出「画中画 / 增强 / 翻译音频」等原生控件 */
.lta__video {
  position: absolute;
  left: 0;
  top: 0;
  width: 2px;
  height: 2px;
  opacity: 0.01;
  pointer-events: none;
}

.lta__hint {
  position: absolute;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  padding: 6px 13px;
  border-radius: 999px;
  background: rgba(16, 19, 27, 0.7);
  color: rgba(255, 244, 222, 0.92);
  font-size: 12px;
  white-space: nowrap;
}

.lta__hint--error {
  color: #ffd9d4;
}
</style>
