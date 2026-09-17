<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  figureId: string
  imageUrl: string | null
  voiceId?: string | null
  voiceStyle?: string | null
  voiceDesc?: string | null
}>()

const emit = defineEmits<{
  ready: [url: string]
  ended: []
  error: [message: string]
}>()

const auth = useAuthStore()
const videoUrl = ref<string | null>(null)
const loading = ref(false)
const error = ref('')
const mainVideo = ref<HTMLVideoElement | null>(null)
const pipVideo = ref<HTMLVideoElement | null>(null)
let objectUrl: string | null = null
let audioUrl: string | null = null
let audio: HTMLAudioElement | null = null
let finished = false

function syncPip() {
  if (!mainVideo.value || !pipVideo.value) return
  const diff = Math.abs(pipVideo.value.currentTime - mainVideo.value.currentTime)
  if (diff > 0.12) pipVideo.value.currentTime = mainVideo.value.currentTime
}

function clearResources() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = null
  }
  if (audioUrl) {
    URL.revokeObjectURL(audioUrl)
    audioUrl = null
  }
  if (audio) {
    audio.pause()
    audio.src = ''
    audio = null
  }
  videoUrl.value = null
}

async function speak(text: string) {
  if (!text.trim() || loading.value) return
  stop()
  error.value = ''
  loading.value = true
  finished = false

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
    }
    const body = JSON.stringify({
      text: text.trim(),
      voice: props.voiceId || undefined,
      voice_style: props.voiceStyle || undefined,
      voice_desc: props.voiceDesc || undefined,
    })

    const [videoResp, audioResp] = await Promise.all([
      fetch(`/api/v1/avatar/talk?figure_id=${encodeURIComponent(props.figureId)}`, {
        method: 'POST',
        headers,
        body,
      }),
      fetch('/api/v1/voice/tts', {
        method: 'POST',
        headers,
        body,
      }),
    ])

    if (!videoResp.ok) {
      const detail = await videoResp.text().catch(() => '')
      throw new Error(detail || `生成讲学视频失败（${videoResp.status}）`)
    }
    if (!audioResp.ok) {
      const detail = await audioResp.text().catch(() => '')
      throw new Error(detail || `生成语音失败（${audioResp.status}）`)
    }

    const [videoBlob, audioBlob] = await Promise.all([videoResp.blob(), audioResp.blob()])
    objectUrl = URL.createObjectURL(videoBlob)
    videoUrl.value = objectUrl

    audioUrl = URL.createObjectURL(audioBlob)
    audio = new Audio(audioUrl)
    audio.onended = () => {
      if (!finished) {
        finished = true
        emit('ended')
        clearResources()
      }
    }
    audio.play().catch(() => {
      if (!finished) {
        finished = true
        emit('ended')
        clearResources()
      }
    })

    loading.value = false
    emit('ready', objectUrl)
  } catch (e: any) {
    const message = e?.message || '生成失败'
    error.value = message
    loading.value = false
    clearResources()
    emit('error', message)
  }
}

function onVideoEnded() {
  if (!finished) {
    finished = true
    emit('ended')
    clearResources()
  }
}

function onVideoError() {
  const message = '视频播放失败'
  error.value = message
  loading.value = false
  clearResources()
  emit('error', message)
}

function stop() {
  finished = true
  loading.value = false
  clearResources()
}

onBeforeUnmount(stop)

defineExpose({ speak, stop, loading, error })
</script>

<template>
  <div class="tp">
    <div v-if="imageUrl && !videoUrl" class="tp__idle">
      <span class="tp__halo" aria-hidden="true" />
      <img :src="imageUrl" alt="历史人物立绘" class="tp__img tp__img--idle" />
      <span class="tp__scan" aria-hidden="true" />
      <span class="tp__status">{{ loading ? '数字人准备中…' : '先生待命' }}</span>
    </div>
    <video
      v-if="videoUrl"
      ref="mainVideo"
      :src="videoUrl"
      autoplay
      muted
      playsinline
      class="tp__video"
      @loadedmetadata="syncPip"
      @timeupdate="syncPip"
      @ended="onVideoEnded"
      @error="onVideoError"
    />
    <video
      v-if="videoUrl"
      ref="pipVideo"
      :src="videoUrl"
      autoplay
      muted
      playsinline
      class="tp__pip"
      aria-hidden="true"
    />
    <div v-if="error" class="tp__error">{{ error }}</div>
  </div>
</template>

<style scoped>
.tp {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 22px;
  background: transparent;
}

.tp__idle {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tp__img,
.tp__video {
  position: relative;
  z-index: 1;
  width: auto;
  height: 100%;
  max-width: 100%;
  object-fit: contain;
  filter: drop-shadow(0 18px 28px rgba(0, 0, 0, 0.42));
}

.tp__img--idle {
  animation: tp-breathe 3.4s ease-in-out infinite;
}

.tp__halo {
  position: absolute;
  left: 50%;
  top: 48%;
  width: min(78%, 340px);
  aspect-ratio: 1;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(255, 214, 150, 0.42) 0%,
    rgba(255, 214, 150, 0.12) 40%,
    transparent 70%
  );
  filter: blur(18px);
  animation: tp-glow 2.8s ease-in-out infinite;
  pointer-events: none;
}

.tp__scan {
  position: absolute;
  inset: 0;
  z-index: 2;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(255, 255, 255, 0.16) 48%,
    rgba(160, 226, 255, 0.22) 50%,
    rgba(255, 255, 255, 0.16) 52%,
    transparent 100%
  );
  opacity: 0.22;
  mix-blend-mode: screen;
  animation: tp-scan 2.6s linear infinite;
  pointer-events: none;
}

.tp__status {
  position: absolute;
  z-index: 3;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  padding: 6px 13px;
  border-radius: 999px;
  background: rgba(16, 19, 27, 0.68);
  color: rgba(255, 244, 222, 0.92);
  font-size: 12px;
  letter-spacing: 0.08em;
  white-space: nowrap;
  backdrop-filter: blur(8px);
}

.tp__pip {
  position: absolute;
  z-index: 3;
  right: 12px;
  top: 12px;
  width: min(128px, 26%);
  aspect-ratio: 1;
  object-fit: cover;
  object-position: 50% 23%;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.72);
  background: #111;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
  pointer-events: none;
}

.tp__error {
  position: absolute;
  z-index: 2;
  left: 50%;
  bottom: 14px;
  transform: translateX(-50%);
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(18, 22, 30, 0.72);
  color: #ffd9d4;
  font-size: 12px;
  white-space: nowrap;
}

@keyframes tp-breathe {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  50% {
    transform: translateY(-5px) scale(1.018);
  }
}

@keyframes tp-glow {
  0%,
  100% {
    opacity: 0.55;
    transform: translate(-50%, -50%) scale(0.92);
  }
  50% {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1.08);
  }
}

@keyframes tp-scan {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(100%);
  }
}
</style>
