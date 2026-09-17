<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Q {
  q: string
  options: string[]
  answer: number
}

const QUESTIONS: Q[] = [
  { q: '白鹿洞书院位于哪座山？', options: ['庐山', '泰山', '华山', '衡山'], answer: 0 },
  { q: '《白鹿洞书院揭示》由谁亲订？', options: ['陆九渊', '朱熹', '王阳明', '吕祖谦'], answer: 1 },
  { q: '“鹅湖之会”主要在哪两人之间论辩？', options: ['朱熹与陆九渊', '朱熹与王阳明', '陆九渊与王阳明', '吕祖谦与朱熹'], answer: 0 },
  { q: '陆九渊是哪个学派的代表人物？', options: ['理学', '心学', '气学', '实学'], answer: 1 },
  { q: '“宇宙便是吾心，吾心即是宇宙”是谁说的？', options: ['朱熹', '王阳明', '陆九渊', '周敦颐'], answer: 2 },
  { q: '王阳明提倡的核心主张是？', options: ['格物致知', '知行合一', '正心诚意', '致中和'], answer: 1 },
  { q: '白鹭洲书院位于哪个城市？', options: ['南昌', '九江', '赣州', '吉安'], answer: 3 },
  { q: '文天祥是哪座书院的学子？', options: ['鹅湖书院', '象山书院', '白鹭洲书院', '白鹿洞书院'], answer: 2 },
  { q: '象山书院位于哪个县市？', options: ['铅山', '贵溪（鹰潭）', '庐山', '吉安'], answer: 1 },
  { q: '“问渠那得清如许？为有源头活水来”出自谁？', options: ['王阳明', '陆九渊', '文天祥', '朱熹'], answer: 3 },
]

const stage = ref<'start' | 'playing' | 'done'>('start')
const idx = ref(0)
const score = ref(0)
const picked = ref<number | null>(null)
const answered = ref(false)
const name = ref('')
const saved = ref(false)
const board = ref<{ name: string; score: number }[]>([])

const current = () => QUESTIONS[idx.value]

function start() {
  stage.value = 'playing'
  idx.value = 0
  score.value = 0
  picked.value = null
  answered.value = false
  saved.value = false
}

function pick(i: number) {
  if (answered.value) return
  picked.value = i
  answered.value = true
  if (i === current().answer) score.value += 10
}

function next() {
  if (idx.value < QUESTIONS.length - 1) {
    idx.value += 1
    picked.value = null
    answered.value = false
  } else {
    stage.value = 'done'
  }
}

function loadBoard() {
  try {
    board.value = JSON.parse(localStorage.getItem('academy_quiz_board') || '[]')
  } catch {
    board.value = []
  }
}

function save() {
  if (!name.value.trim()) return
  board.value.push({ name: name.value.trim(), score: score.value })
  board.value.sort((a, b) => b.score - a.score)
  board.value = board.value.slice(0, 10)
  localStorage.setItem('academy_quiz_board', JSON.stringify(board.value))
  saved.value = true
}

onMounted(loadBoard)
</script>

