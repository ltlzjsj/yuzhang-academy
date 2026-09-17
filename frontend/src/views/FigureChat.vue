<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { listFigures, type HistoricalFigure } from '@/api/figures'
import DigitalHuman3D from '@/components/agent/DigitalHuman3D.vue'
import XmovAvatar from '@/components/agent/XmovAvatar.vue'
import TalkingPortrait from '@/components/agent/TalkingPortrait.vue'
import LiveTalkingAvatar from '@/components/agent/LiveTalkingAvatar.vue'
import { transcribe } from '@/api/voice'
import { streamSSE } from '@/api/sse'
import { useAuthStore } from '@/stores/auth'
import { useVoiceRecorder } from '@/composables/useVoiceRecorder'
import { useSpeechPlayback } from '@/composables/useSpeechPlayback'
import { useAlignedSpeech } from '@/composables/useAlignedSpeech'
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
const portraitPreparing = ref(false)
const pendingPortraitAnswer = ref('')
const hiddenHistory = ref<HiddenMessage[]>([])
const ASSET_V = 'v=11'
let abort: AbortController | null = null

// --- 语音对话 ---
// 录音识别 + 语音作答 + 立绘随声口型动画。
const VOICE_ENABLED = true
const recorder = useVoiceRecorder()
const speech = useSpeechPlayback(() => ({
  voice: fig.value?.voice_id || '白桦',
  voiceStyle: fig.value?.voice_style || undefined,
  voiceDesc: fig.value?.voice_desc || undefined,
}))
const transcribing = ref(false)
const autoRead = ref(true) // 收到回答后自动朗读（先生开口说话）
const xmovRef = ref<{ speak: (text: string) => void; idle: () => void } | null>(null)
const digitalHumanRef = ref<{ setPhoneme: (weights: Record<string, number> | null) => void } | null>(null)
const talkingPortraitRef = ref<{ speak: (text: string) => void; stop: () => void } | null>(null)
const liveTalkingRef = ref<{ speak: (text: string) => Promise<number> } | null>(null)
// 影院字幕容器：文字增长时自动滚到最后一行
const cineLineRef = ref<HTMLElement | null>(null)
// 朱熹暂时改用“画像开口说话 + 点头呼吸”，与吕祖谦保持一致。
const useXmov = computed(() => false)
// LiveTalking 实时数字人（WebRTC 口型驱动）：全部历史人物统一走这条链路。
// 素材来自「数字人」目录的「说话动作 + 待机动作」两段视频：
//   data/avatars/<id>_lt        —— 说话视频逐帧导出（wav2lip 在上面改口型）
//   data/custom/<id>_idle       —— 待机视频逐帧导出（静音时循环播放）
// idle 通过 custom_config 在建立连接时传给 LiveTalking。
// zoom：画面等比放大倍数，按人物原片取景单独标定（见注释，目标是各人面部在卡片上
// 的占比接近，且放大后不切到头顶）。
const LIVE_TALKING_AVATARS: Record<string, { avatar: string; idle?: string; zoom?: number }> = {
  // 江万里：待机由服务启动参数 custom_jiangwanli.json 指定，这里不重复传
  jiangwanli: { avatar: 'jiangwanli_lt' },
  luocongyan: {
    avatar: 'luocongyan_lt',
    idle: JSON.stringify([{ audiotype: 1, imgpath: './data/custom/luocongyan_idle' }]),
    zoom: 1.18,
  },
  zhuxi: {
    avatar: 'zhuxi_lt',
    idle: JSON.stringify([{ audiotype: 1, imgpath: './data/custom/zhuxi_idle' }]),
    zoom: 1.13,
  },
  lvzuqian: {
    avatar: 'lvzuqian_lt',
    idle: JSON.stringify([{ audiotype: 1, imgpath: './data/custom/lvzuqian_idle' }]),
    zoom: 1.31,
  },
  // 陆九渊、王阳明原片为 4:3（480×640），头顶已贴近画面顶端，保持原样不放大
  luxiangshan: {
    avatar: 'luxiangshan_lt',
    idle: JSON.stringify([{ audiotype: 1, imgpath: './data/custom/luxiangshan_idle' }]),
  },
  wangyangming: {
    avatar: 'wangyangming_lt',
    idle: JSON.stringify([{ audiotype: 1, imgpath: './data/custom/wangyangming_idle' }]),
  },
}
const liveTalkingAvatar = computed(() => LIVE_TALKING_AVATARS[fig.value?.id ?? ''] ?? null)
const useLiveTalking = computed(() => !!liveTalkingAvatar.value)
// 画像开口说话（离线渲染成视频的旧路径）：朱熹、吕祖谦曾经用它。
// 现在这两位也已接入 LiveTalking 实时数字人，所以只有在没接 LiveTalking 时才回退到这条路径
// ——否则下面的分支会先命中旧路径，导致答完后不驱动数字人、字幕一直停在「正在思量」。
const useTalkingPortrait = computed(
  () => ['zhuxi', 'lvzuqian'].includes(fig.value?.id ?? '') && !useLiveTalking.value,
)
const isSpeaking = computed(() => (useXmov.value ? speech.speaking.value : aligned.speaking.value))

// 自研数字人的音素驱动语音：播放时把口型权重喂给 DigitalHuman3D
const aligned = useAlignedSpeech((weights) => {
  digitalHumanRef.value?.setPhoneme(weights)
})

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
    aligned.stop()
    xmovRef.value?.idle()
    await recorder.start()
  }
}

