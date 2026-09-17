<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import LiveTalkingAvatar from '@/components/agent/LiveTalkingAvatar.vue'
import { listFigures } from '@/api/figures'
import { academyById } from '@/data/academies'

const route = useRoute()
const academy = computed(() => academyById(String(route.params.id || '')) || null)

// 与江万里数字人同一套逻辑：LiveTalking 实时口型驱动
const liveRef = ref<InstanceType<typeof LiveTalkingAvatar> | null>(null)
const liveReady = ref(false)
const liveSpeaking = ref(false)
const liveError = ref('')
// 讲解员音色跟随「江万里」这个数字人，与名人对话页保持一致
const guideVoice = ref<{ id?: string | null; style?: string | null; desc?: string | null }>({})

onMounted(async () => {
  try {
    const figures = await listFigures()
    const jw = figures.find((f) => f.id === 'jiangwanli')
    if (jw) {
      guideVoice.value = { id: jw.voice_id, style: jw.voice_style, desc: jw.voice_desc }
    }
  } catch {
    // 拉取失败时回退到默认音色
  }
})

function playGuide() {
  if (academy.value) liveRef.value?.speak(academy.value.narration)
}

function onLiveReady() {
  liveReady.value = true
}

function onLiveSpeaking(active: boolean) {
  liveSpeaking.value = active
}

function onLiveError(message: string) {
  liveError.value = message
}
</script>

<template>
  <div v-if="academy" class="ad">
    <section class="shell ad__hero">
      <div class="ad__media">
        <img v-if="academy.image" :src="academy.image" :alt="academy.name" />
        <span v-else class="ad__seal h-serif">{{ academy.name.slice(0, 1) }}</span>
      </div>
      <div class="ad__info">
        <p class="eyebrow">{{ academy.city }} · {{ academy.era }}</p>
        <h1 class="h-serif">{{ academy.name }}</h1>
        <p class="ad__summary">{{ academy.summary }}</p>
      </div>
    </section>

    <section class="shell ad__grid">
      <div class="ad__main">
        <h2 class="ad__h">历史沿革</h2>
        <ol class="ad__history">
          <li v-for="(h, i) in academy.history" :key="i">{{ h }}</li>
        </ol>

        <h2 class="ad__h">相关人物</h2>
        <div class="ad__figures">
          <span v-for="f in academy.figures" :key="f" class="ad__figure">{{ f }}</span>
        </div>

        <h2 class="ad__h">代表诗文</h2>
        <div v-for="p in academy.poems" :key="p.title" class="ad__poem">
          <strong>{{ p.title }}</strong>
          <p>{{ p.text }}</p>
        </div>
      </div>

      <aside class="ad__guide">
        <div class="ad__guideTop">
          <span class="ad__guideTag">AI 数字人讲解员</span>
          <h3 class="h-serif">江万里 · 为你讲解</h3>
        </div>
        <div class="ad__human">
          <LiveTalkingAvatar
            ref="liveRef"
            avatar-id="jiangwanli_lt"
            :voice-id="guideVoice.id"
            :voice-style="guideVoice.style"
            :voice-desc="guideVoice.desc"
            @ready="onLiveReady"
            @speaking="onLiveSpeaking"
            @error="onLiveError"
          />
        </div>
        <button class="ad__play" :disabled="!liveReady || liveSpeaking" @click="playGuide">
          {{ !liveReady ? '数字人连接中…' : liveSpeaking ? '正在讲解…' : '播放书院讲解' }}
        </button>
        <p v-if="liveError" class="ad__err">{{ liveError }}</p>
      </aside>
    </section>

    <section class="shell ad__back">
      <RouterLink to="/academies">← 返回书院百科</RouterLink>
    </section>
  </div>
  <div v-else class="ad__empty shell">未找到该书院</div>
</template>

<style scoped>
.ad { min-height: 100vh; background: var(--bg); padding-bottom: 64px; }
.ad__hero { display: grid; grid-template-columns: 380px 1fr; gap: 32px; align-items: center; padding: 44px 0 28px; }
.ad__media { aspect-ratio: 4 / 3; display: grid; place-items: center; border-radius: 18px; overflow: hidden; background: linear-gradient(155deg, rgba(44,62,80,.06), #fff); border: 1px solid var(--line); }
.ad__media img { width: 100%; height: 100%; object-fit: cover; }
.ad__seal { font-size: 96px; font-weight: 800; color: var(--navy); opacity: .3; }
.eyebrow { color: var(--gold-deep); font-size: 13px; font-weight: 700; letter-spacing: .06em; }
.ad__info h1 { margin: 8px 0 12px; font-size: clamp(30px, 4vw, 46px); font-weight: 800; color: var(--ink); }
.ad__summary { color: var(--sub); font-size: 16px; line-height: 1.9; max-width: 680px; }
.ad__grid { display: grid; grid-template-columns: 1fr 360px; gap: 24px; }
.ad__main { padding: 24px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.ad__h { margin: 18px 0 12px; font-size: 20px; font-weight: 800; color: var(--ink); }
.ad__h:first-child { margin-top: 0; }
.ad__history { list-style: none; padding: 0; }
.ad__history li { position: relative; padding: 10px 0 10px 26px; color: var(--sub); font-size: 14.5px; }
.ad__history li::before { content: ''; position: absolute; left: 4px; top: 18px; width: 8px; height: 8px; border-radius: 50%; background: var(--gold); }
.ad__history li + li { border-top: 1px solid var(--line); }
.ad__figures { display: flex; flex-wrap: wrap; gap: 8px; }
.ad__figure { padding: 6px 14px; border-radius: 999px; background: color-mix(in srgb, var(--gold) 12%, var(--bg)); color: var(--gold-deep); font-size: 13px; }
.ad__poem { margin-bottom: 10px; padding: 12px 16px; border-left: 3px solid var(--gold); background: var(--bg); border-radius: 0 10px 10px 0; }
.ad__poem strong { color: var(--ink); }
.ad__poem p { margin-top: 4px; color: var(--sub); }
.ad__guide { align-self: start; display: flex; flex-direction: column; padding: 18px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.ad__guideTop { display: flex; flex-direction: column; gap: 4px; }
.ad__guideTag { color: var(--gold-deep); font-size: 12px; font-weight: 700; letter-spacing: .06em; }
.ad__guide h3 { font-size: 20px; font-weight: 800; color: var(--ink); }
/* 与数字人竖版画面同比例，保证画面铺满、不裁人 */
.ad__human { width: min(100%, 320px); margin: 12px auto; aspect-ratio: 480 / 854; border-radius: 12px; overflow: hidden; background: #10151c; }
.ad__play { padding: 12px; border-radius: 12px; background: var(--navy); color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; }
.ad__play:disabled { opacity: .55; cursor: default; }
.ad__err { margin-top: 8px; color: var(--red); font-size: 12.5px; }
.ad__back { padding-top: 24px; }
.ad__back a { color: var(--navy); font-weight: 700; text-decoration: none; }
.ad__empty { padding: 80px 0; text-align: center; color: var(--muted); }
@media (max-width: 900px) {
  .ad__hero, .ad__grid { grid-template-columns: 1fr; }
}
</style>