<template>
  <div class="qz">
    <section class="shell qz__head">
      <p class="eyebrow">闯关答题</p>
      <h1 class="h-serif">书院知识 · 挑战赛</h1>
      <p class="qz__lead">每答对一题得 10 分，看看你对江右书院了解多少。</p>
    </section>

    <section class="shell qz__panel">
      <template v-if="stage === 'start'">
        <div class="qz__start">
          <strong>共 {{ QUESTIONS.length }} 题</strong>
          <p>答题结果会保存在本机排行榜（不会上传）。</p>
          <button class="qz__btn" @click="start">开始挑战</button>
        </div>
      </template>

      <template v-else-if="stage === 'playing'">
        <div class="qz__bar">
          <span>{{ idx + 1 }} / {{ QUESTIONS.length }}</span>
          <span>{{ score }} 分</span>
        </div>
        <h2 class="qz__q">{{ current().q }}</h2>
        <div class="qz__opts">
          <button
            v-for="(opt, i) in current().options"
            :key="i"
            class="qz__opt"
            :class="{
              'is-right': answered && i === current().answer,
              'is-wrong': answered && picked === i && i !== current().answer,
            }"
            :disabled="answered"
            @click="pick(i)"
          >{{ opt }}</button>
        </div>
        <button v-if="answered" class="qz__btn" @click="next">
          {{ idx < QUESTIONS.length - 1 ? '下一题' : '查看成绩' }}
        </button>
      </template>

      <template v-else>
        <div class="qz__done">
          <h2 class="h-serif">本次得分：{{ score }}</h2>
          <div v-if="!saved" class="qz__save">
            <input v-model="name" maxlength="12" placeholder="输入你的名字" />
            <button class="qz__btn" :disabled="!name.trim()" @click="save">保存成绩</button>
          </div>
          <div class="qz__board">
            <h3>排行榜</h3>
            <p v-if="!board.length" class="qz__empty">还没有记录</p>
            <ol v-else>
              <li v-for="(b, i) in board" :key="i">
                <span>{{ i + 1 }}. {{ b.name }}</span>
                <strong>{{ b.score }} 分</strong>
              </li>
            </ol>
          </div>
          <button class="qz__btn qz__btn--ghost" @click="start">再来一次</button>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.qz { min-height: 100vh; background: var(--bg); padding-bottom: 64px; }
.qz__head { padding: 48px 0 20px; text-align: center; }
.eyebrow { color: var(--gold-deep); font-size: 13px; font-weight: 700; letter-spacing: .08em; }
.qz__head h1 { margin: 8px 0 0; font-size: clamp(26px, 3.4vw, 40px); font-weight: 800; color: var(--ink); }
.qz__lead { margin: 12px auto 0; color: var(--sub); font-size: 14.5px; }
.qz__panel { max-width: 680px; margin: 0 auto; padding: 24px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.qz__start { text-align: center; padding: 20px 0; }
.qz__start strong { display: block; font-size: 22px; color: var(--ink); }
.qz__start p { margin: 10px 0 20px; color: var(--muted); font-size: 13px; }
.qz__btn { padding: 11px 26px; border-radius: 12px; background: var(--navy); color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; }
.qz__btn:disabled { opacity: .5; cursor: default; }
.qz__btn--ghost { background: transparent; color: var(--navy); border: 1px solid var(--navy); }
.qz__bar { display: flex; justify-content: space-between; color: var(--sub); font-size: 13px; }
.qz__q { margin: 18px 0; font-size: 20px; font-weight: 800; color: var(--ink); line-height: 1.6; }
.qz__opts { display: flex; flex-direction: column; gap: 10px; }
.qz__opt { padding: 13px 16px; border-radius: 12px; border: 1px solid var(--line); background: var(--bg); color: var(--ink); text-align: left; cursor: pointer; transition: all .15s var(--ease); }
.qz__opt:hover:not(:disabled) { border-color: var(--gold); }
.qz__opt.is-right { background: rgba(46, 160, 67, .14); border-color: #2ea043; }
.qz__opt.is-wrong { background: rgba(231, 76, 60, .12); border-color: #e74c3c; }
.qz__done { text-align: center; }
.qz__done h2 { font-size: 30px; color: var(--ink); }
.qz__save { display: flex; gap: 10px; justify-content: center; margin: 18px 0; }
.qz__save input { width: 200px; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--bg); }
.qz__board { margin: 20px 0; text-align: left; }
.qz__board h3 { font-size: 17px; color: var(--ink); }
.qz__board ol { list-style: none; padding: 0; }
.qz__board li { display: flex; justify-content: space-between; padding: 8px 4px; border-bottom: 1px solid var(--line); color: var(--sub); }
.qz__board strong { color: var(--gold-deep); }
.qz__empty { color: var(--muted); font-size: 13px; }
</style>