function speakAnswer() {
  if (!latestAnswer.value.trim()) return
  if (useXmov.value) xmovRef.value?.speak(latestAnswer.value)
  else if (useLiveTalking.value) liveTalkingRef.value?.speak(latestAnswer.value)
  else if (useTalkingPortrait.value) talkingPortraitRef.value?.speak(latestAnswer.value)
  else aligned.speak(latestAnswer.value, { voiceDesc: fig.value?.voice_desc || undefined })
}

function onPortraitReady() {
  if (pendingPortraitAnswer.value) {
    latestAnswer.value = pendingPortraitAnswer.value
  }
  portraitPreparing.value = false
}

let revealRaf = 0
// 字幕是否正在逐字增长（用于显示光标）
const revealing = ref(false)
// 讲完之后收起字幕的定时器
let subtitleClearTimer: number | undefined

// ---- 逐句流式播报：LLM 吐出一句就立刻合成并驱动数字人，不必等全文 ----
const SPEAK_MIN_CHARS = 8 // 太短的片段（“好，”）并入下一句一起播，避免碎句
const speakQueue: string[] = []
const revealItems: { text: string; duration: number }[] = []
let audioPumpRunning = false
let revealPumpRunning = false
let rawBuf = '' // 已收到但尚未成句的残余文本
let spokenPrefix = '' // 已经念完、字幕已完整显示的部分

/** 从缓冲区切出已完整的句子（保留句末标点），返回句子列表与残余。 */
function takeSentences(buf: string): { sentences: string[]; rest: string } {
  const sentences: string[] = []
  let start = 0
  for (let i = 0; i < buf.length; i++) {
    const ch = buf[i]
    if (!('。！？!?；;'.includes(ch) || ch === '\n')) continue
    const s = buf.slice(start, i + 1).trim()
    if (!s) {
      start = i + 1
      continue
    }
    // 过短的片段不单独成一“句”，留在缓冲里与下一段合并
    if (s.length < SPEAK_MIN_CHARS) continue
    sentences.push(s)
    start = i + 1
  }
  return { sentences, rest: buf.slice(start) }
}

/** 把流式增量喂进句子队列，凑成一句就推给数字人。 */
function feedAnswerDelta(text: string) {
  rawBuf += text
  const { sentences, rest } = takeSentences(rawBuf)
  rawBuf = rest
  for (const s of sentences) if (s) speakQueue.push(s)
  void pumpAudio()
}

/**
 * 音频管线：句子一到就立刻合成并推给数字人（不等上一句播完），
 * 这样 LiveTalking 的音频队列里始终有下一句，句与句之间不会出现空档。
 */
async function pumpAudio() {
  if (audioPumpRunning) return
  audioPumpRunning = true
  try {
    while (speakQueue.length) {
      const sentence = speakQueue.shift()!
      let duration = 0
      if (useLiveTalking.value) {
        duration = Number(await Promise.resolve(liveTalkingRef.value?.speak(sentence))) || 0
      } else if (useXmov.value) {
        xmovRef.value?.speak(sentence)
      } else {
        aligned.enqueue(sentence, { voiceDesc: fig.value?.voice_desc || undefined })
      }
      if (!useLiveTalking.value) portraitPreparing.value = false
      revealItems.push({ text: sentence, duration })
      void pumpReveal()
    }
  } finally {
    audioPumpRunning = false
  }
}

/** 字幕管线：LiveTalking 路径按每句语音时长逐字浮现；其他链路字幕随流式文本显示。 */
async function pumpReveal() {
  if (revealPumpRunning) return
  revealPumpRunning = true
  try {
    while (revealItems.length) {
      const item = revealItems.shift()!
      if (useLiveTalking.value) await revealAppend(item.text, item.duration)
    }
  } finally {
    revealPumpRunning = false
  }
}
/** 逐句浮现字幕：把这一句按语音时长铺开，接在已念完的部分后面。 */
function revealAppend(text: string, durationSec: number): Promise<void> {
  return new Promise((resolve) => {
    const chars = Array.from(text)
    if (!chars.length) {
      resolve()
      return
    }
    const base = spokenPrefix
    const leadMs = 150
    const speechMs = durationSec > 0 ? durationSec * 1000 : chars.length * 180
    const start = performance.now()
    portraitPreparing.value = false
    revealing.value = true
    const tick = () => {
      const elapsed = performance.now() - start
      const ratio = Math.min(1, Math.max(0, (elapsed - leadMs) / Math.max(1, speechMs)))
      const shown = Math.max(1, Math.round(chars.length * ratio))
      latestAnswer.value = base + chars.slice(0, shown).join('')
      if (ratio < 1) {
        revealRaf = requestAnimationFrame(tick)
      } else {
        revealRaf = 0
        revealing.value = false
        spokenPrefix = base + text
        latestAnswer.value = spokenPrefix
        resolve()
      }
    }
    revealRaf = requestAnimationFrame(tick)
  })
}

function cancelSubtitleClear() {
  if (subtitleClearTimer !== undefined) {
    clearTimeout(subtitleClearTimer)
    subtitleClearTimer = undefined
  }
}

/** 数字人讲完再收字幕：还在逐字显示时不收，讲完停顿 1 秒后收起。 */
function maybeScheduleSubtitleClear() {
  if (revealing.value || !latestAnswer.value) return
  cancelSubtitleClear()
  subtitleClearTimer = window.setTimeout(() => {
    subtitleClearTimer = undefined
    if (revealing.value) return
    latestAnswer.value = ''
  }, 1000)
}

