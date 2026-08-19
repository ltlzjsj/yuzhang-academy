<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { listFigures, type HistoricalFigure } from '@/api/figures'
import DigitalHuman3D from '@/components/agent/DigitalHuman3D.vue'
import { transcribe } from '@/api/voice'
import { streamSSE } from '@/api/sse'
import { useAuthStore } from '@/stores/auth'
import { useVoiceRecorder } from '@/composables/useVoiceRecorder'
import { useSpeechPlayback } from '@/composables/useSpeechPlayback'
import { renderMarkdown } from '@/utils/markdown'

type HiddenMessage = { role: 'user' | 'assistant'; content: string }

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const figures = ref<HistoricalFigure[]>([])
const loading = ref(true)
const draft = ref('')
const latestQuestion = ref('')
const latestAnswer = ref('')
const latestSources = ref(0)
const error = ref('')
const streaming = ref(false)
const hiddenHistory = ref<HiddenMessage[]>([])
const ASSET_V = 'v=9'
let abort: AbortController | null = null

// --- 语音对话 ---
// 录音识别 + 语音作答 + 立绘随声口型动画。
const VOICE_ENABLED = true
const recorder = useVoiceRecorder()
const speech = useSpeechPlayback(() => ({
  voice: fig.value?.voice_id || '白桦',
  voiceStyle: fig.value?.voice_style || undefined,
}))
const transcribing = ref(false)
const autoRead = ref(true) // 收到回答后自动朗读（先生开口说话）