/** LiveTalking 播报状态：开始说话先取消收字幕，讲完安排收起。 */
function onPortraitSpeaking(active: boolean) {
  if (active) {
    cancelSubtitleClear()
    return
  }
  maybeScheduleSubtitleClear()
}

function stopReveal() {
  if (revealRaf) {
    cancelAnimationFrame(revealRaf)
    revealRaf = 0
  }
  revealing.value = false
}

/**
 * 跟着数字人说话的速度逐字显示回答：按这段语音的时长匀速推进，
 * 说到哪个字就出现哪个字，避免文字一次性全部砸出来。
 */
function revealBySpeech(text: string, durationSec: number) {
  stopReveal()
  const chars = Array.from(text)
  if (!chars.length) {
    latestAnswer.value = ''
    portraitPreparing.value = false
    return
  }
  const leadMs = 600 // 数字人起播缓冲，这段时间仍显示“先生正在思量”
  const speechMs = durationSec > 0 ? durationSec * 1000 : chars.length * 190
  const start = performance.now()
  latestAnswer.value = ''
  revealing.value = true
  const tick = () => {
    const elapsed = performance.now() - start
    if (elapsed < leadMs) {
      revealRaf = requestAnimationFrame(tick)
      return
    }
    portraitPreparing.value = false
    const ratio = Math.min(1, (elapsed - leadMs) / Math.max(1, speechMs))
    const shown = Math.max(1, Math.round(chars.length * ratio))
    latestAnswer.value = chars.slice(0, shown).join('')
    revealRaf = ratio < 1 ? requestAnimationFrame(tick) : 0
    if (ratio >= 1) {
      revealing.value = false
      // 兜底：若播报状态已结束，这里也会把字幕收掉
      maybeScheduleSubtitleClear()
    }
  }
  revealRaf = requestAnimationFrame(tick)
}

function onPortraitEnded() {
  portraitPreparing.value = false
}

// 回答较长时字幕会超出一屏，跟着逐字显示自动滚到底
watch(
  latestAnswer,
  () => {
    const el = cineLineRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
  { flush: 'post' },
)

function onPortraitError(message: string) {
  error.value = message
  portraitPreparing.value = false
}

const fig = computed(() => figures.value.find((f) => f.id === route.params.id) ?? null)
// v2 界面（书院讲堂风 · 数字人为主）：江万里、罗从彦，其他人物保持原样。
const isJiangwanli = computed(() => !!liveTalkingAvatar.value)
const hasReply = computed(() => !!latestAnswer.value || streaming.value || portraitPreparing.value || !!error.value)

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
  stopReveal()
  cancelSubtitleClear()
  speakQueue.length = 0
  rawBuf = ''
  revealItems.length = 0
  revealing.value = false
  if (abort) {
    abort.abort()
    abort = null
  }
  streaming.value = false
}

function resetContext() {
  stop()
  speech.stop()
  aligned.stop()
  xmovRef.value?.idle()
  talkingPortraitRef.value?.stop()
  recorder.cancel()
  hiddenHistory.value = []
  latestQuestion.value = ''
  latestAnswer.value = ''
  pendingPortraitAnswer.value = ''
  portraitPreparing.value = false
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
  pendingPortraitAnswer.value = ''
  portraitPreparing.value = false
  latestSources.value = 0
  streaming.value = true
  // 重置逐句播报状态
  speakQueue.length = 0
  rawBuf = ''
  spokenPrefix = ''
  revealItems.length = 0

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

界面说明：你正在以历史人物身份面对来访者当场答问。前文对话会作为记忆传入，但页面只展示你对当前问题的回答。请自然承接上下文，不要复述全部历史，不要说自己是 AI。
【本次答问的说话方式 · 必须遵守】
1. 短：全文 40~70 字，最多 80 字，2~3 句说完，宁可少说不可多说。
2. 先接后答：第一句用十来字接住对方的话，可调侃、可自嘲、可感叹，如“你这一问倒是有趣”“嚯，问到要害了”“好，老夫捡要紧的说”。
3. 之后一到两句只讲最要紧的一点，一句一个意思；不铺背景、不堆典故。
4. 不复述对方的问题，不用“首先/其次/综上所述”这类套话，不分点、不成篇。
5. 语言用宋明语录体的白话，半文半白、接近口语，像《朱子语类》《传习录》那样随口讲学；不生僻、不堆砌之乎者也。
6. 讲完可用半句把话头递回去，如“还想问什么，尽管说”。
7. 绝不写动作、神态、语气提示，不出现括号（如：（笑）（顿了顿）之类）；只写你要说出口的话，不要暴露你是 AI。`,
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
          finalAnswer += text
          if (useTalkingPortrait.value) {
            // 画像开口说话要整段渲染视频，先攒文本，done 时统一处理
            pendingPortraitAnswer.value += text
          } else if (useLiveTalking.value) {
            // 实时数字人：攒文本用于兜底，同时逐句推给它播报
            pendingPortraitAnswer.value += text
            if (VOICE_ENABLED && autoRead.value) {
              portraitPreparing.value = true
              feedAnswerDelta(text)
            }
          } else {
            latestAnswer.value += text
            if (VOICE_ENABLED && autoRead.value) feedAnswerDelta(text)
          }
        } else if (event === 'error') {
          error.value = data.message || '先生暂时无言，请稍后再问。'
        } else if (event === 'done') {
          streaming.value = false
          abort = null
          if (finalAnswer.trim()) {
            const tail = rawBuf.trim()
            rawBuf = ''
            // 逐句流式：句子已在生成过程中边出边播，这里只补最后一句没有句号的残余
            const streamingVoice = VOICE_ENABLED && autoRead.value && !useTalkingPortrait.value
            if (streamingVoice) {
              if (tail) speakQueue.push(tail)
              void pumpAudio()
              if (useLiveTalking.value) {
                // 兜底：万一没能播出（例如会话未就绪），直接把全文显示出来
                window.setTimeout(() => {
                  if (!latestAnswer.value && !audioPumpRunning && !speakQueue.length) {
                    latestAnswer.value = finalAnswer.trim()
                    portraitPreparing.value = false
                  }
                }, 1500)
              }
            } else if (useTalkingPortrait.value) {
              // 画像开口说话：整段生成视频后播放
              pendingPortraitAnswer.value = finalAnswer.trim()
              if (VOICE_ENABLED && autoRead.value) {
                portraitPreparing.value = true
                talkingPortraitRef.value?.speak(finalAnswer)
              } else {
                latestAnswer.value = finalAnswer.trim()
              }
            } else {
              latestAnswer.value = finalAnswer.trim()
            }
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
  <div v-if="fig" class="fc" :class="{ 'fc--v2': isJiangwanli }" :style="{ '--ac': fig.accent }">
    <RouterLink to="/figures" class="fc__back">← 历代名人</RouterLink>
    <button class="fc__reset" :disabled="!hiddenHistory.length && !hasReply" @click="resetContext">重新请教</button>

    <!-- 江万里 / 罗从彦：以数字人为主的电影字幕式布局 -->
    <section v-if="isJiangwanli" class="fc__cinema">
      <aside class="fc__cineInfo">
        <p class="fc__dyn">{{ fig.dynasty }} · {{ fig.academy }}</p>
        <h1 class="h-serif">{{ fig.name }}</h1>
        <p class="fc__title">{{ fig.title }}</p>
        <blockquote v-if="fig.quote" class="fc__quote h-serif">“{{ fig.quote }}”</blockquote>
        <p class="fc__bio">{{ fig.bio }}</p>

        <!-- 固定问题挪到左侧人物卡下方 -->
        <div v-if="fig.suggestions?.length" class="fc__cineAsk">
          <p class="fc__cineAskLbl">可以这样问</p>
          <button v-for="q in fig.suggestions" :key="q" :disabled="streaming" @click="pick(q)">
            {{ q }}
          </button>
        </div>
      </aside>

      <div class="fc__cineMain">
        <div class="fc__cineStage">
          <LiveTalkingAvatar
            ref="liveTalkingRef"
            :avatar-id="liveTalkingAvatar!.avatar"
            :custom-config="liveTalkingAvatar!.idle"
            :zoom="liveTalkingAvatar!.zoom ?? 1"
            :voice-id="fig.voice_id"
            :voice-style="fig.voice_style"
            :voice-desc="fig.voice_desc"
            @speaking="onPortraitSpeaking"
            @error="onPortraitError"
          />
        </div>

        <div class="fc__cineSubtitle">
          <p
            v-if="latestAnswer"
            ref="cineLineRef"
            class="fc__cineLine"
            :class="{ 'is-typing': revealing }"
          >
            {{ latestAnswer }}
          </p>
          <p v-else-if="streaming || portraitPreparing" class="fc__cineLine fc__cineLine--wait">
            先生正在思量…
          </p>
          <p v-else-if="error" class="fc__cineLine fc__cineLine--err">{{ error }}</p>
          <p v-else class="fc__cineLine fc__cineLine--idle">点左侧问题，或按住喇叭向先生请教</p>
        </div>

        <div class="fc__cineActions">
          <button
            v-if="VOICE_ENABLED"
            class="fc__micRound"
            :class="{ 'is-rec': recorder.recording.value }"
            :disabled="transcribing || streaming"
            :title="recorder.recording.value ? '点击结束并识别' : '按住说话'"
            @click="toggleMic"
          >
            <span v-if="transcribing" class="fc__micText">识别中…</span>
            <span v-else-if="recorder.recording.value" class="fc__micText">● 录音中</span>
            <span v-else class="fc__micIcon">🎤</span>
          </button>
        </div>
      </div>

      <div class="fc__cineSpacer" aria-hidden="true" />
    </section>

    <template v-else>
    <section class="fc__stage">
      <div class="fc__left">
        <div
          class="fc__figure fc__figure--3d"
          :class="{ 'is-speaking': speech.speaking.value }"
          :style="{ '--talk': speech.level.value }"
        >
          <span class="fc__glow" />
          <LiveTalkingAvatar
            v-if="useLiveTalking"
            ref="liveTalkingRef"
            :avatar-id="liveTalkingAvatar?.avatar || 'jiangwanli_lt'"
            :voice-id="fig.voice_id"
            :voice-style="fig.voice_style"
            :voice-desc="fig.voice_desc"
            @error="onPortraitError"
          />
          <TalkingPortrait
            v-else-if="useTalkingPortrait"
            ref="talkingPortraitRef"
            :figure-id="fig.id"
            :image-url="portrait(fig.image_url)"
            :voice-id="fig.voice_id"
            :voice-style="fig.voice_style"
            :voice-desc="fig.voice_desc"
            @ready="onPortraitReady"
            @ended="onPortraitEnded"
            @error="onPortraitError"
          />
          <XmovAvatar v-else-if="useXmov" ref="xmovRef" />
          <DigitalHuman3D
            v-else
            ref="digitalHumanRef"
            :key="fig.id"
            :src="fig.id === 'wangyangming' ? '/models/zhuxi_ue5.glb' : `/models/${fig.id}.glb`"
            :level="speech.level.value"
            :speaking="isSpeaking"
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
          <div v-else-if="portraitPreparing" class="fc__thinking">
            <i /><i /><i />
            <span>{{ useLiveTalking ? '先生正在思量…' : '先生正在准备讲学，请稍候…' }}</span>
          </div>
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
        <span v-if="isJiangwanli && hasReply" class="fc__wm" aria-hidden="true">豫章书院</span>
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
          v-if="latestAnswer && !aligned.speaking.value"
          class="fc__readbtn"
          :disabled="aligned.loading.value"
          @click="speakAnswer"
        >{{ aligned.loading.value ? '合成中…' : '🔊 朗读回答' }}</button>
        <button v-else-if="aligned.speaking.value" class="fc__readbtn" @click="aligned.stop()">⏹ 停止朗读</button>
        <span v-if="recorder.error.value || speech.error.value || aligned.error.value" class="fc__verr">
          {{ recorder.error.value || speech.error.value || aligned.error.value }}
        </span>
      </div>
    </footer>
    </template>
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

/* ============================================================
   江万里 · 书院讲堂界面（v2）
   仅在 .fc--v2 下生效，其他人物的界面保持原样。
   布局参考：左侧数字人舞台大卡 + 右侧信息卡/对话卡 + 底部操作卡，
   配色沿用系统令牌（藏青 + 描金 + 宣纸米白）。
   ============================================================ */
.fc--v2 {
  color: #ece5d8;
  background:
    radial-gradient(120% 78% at 12% -12%, rgba(198, 154, 75, 0.18), transparent 58%),
    radial-gradient(92% 70% at 100% 112%, rgba(40, 86, 78, 0.26), transparent 64%),
    linear-gradient(165deg, #17212b 0%, #111a22 52%, #0b1117 100%);
}
.fc--v2::before {
  background:
    radial-gradient(58% 40% at 16% 20%, rgba(198, 154, 75, 0.10), transparent 62%),
    radial-gradient(46% 34% at 84% 28%, rgba(56, 112, 98, 0.15), transparent 66%),
    radial-gradient(54% 40% at 62% 90%, rgba(126, 92, 48, 0.12), transparent 68%);
  mask-image: linear-gradient(to bottom, transparent, black 14%, black 80%, transparent);
}

/* 顶部返回 / 重新请教 */
.fc--v2 .fc__back,
.fc--v2 .fc__reset {
  border: 1px solid rgba(214, 178, 111, 0.30);
  background: rgba(255, 250, 240, 0.07);
  color: #ece5d8;
  box-shadow: none;
  backdrop-filter: blur(8px);
}
.fc--v2 .fc__back:hover,
.fc--v2 .fc__reset:not(:disabled):hover {
  background: rgba(214, 178, 111, 0.18);
  border-color: rgba(214, 178, 111, 0.52);
}
/* 顶部按钮对齐到内容网格，而不是贴浏览器边角 */
.fc--v2 .fc__back {
  left: max(20px, calc((100% - 1240px) / 2 + clamp(20px, 4vw, 56px)));
}
.fc--v2 .fc__reset {
  right: max(20px, calc((100% - 1240px) / 2 + clamp(20px, 4vw, 56px)));
}

/* 两栏：左舞台 / 右信息 + 对话 */
.fc--v2 .fc__stage {
  width: 100%;
  max-width: 1240px;
  min-width: 0;
  margin-left: auto;
  margin-right: auto;
  /* 左列上限给足，让竖版卡片能按自身比例撑开，不会被压窄后裁掉人物两侧 */
  grid-template-columns: minmax(280px, 600px) minmax(320px, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  align-items: stretch;
  gap: clamp(14px, 1.6vw, 24px);
  padding: clamp(54px, 7vh, 70px) clamp(20px, 4vw, 56px) clamp(8px, 1.6vh, 16px);
}
/* 让“人物 / 信息”直接参与父级栅格 */
.fc--v2 .fc__left { display: contents; }

/* 数字人舞台卡 */
.fc--v2 .fc__figure,
.fc--v2 .fc__figure--3d {
  grid-column: 1;
  grid-row: 1 / span 2;
  height: 100%;
  width: auto;
  max-width: 100%;
  min-height: 0;
  /* 与数字人竖版画面同比例，避免出现内外两层大小不一的框 */
  aspect-ratio: 480 / 854;
  justify-self: start;
  padding: 0;
  border-radius: 26px;
  overflow: hidden;
  border: 1px solid rgba(214, 178, 111, 0.24);
  background:
    radial-gradient(78% 52% at 50% 16%, rgba(198, 154, 75, 0.20), transparent 64%),
    linear-gradient(180deg, #1d2833 0%, #141d26 58%, #0c1319 100%);
  box-shadow: 0 30px 70px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
/* 舞台四周压暗，人物画面更聚焦 */
.fc--v2 .fc__figure::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  /* 轻微压暗 + 四周加暗，让绿幕画面与墨色主题更融合 */
  background:
    linear-gradient(180deg, rgba(12, 18, 24, 0.10), rgba(12, 18, 24, 0.24)),
    radial-gradient(124% 92% at 50% 44%, transparent 54%, rgba(8, 12, 16, 0.48) 100%);
}
.fc--v2 .fc__glow {
  z-index: 0;
  bottom: auto;
  top: 46%;
  width: min(64%, 320px);
  background: radial-gradient(circle, rgba(237, 183, 79, 0.22), rgba(255, 255, 255, 0.06) 46%, transparent 72%);
  filter: blur(16px);
}
.fc--v2 .fc__figure > *:not(.fc__glow) { z-index: 1; }
.fc--v2 .fc__figure img {
  max-height: 100%;
  max-width: 100%;
  transform: translateY(calc(var(--talk, 0) * -6px)) scale(1.02);
  filter: drop-shadow(0 20px 28px rgba(0, 0, 0, 0.42));
}
.fc--v2 .fc__figure video,
.fc--v2 .fc__figure canvas { max-height: 100%; max-width: 100%; }

/* 人物信息卡 */
.fc--v2 .fc__meta {
  grid-column: 2;
  grid-row: 1;
  width: 100%;
  text-align: left;
  padding: 20px 22px 18px;
  border-radius: 20px;
  border: 1px solid rgba(214, 178, 111, 0.20);
  background: rgba(255, 250, 240, 0.055);
  backdrop-filter: blur(10px);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
  text-shadow: none;
}
.fc--v2 .fc__dyn {
  display: inline-block;
  margin-bottom: 10px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid rgba(214, 178, 111, 0.30);
  background: rgba(214, 178, 111, 0.16);
  color: #e8cd93;
  font-size: 12px;
  letter-spacing: 0.06em;
}
.fc--v2 .fc__meta h1 {
  margin: 2px 0 4px;
  color: #f4ecdc;
  font-size: clamp(26px, 2.6vw, 36px);
}
.fc--v2 .fc__title { color: rgba(236, 229, 216, 0.76); font-size: 14px; }
.fc--v2 .fc__quote {
  margin-top: 12px;
  padding-left: 12px;
  border-left: 3px solid #c69a4b;
  color: #dcc292;
  font-size: 14.5px;
  text-align: left;
}

/* 对话卡 */
.fc--v2 .fc__bubble {
  grid-column: 2;
  grid-row: 2;
  display: flex;
  flex-direction: column;
  align-self: stretch;
  justify-self: stretch;
  width: 100%;
  max-height: none;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 22px;
  border-radius: 20px;
  border: 1px solid rgba(214, 178, 111, 0.20);
  background: rgba(255, 250, 240, 0.055);
  backdrop-filter: blur(10px);
  color: #ece5d8;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
}
.fc--v2 .fc__bubble::before,
.fc--v2 .fc__bubble::after { display: none; }
.fc--v2 .fc__bubble.is-empty { width: 100%; }
.fc--v2 .fc__asked {
  color: rgba(236, 229, 216, 0.74);
  border-bottom-color: rgba(236, 229, 216, 0.12);
}
.fc--v2 .fc__emptyTitle { color: #eed9a8; }
.fc--v2 .fc__emptyText { color: rgba(236, 229, 216, 0.74); }
.fc--v2 .fc__sources { padding-top: 12px; color: rgba(236, 229, 216, 0.66); }
/* 对话卡底部的书院水印，填补内容较少时的留白 */
.fc--v2 .fc__wm {
  margin-top: auto;
  padding-top: 18px;
  text-align: center;
  font-family: var(--font-serif);
  font-size: clamp(18px, 1.8vw, 26px);
  letter-spacing: 0.36em;
  text-indent: 0.36em;
  color: rgba(214, 178, 111, 0.13);
  user-select: none;
  pointer-events: none;
}
/* 深色底下的正文排版微调（v-html 内容需要用 :deep 穿透） */
.fc--v2 .fc__bubble :deep(.md-body blockquote) {
  color: rgba(236, 229, 216, 0.62);
  border-left-color: rgba(214, 178, 111, 0.45);
}
.fc--v2 .fc__bubble :deep(.md-body code) {
  background: rgba(255, 255, 255, 0.09);
  color: #ecdcb8;
}
.fc--v2 .fc__bubble :deep(.md-body pre) { background: rgba(0, 0, 0, 0.36); }
.fc--v2 .fc__bubble :deep(.md-body a) { color: #d9b46b; }
.fc--v2 .fc__bubble :deep(.md-body th),
.fc--v2 .fc__bubble :deep(.md-body td) { border-color: rgba(236, 229, 216, 0.16); }

/* 底部操作区 */
.fc--v2 .fc__dock {
  width: 100%;
  max-width: 1240px;
  min-width: 0;
  margin-left: auto;
  margin-right: auto;
  padding: 10px clamp(20px, 4vw, 56px) 18px;
  box-sizing: border-box;
}
.fc--v2 .fc__chips { min-width: 0; }
.fc--v2 .fc__chips button {
  border: 1px solid rgba(214, 178, 111, 0.30);
  background: rgba(255, 250, 240, 0.06);
  color: #dcc79a;
  box-shadow: none;
}
.fc--v2 .fc__chips button:hover:not(:disabled) {
  background: rgba(214, 178, 111, 0.18);
  transform: translateY(-1px);
}
.fc--v2 .fc__composer {
  min-width: 0;
  border: 1px solid rgba(214, 178, 111, 0.22);
  border-radius: 20px;
  background: rgba(255, 250, 240, 0.055);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(10px);
  padding: 12px;
}
.fc--v2 .fc__input {
  min-width: 0;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.30);
  color: #ece5d8;
}
.fc--v2 .fc__input::placeholder { color: rgba(236, 229, 216, 0.52); }
.fc--v2 .fc__input:focus { outline: 2px solid rgba(198, 154, 75, 0.45); }
.fc--v2 .fc__send {
  border-radius: 14px;
  background: linear-gradient(135deg, #d9ae5d, #b8863a);
  color: #1d1608;
  box-shadow: 0 12px 24px rgba(184, 134, 58, 0.28);
}
.fc--v2 .fc__send--stop { background: var(--red); box-shadow: none; }
.fc--v2 .fc__mic {
  border-radius: 14px;
  border: 1px solid rgba(214, 178, 111, 0.24);
  background: rgba(0, 0, 0, 0.26);
  color: #dcc79a;
}
.fc--v2 .fc__voicebar { color: rgba(236, 229, 216, 0.76); padding: 0 12px; }
.fc--v2 .fc__toggle input { accent-color: #c69a4b; width: 15px; height: 15px; }
.fc--v2 .fc__readbtn {
  border: 1px solid rgba(214, 178, 111, 0.30);
  background: rgba(255, 250, 240, 0.06);
  color: #dcc79a;
}
.fc--v2 .fc__error { color: #f0a9a0; }
.fc--v2 .fc__verr { color: #e8b584; }

/* 窄屏回退单栏 */
@media (max-width: 980px) {
  .fc--v2 .fc__stage { grid-template-columns: minmax(0, 1fr); grid-template-rows: none; }
  .fc--v2 .fc__figure,
  .fc--v2 .fc__figure--3d {
    grid-column: 1;
    grid-row: auto;
    /* 单栏时用确定高度反推宽度，保证与竖版画面同比例 */
    height: min(560px, 62vh);
    width: auto;
    max-width: 100%;
    min-height: 0;
    aspect-ratio: 480 / 854;
    justify-self: center;
  }
  .fc--v2 .fc__meta,
  .fc--v2 .fc__bubble { grid-column: 1; grid-row: auto; min-width: 0; }
  .fc--v2 .fc__bubble { max-height: min(52vh, 460px); align-self: start; }
}

/* ============================================================
   江万里 · 数字人主舞台（电影字幕式）
   左：人物小传 ｜ 中：数字人 ｜ 右：留白
   回答以影院字幕形式出现在数字人正下方，随语音逐字浮现。
   ============================================================ */
.fc--v2 .fc__cinema {
  position: relative;
  z-index: 1;
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  max-width: 1560px;
  margin: 0 auto;
  box-sizing: border-box;
  display: grid;
  /* 左右各占一份等宽留白，中间列即屏幕正中 */
  grid-template-columns: minmax(0, 1fr) minmax(0, 760px) minmax(0, 1fr);
  /* 单行撑满整个可用高度，剩余空间由中间列内部再分配 */
  grid-template-rows: minmax(0, 1fr);
  align-items: stretch;
  gap: clamp(14px, 2vw, 40px);
  padding: clamp(14px, 2.2vh, 34px) clamp(18px, 3.2vw, 48px) clamp(8px, 1.2vh, 14px);
}

/* ---- 左侧：人物小传 ---- */
.fc--v2 .fc__cineInfo {
  grid-column: 1;
  justify-self: end;
  align-self: center;
  width: clamp(238px, 23vw, 340px);
  max-width: 100%;
  max-height: 100%;
  overflow-y: auto;
  padding: 22px 24px 24px;
  border-radius: 20px;
  border: 1px solid rgba(214, 178, 111, 0.20);
  background: rgba(255, 250, 240, 0.055);
  backdrop-filter: blur(10px);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.36);
  text-align: left;
}
.fc--v2 .fc__cineInfo h1 {
  margin: 2px 0 4px;
  color: #f4ecdc;
  font-size: clamp(26px, 2.4vw, 34px);
}
.fc--v2 .fc__cineInfo .fc__title {
  color: rgba(236, 229, 216, 0.76);
  font-size: 14px;
}
.fc--v2 .fc__cineInfo .fc__quote {
  margin-top: 14px;
  padding-left: 12px;
  border-left: 3px solid #c69a4b;
  color: #dcc292;
  font-size: 14.5px;
  text-align: left;
}
.fc--v2 .fc__bio {
  margin-top: 14px;
  color: rgba(236, 229, 216, 0.70);
  font-size: 13.5px;
  line-height: 1.95;
  text-align: justify;
}

/* 固定问题：竖排在人物卡下方 */
.fc--v2 .fc__cineAsk {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(214, 178, 111, 0.18);
}
.fc--v2 .fc__cineAskLbl {
  margin-bottom: 2px;
  color: rgba(236, 229, 216, 0.48);
  font-size: 11.5px;
  letter-spacing: 0.1em;
}
.fc--v2 .fc__cineAsk button {
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid rgba(214, 178, 111, 0.24);
  background: rgba(255, 250, 240, 0.05);
  color: #dcc79a;
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease, transform 0.16s ease;
}
.fc--v2 .fc__cineAsk button:hover:not(:disabled) {
  background: rgba(214, 178, 111, 0.16);
  color: #f2dfae;
  transform: translateX(2px);
}
.fc--v2 .fc__cineAsk button:disabled { opacity: 0.5; cursor: default; }

/* ---- 中间：数字人主舞台 ---- */
.fc--v2 .fc__cineMain {
  grid-column: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* 撑满所在栅格行，数字人再把剩余高度全吃掉 */
  height: 100%;
  min-height: 0;
  min-width: 0;
}

.fc--v2 .fc__cineStage {
  position: relative;
  /* 自动吃满「减去字幕与喇叭」后的全部高度，不再依赖固定像素推算 */
  flex: 1 1 auto;
  min-height: 220px;
  height: auto;
  max-height: 100%;
  /* 保持原视频比例整体等比放大，只去掉最上方一条绿边，全身完整 */
  aspect-ratio: 480 / 824;
  width: auto;
  max-width: 100%;
  justify-self: center;
  align-self: center;
  border-radius: 26px;
  overflow: hidden;
  border: 1px solid rgba(214, 178, 111, 0.24);
  background:
    radial-gradient(78% 52% at 50% 16%, rgba(198, 154, 75, 0.20), transparent 64%),
    linear-gradient(180deg, #1d2833 0%, #141d26 58%, #0c1319 100%);
  box-shadow: 0 30px 70px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
/* 画面裁切偏上，去掉上方绿幕留白，人物整体更饱满 */
.fc--v2 .fc__cineStage :deep(.lta__canvas) {
  /* 裁切只发生在画面上缘（绿幕留白），下半身完整保留 */
  object-position: center bottom;
}
/* 四周压暗，画面更聚焦 */
.fc--v2 .fc__cineStage::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background:
    linear-gradient(180deg, rgba(12, 18, 24, 0.08), rgba(12, 18, 24, 0.22)),
    radial-gradient(124% 92% at 50% 44%, transparent 54%, rgba(8, 12, 16, 0.46) 100%);
}

/* ---- 字幕区（数字人正下方，电影字幕式） ---- */
.fc--v2 .fc__cineSubtitle {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  flex: none;
  width: min(660px, 100%);
  /* 固定高度，逐字浮现时下方按钮不会跟着跳动 */
  height: 62px;
  margin-top: 8px;
  text-align: center;
}
.fc--v2 .fc__cineLine {
  margin: 0;
  max-height: 100%;
  overflow-y: auto;
  font-size: clamp(15px, 1.02vw, 16px);
  line-height: 1.8;
  letter-spacing: 0.03em;
  color: #f6eedd;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.9), 0 0 26px rgba(0, 0, 0, 0.7);
}
/* 逐字浮现时的光标 */
.fc--v2 .fc__cineLine.is-typing::after {
  content: "";
  display: inline-block;
  width: 0.44em;
  height: 1em;
  margin-left: 4px;
  vertical-align: -0.14em;
  border-radius: 2px;
  background: linear-gradient(180deg, #f2dda6, #c69a4b);
  animation: fcCaret 1s steps(1) infinite;
}
@keyframes fcCaret {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}
.fc--v2 .fc__cineLine--wait {
  color: rgba(236, 229, 216, 0.68);
  animation: fcBreath 1.8s ease-in-out infinite;
}
@keyframes fcBreath {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0.95; }
}
.fc--v2 .fc__cineLine--idle { color: rgba(236, 229, 216, 0.50); font-size: 14px; }
.fc--v2 .fc__cineLine--err { color: #f0a9a0; font-size: 14.5px; }

/* ---- 操作区：默认问题 + 喇叭 ---- */
.fc--v2 .fc__cineActions {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: none;
  gap: 8px;
  width: 100%;
  margin-top: 6px;
}
.fc--v2 .fc__cineActions .fc__chips {
  max-width: 620px;
  margin-bottom: 0;
  gap: 10px;
}
.fc--v2 .fc__cineActions .fc__chips button {
  padding: 8px 16px;
  border: 1px solid rgba(214, 178, 111, 0.30);
  background: rgba(255, 250, 240, 0.06);
  color: #dcc79a;
  font-size: 13px;
  box-shadow: none;
  backdrop-filter: blur(8px);
}
.fc--v2 .fc__cineActions .fc__chips button:hover:not(:disabled) {
  background: rgba(214, 178, 111, 0.18);
  color: #f2dfae;
  transform: translateY(-1px);
}

.fc--v2 .fc__micRound {
  display: grid;
  place-items: center;
  width: 78px;
  height: 78px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid rgba(214, 178, 111, 0.42);
  background: radial-gradient(circle at 50% 32%, rgba(214, 178, 111, 0.30), rgba(19, 28, 37, 0.94) 72%);
  color: #f2e2bb;
  font-size: 12.5px;
  letter-spacing: 0.04em;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.46), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}
.fc--v2 .fc__micRound:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(214, 178, 111, 0.72);
  box-shadow: 0 20px 42px rgba(0, 0, 0, 0.5), 0 0 0 6px rgba(214, 178, 111, 0.08);
}
.fc--v2 .fc__micRound:disabled { opacity: 0.5; cursor: default; }
.fc--v2 .fc__micRound .fc__micIcon { font-size: 30px; line-height: 1; }
.fc--v2 .fc__micRound.is-rec {
  border-color: rgba(231, 118, 100, 0.72);
  background: radial-gradient(circle at 50% 32%, rgba(231, 118, 100, 0.48), rgba(58, 20, 18, 0.94) 72%);
  color: #ffe8e3;
  animation: micpulse 1.1s infinite;
}
/* 右侧留白（与左栏等宽，保证数字人真正居中） */
.fc--v2 .fc__cineSpacer { grid-column: 3; }

/* 中窄屏：单列堆叠，仍是数字人为主 */
@media (max-width: 1240px) {
  .fc--v2 .fc__cinema {
    /* 单列时改成纵向流式排列，避免栅格居中导致内容互相压叠 */
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    gap: 18px;
    overflow-y: auto;
    padding: clamp(58px, 7vh, 74px) clamp(16px, 4vw, 32px) clamp(14px, 3vh, 26px);
  }
  .fc--v2 .fc__cineInfo {
    justify-self: center;
    width: min(560px, 100%);
    order: 2;
    /* 不参与收缩，否则内容会比卡片高而压到下一块 */
    flex: none;
  }
  .fc--v2 .fc__cineMain { width: 100%; order: 1; flex: none; }
  .fc--v2 .fc__cineStage { height: min(58vh, 540px); max-width: 100%; flex: none; }
  .fc--v2 .fc__cineSpacer { display: none; }
}
</style>