async function toggleMic() {
  if (!auth.token) {
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  if (recorder.recording.value) {
    const blob = await recorder.stop()
    if (!blob) return
    transcribing.value = true
    try {
      const text = await transcribe(blob)
      if (text.trim()) {
        draft.value = text.trim()
        submit()
      }
    } catch (e: any) {
      error.value = e?.message || '语音识别失败，请重试。'
    } finally {
      transcribing.value = false
    }
  } else {
    speech.stop()
    await recorder.start()
  }
}

function speakAnswer() {
  if (latestAnswer.value.trim()) speech.speak(latestAnswer.value)
}

const fig = computed(() => figures.value.find((f) => f.id === route.params.id) ?? null)
const hasReply = computed(() => !!latestAnswer.value || streaming.value || !!error.value)

function withAssetVersion(url: string | null): string | null {
  if (!url || !url.includes('/assets/academy/')) return url
  return `${url}${url.includes('?') ? '&' : '?'}${ASSET_V}`
}

function isPortrait(url: string | null): boolean {
  return !!url && url.includes('/assets/academy/') && url.split('?')[0].toLowerCase().endsWith('.png')
}

function portrait(url: string | null): string | null {
  if (!url || !url.includes('/assets/academy/')) return url
  if (isPortrait(url)) return withAssetVersion(url)
  return withAssetVersion(url.replace('/assets/academy/', '/assets/thumb/academy/') + '?w=720&h=960')
}

function trimHistory() {
  hiddenHistory.value = hiddenHistory.value.slice(-8)
}

function stop() {
  if (abort) {
    abort.abort()
    abort = null
  }
  streaming.value = false
}

function resetContext() {
  stop()
  speech.stop()
  recorder.cancel()
  hiddenHistory.value = []
  latestQuestion.value = ''
  latestAnswer.value = ''
  latestSources.value = 0
  error.value = ''
}

function pick(q: string) {
  draft.value = q
  submit()
}

function onEnter(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

function submit() {
  const content = draft.value.trim()
  if (!content || streaming.value || !fig.value) return
  if (!auth.token) {
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }

  stop()
  speech.reset()
  error.value = ''
  draft.value = ''
  latestQuestion.value = content
  latestAnswer.value = ''
  latestSources.value = 0
  streaming.value = true

  const outgoing: HiddenMessage[] = [...hiddenHistory.value, { role: 'user', content }]
  let finalAnswer = ''

  abort = streamSSE(
    '/api/v1/agent/stream',
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` },
      body: {
        messages: outgoing,
        system_prompt: `${fig.value.system_prompt}

界面说明：你正在以历史人物身份面对来访者当场答问。前文对话会作为记忆传入，但页面只展示你对当前问题的回答。请自然承接上下文，不要复述全部历史，不要说自己是 AI。`,
        kb_ids: [],
        rag_enabled: false,
      },
    },
    {
      onEvent: (event, data) => {
        if (event === 'citations') {
          latestSources.value = (data.items ?? []).length
        } else if (event === 'delta') {
          const text = data.content ?? ''
          latestAnswer.value += text
          finalAnswer += text
          if (VOICE_ENABLED && autoRead.value) speech.feed(text) // 边生成边按句合成播放
        } else if (event === 'error') {
          error.value = data.message || '先生暂时无言，请稍后再问。'
        } else if (event === 'done') {
          streaming.value = false
          abort = null
          if (VOICE_ENABLED && autoRead.value) speech.finish()
          if (finalAnswer.trim()) {
            hiddenHistory.value = [...outgoing, { role: 'assistant', content: finalAnswer.trim() }]
            trimHistory()
          }
        }
      },
      onError: (e) => {
        error.value = e.message || '先生暂时无言，请稍后再问。'
        streaming.value = false
        abort = null
      },
      onClose: () => {
        streaming.value = false
      },
    },
  )
}

onMounted(async () => {
  try {
    figures.value = await listFigures()
  } catch {
    figures.value = []
  } finally {
    loading.value = false
  }
})

watch([loading, fig], () => {
  if (!loading.value && !fig.value) router.replace('/figures')
})

watch(
  () => route.params.id,
  () => {
    resetContext()
  },
)

onBeforeUnmount(stop)
</script>

<template>
  <div v-if="fig" class="fc" :style="{ '--ac': fig.accent }">
    <RouterLink to="/figures" class="fc__back">← 历代名人</RouterLink>
    <button class="fc__reset" :disabled="!hiddenHistory.length && !hasReply" @click="resetContext">重新请教</button>

    <section class="fc__stage">
      <div class="fc__left">
        <div
          class="fc__figure fc__figure--3d"
          :class="{ 'is-speaking': speech.speaking.value }"
          :style="{ '--talk': speech.level.value }"
        >
          <span class="fc__glow" />
          <DigitalHuman3D
            :key="fig.id"
            :src="`/models/${fig.id}.glb`"
            :level="speech.level.value"
            :speaking="speech.speaking.value"
          />
        </div>

        <aside class="fc__meta">
          <p class="fc__dyn">{{ fig.dynasty }} · {{ fig.academy }}</p>
          <h1 class="h-serif">{{ fig.name }}</h1>
          <p class="fc__title">{{ fig.title }}</p>
          <blockquote v-if="fig.quote" class="fc__quote h-serif">“{{ fig.quote }}”</blockquote>
        </aside>
      </div>

      <div class="fc__bubble" :class="{ 'is-empty': !hasReply }">
        <template v-if="hasReply">
          <p v-if="latestQuestion" class="fc__asked">你问：{{ latestQuestion }}</p>
          <div v-if="latestAnswer" class="fc__answer md-body" v-html="renderMarkdown(latestAnswer)" />
          <div v-else-if="streaming" class="fc__thinking">
            <i /><i /><i />
            <span>先生正在思量...</span>
          </div>
          <p v-if="error" class="fc__error">{{ error }}</p>
          <p v-if="latestSources" class="fc__sources">引用 {{ latestSources }} 条书院资料</p>
        </template>
        <template v-else>
          <p class="fc__emptyTitle h-serif">请先生开示</p>
          <p class="fc__emptyText">可从下方择一题发问，也可自行向先生请教。</p>
        </template>
      </div>
    </section>

    <footer class="fc__dock">
      <div v-if="fig.suggestions?.length" class="fc__chips">
        <button v-for="q in fig.suggestions" :key="q" :disabled="streaming" @click="pick(q)">{{ q }}</button>
      </div>
      <div class="fc__composer">
        <button
          v-if="VOICE_ENABLED"
          class="fc__mic"
          :class="{ 'is-rec': recorder.recording.value }"
          :disabled="transcribing || streaming"
          :title="recorder.recording.value ? '点击结束并识别' : '按住说话'"
          @click="toggleMic"
        >
          <span v-if="transcribing">识别中…</span>
          <span v-else-if="recorder.recording.value">● 录音中</span>
          <span v-else>🎤</span>
        </button>
        <textarea
          v-model="draft"
          rows="1"
          class="fc__input"
          :placeholder="`向${fig.name}先生请教...`"
          @keydown="onEnter"
        />
        <button v-if="streaming" class="fc__send fc__send--stop" @click="stop">停止</button>
        <button v-else class="fc__send" :disabled="!draft.trim()" @click="submit">请教</button>
      </div>
      <div v-if="VOICE_ENABLED" class="fc__voicebar">
        <label class="fc__toggle">
          <input v-model="autoRead" type="checkbox" />
          <span>语音作答</span>
        </label>
        <button
          v-if="latestAnswer && !speech.speaking.value"
          class="fc__readbtn"
          :disabled="speech.loading.value"
          @click="speakAnswer"
        >{{ speech.loading.value ? '合成中…' : '🔊 朗读回答' }}</button>
        <button v-else-if="speech.speaking.value" class="fc__readbtn" @click="speech.stop()">⏹ 停止朗读</button>
        <span v-if="recorder.error.value || speech.error.value" class="fc__verr">
          {{ recorder.error.value || speech.error.value }}
        </span>
      </div>
    </footer>
  </div>

  <div v-else-if="loading" class="fc__loading">正在恭请先生...</div>
</template>

<style scoped>
.fc {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(circle at 28% 28%, color-mix(in srgb, var(--ac) 44%, transparent), transparent 34%),
    radial-gradient(circle at 72% 16%, rgba(237, 183, 79, 0.16), transparent 32%),
    linear-gradient(150deg, #27313a 0%, var(--navy) 45%, var(--navy-deep) 100%);
}

.fc::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(0deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(to bottom, transparent, black 12%, black 82%, transparent);
  pointer-events: none;
}

.fc__back,
.fc__reset {
  position: absolute;
  top: 18px;
  z-index: 5;
  padding: 8px 15px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.13);
  color: #fff;
  font-size: 13.5px;
  font-weight: 700;
  text-decoration: none;
  backdrop-filter: blur(10px);
}

.fc__back { left: 20px; }
.fc__reset { right: 24px; }
.fc__reset:disabled { opacity: 0.42; cursor: default; }
.fc__back:hover,
.fc__reset:not(:disabled):hover { background: rgba(255, 255, 255, 0.24); }

.fc__stage {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  grid-template-columns: minmax(320px, 0.98fr) minmax(320px, 1.02fr);
  align-items: center;
  gap: clamp(18px, 3vw, 56px);
  padding: clamp(20px, 4vh, 58px) clamp(24px, 5vw, 86px) clamp(14px, 2vh, 28px);
}

.fc__left {
  position: relative;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(6px, 1.4vh, 18px);
}

.fc__figure {
  position: relative;
  min-height: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
/* 3D 数字人舞台：给画布一个确定尺寸 */
.fc__figure--3d {
  width: min(460px, 86vw);
  height: min(60vh, 640px);
}

.fc__glow {
  position: absolute;
  bottom: 18%;
  width: min(82%, 430px);
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.32), rgba(237, 183, 79, 0.16) 42%, transparent 70%);
  filter: blur(10px);
  transition: opacity 0.1s linear, transform 0.1s linear;
}
/* 说话时光晕随声脉动 */
.fc__figure.is-speaking .fc__glow {
  opacity: calc(0.7 + var(--talk, 0) * 0.5);
  transform: scale(calc(1 + var(--talk, 0) * 0.06));
}

.fc__figure img {
  position: relative;
  z-index: 1;
  max-height: min(62vh, 760px);
  max-width: min(108%, 600px);
  object-fit: contain;
  /* 基础放大 1.08，叠加随声"说话"动作：上抬 + 轻微缩放 + 极小摆动（拟态开口） */
  transform:
    translateY(calc(var(--talk, 0) * -7px))
    scale(calc(1.08 + var(--talk, 0) * 0.022))
    rotate(calc(var(--talk, 0) * 0.5deg));
  transform-origin: bottom center;
  transition: transform 0.07s linear;
  filter:
    drop-shadow(1.5px 0 0 rgba(255, 255, 255, 0.92))
    drop-shadow(-1.5px 0 0 rgba(255, 255, 255, 0.92))
    drop-shadow(0 1.5px 0 rgba(255, 255, 255, 0.88))
    drop-shadow(0 -1.5px 0 rgba(255, 255, 255, 0.88))
    drop-shadow(0 24px 30px rgba(0, 0, 0, 0.48));
}

.fc__seal {
  display: grid;
  place-items: center;
  height: 220px;
  width: 220px;
  border-radius: 24px;
  background: color-mix(in srgb, var(--ac) 40%, var(--navy-deep));
  color: var(--gold-soft);
  font-size: 110px;
  font-weight: 800;
}

.fc__meta {
  position: relative;
  width: min(420px, 92%);
  text-align: center;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.42);
}

.fc__dyn {
  color: var(--gold);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.fc__meta h1 {
  margin: 7px 0 4px;
  font-size: clamp(32px, 4vw, 52px);
  font-weight: 800;
}

.fc__title { color: rgba(255, 255, 255, 0.82); font-size: 15px; }
.fc__quote {
  margin: 16px auto 0;
  color: var(--gold-soft);
  font-size: 16px;
  line-height: 1.7;
}

.fc__bubble {
  position: relative;
  align-self: center;
  justify-self: start;
  width: min(720px, 100%);
  min-height: 0;
  max-height: min(62vh, 590px);
  overflow-y: auto;
  padding: clamp(20px, 2.7vw, 34px) clamp(24px, 3.2vw, 42px);
  border-radius: 22px;
  border: 1.5px solid rgba(23, 34, 48, 0.72);
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(251, 246, 237, 0.95));
  color: var(--ink);
  box-shadow:
    0 7px 0 rgba(23, 34, 48, 0.86),
    0 24px 48px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.88);
}

.fc__bubble::before {
  content: "";
  position: absolute;
  left: -38px;
  top: 42%;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 1.5px solid rgba(23, 34, 48, 0.56);
  background: rgba(255, 253, 248, 0.96);
  box-shadow:
    -22px 17px 0 -4px rgba(255, 253, 248, 0.96),
    -22px 17px 0 -2.5px rgba(23, 34, 48, 0.5),
    -42px 31px 0 -6px rgba(255, 253, 248, 0.92),
    -42px 31px 0 -4.8px rgba(23, 34, 48, 0.42);
}

.fc__bubble::after {
  content: "";
  position: absolute;
  inset: 9px;
  border-radius: 16px;
  border: 1px solid rgba(138, 90, 43, 0.08);
  pointer-events: none;
}

.fc__bubble.is-empty {
  display: grid;
  place-content: center;
  text-align: center;
  width: min(560px, 100%);
  min-height: 116px;
}

.fc__asked {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
  color: var(--muted);
  font-size: 13px;
}

.fc__answer {
  font-size: 16px;
  line-height: 2;
}

.fc__thinking {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--sub);
}

.fc__thinking i {
  height: 8px;
  width: 8px;
  border-radius: 50%;
  background: var(--ac);
  animation: blink 1.2s infinite ease-in-out;
}

.fc__thinking i:nth-child(2) { animation-delay: 0.2s; }
.fc__thinking i:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }

.fc__error { color: var(--red); }
.fc__sources { margin-top: 14px; color: var(--muted); font-size: 12px; }
.fc__emptyTitle { margin-bottom: 8px; color: var(--ac); font-size: 30px; font-weight: 800; }
.fc__bubble.is-empty .fc__emptyTitle { color: var(--ac); }
.fc__emptyText { max-width: 440px; color: var(--sub); line-height: 1.8; }

.fc__dock {
  position: relative;
  z-index: 4;
  flex: none;
  width: min(960px, calc(100% - 42px));
  margin: 0 auto;
  padding: 10px 0 16px;
}

.fc__chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-bottom: 10px;
}

.fc__chips button {
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.9);
  color: var(--sub);
  font-size: 12.5px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.fc__chips button:hover:not(:disabled) { color: var(--ac); transform: translateY(-1px); }
.fc__chips button:disabled { opacity: 0.5; }

.fc__composer {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 20px 55px rgba(0, 0, 0, 0.24);
  backdrop-filter: blur(14px);
}

.fc__input {
  flex: 1;
  min-height: 44px;
  max-height: 132px;
  resize: none;
  padding: 12px 14px;
  border: 0;
  border-radius: 12px;
  background: rgba(245, 242, 236, 0.92);
  color: var(--ink);
  font-size: 15px;
  line-height: 1.5;
}

.fc__input:focus { outline: 2px solid color-mix(in srgb, var(--ac) 42%, transparent); }

.fc__send {
  flex: none;
  min-height: 44px;
  padding: 0 22px;
  border-radius: 12px;
  background: var(--ac);
  color: #fff;
  font-weight: 800;
}

.fc__send:disabled { opacity: 0.45; }
.fc__send--stop { background: var(--red); }
.fc__loading { display: grid; place-items: center; height: 100%; color: var(--muted); }

.fc__mic {
  flex: none;
  min-height: 44px;
  min-width: 56px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(245, 242, 236, 0.92);
  color: var(--sub);
  font-size: 15px;
  font-weight: 700;
}
.fc__mic:disabled { opacity: 0.5; }
.fc__mic.is-rec {
  background: var(--red);
  color: #fff;
  border-color: transparent;
  animation: micpulse 1.1s infinite;
}
@keyframes micpulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.45); } 50% { box-shadow: 0 0 0 7px rgba(231, 76, 60, 0); } }

.fc__voicebar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 8px;
  padding: 0 6px;
  color: rgba(255, 255, 255, 0.86);
  font-size: 12.5px;
}
.fc__toggle { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.fc__readbtn {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
}
.fc__readbtn:disabled { opacity: 0.55; }
.fc__verr { color: var(--gold-soft); }

/* 矮屏（小笔记本）：缩小立绘，保证人物完整 + 输入框可见 */
@media (max-height: 760px) {
  .fc__figure img { max-height: 48vh; transform: scale(1.04); }
  .fc__meta h1 { font-size: clamp(26px, 3.4vw, 38px); }
  .fc__quote { font-size: 14px; margin-top: 8px; }
}
@media (max-height: 600px) {
  .fc__figure img { max-height: 40vh; }
  .fc__quote { display: none; }
}

@media (max-width: 920px) {
  .fc__stage {
    grid-template-columns: 1fr;
    padding: 18px 16px 12px;
  }
  .fc__left { order: 1; }
  .fc__figure { min-height: 220px; }
  .fc__figure img { max-height: 280px; }
  .fc__meta { width: 100%; }
  .fc__bubble {
    order: 2;
    width: 100%;
    max-height: none;
  }
  .fc__bubble::before {
    left: 48%;
    top: -27px;
    border-left: 15px solid transparent;
    border-right: 15px solid transparent;
    border-bottom: 20px solid rgba(255, 255, 255, 0.96);
    border-top: 0;
  }
  .fc__dock { width: calc(100% - 24px); }
  .fc__chips { justify-content: flex-start; overflow-x: auto; flex-wrap: nowrap; padding-bottom: 2px; }
  .fc__chips button { white-space: nowrap; }
}
</style>
