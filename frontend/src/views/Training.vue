<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  listSubjects,
  startExam,
  gradeTrainingSession,
  listTrainingSessions,
  getTrainingReport,
  type Subject,
  type TrainingSession,
  type TrainingQuestion,
  type TrainingReport,
} from '@/api/training'

const EXAM_SIZE = 20 // 每次答卷固定 20 题

type Step = 'pick' | 'answer' | 'report'

const subjects = ref<Subject[]>([])
const step = ref<Step>('pick')
const busy = ref(false)
const busyText = ref('')
const error = ref('')
const loadingSubjects = ref(true)

const pick = reactive({ subject: '', difficulty: 'normal' })

const sessionId = ref<number | null>(null)
const questions = ref<TrainingQuestion[]>([])
const answers = reactive<Record<number, string>>({})
const report = ref<TrainingReport | null>(null)
const history = ref<TrainingSession[]>([])

const diffOptions = [
  { value: 'easy', label: '基础', key: 'easy' as const },
  { value: 'normal', label: '进阶', key: 'normal' as const },
  { value: 'hard', label: '挑战', key: 'hard' as const },
]
const TYPE_LABEL: Record<string, string> = {
  single_choice: '单选题', judge: '判断题', short_answer: '简答题', essay: '论述题', compare: '辨析题', mixed: '综合',
}
const JUDGE_OPTS = [
  { key: '对', text: '正确' },
  { key: '错', text: '错误' },
]

const activeSubject = computed(() => subjects.value.find((s) => s.subject === pick.subject) || null)
const availForPick = computed(() => activeSubject.value ? (activeSubject.value[pick.difficulty as 'easy' | 'normal' | 'hard'] || 0) : 0)
const canStart = computed(() => !!pick.subject && availForPick.value > 0 && !busy.value)
const answeredCount = computed(() => questions.value.filter((q) => (answers[q.id] || '').trim()).length)
const totalScoreMax = computed(() => questions.value.reduce((s, q) => s + (q.max_score || 0), 0))

// 题型分区顺序：判断题 → 单选题 → 简答 → 论述 → 辨析（与后端成卷顺序一致）。
const TYPE_ORDER = ['judge', 'single_choice', 'short_answer', 'essay', 'compare']
const CN_NUM = ['一', '二', '三', '四', '五', '六']
function typeRank(t: string) {
  const i = TYPE_ORDER.indexOf(t)
  return i < 0 ? 99 : i
}

// 按题型分区（单选/判断/简答/论述…），区内按序号；全卷连续编号。
const orderedQuestions = computed(() =>
  [...questions.value].sort((a, b) => typeRank(a.question_type) - typeRank(b.question_type) || (a.seq ?? 0) - (b.seq ?? 0)),
)
const numById = computed(() => {
  const m: Record<number, number> = {}
  orderedQuestions.value.forEach((q, i) => (m[q.id] = i + 1))
  return m
})
const examSections = computed(() => {
  const g: { type: string; label: string; max: number; items: TrainingQuestion[] }[] = []
  for (const q of orderedQuestions.value) {
    let s = g.find((x) => x.type === q.question_type)
    if (!s) { s = { type: q.question_type, label: TYPE_LABEL[q.question_type] || q.question_type, max: q.max_score, items: [] }; g.push(s) }
    s.items.push(q)
  }
  return g
})

// 成绩单同样分区
const reportOrdered = computed(() =>
  [...reportRows.value].sort((a, b) => typeRank(a.q!.question_type) - typeRank(b.q!.question_type) || (a.q!.seq ?? 0) - (b.q!.seq ?? 0)),
)
const reportNumById = computed(() => {
  const m: Record<number, number> = {}
  reportOrdered.value.forEach((r, i) => (m[r.q!.id] = i + 1))
  return m
})
const reportSections = computed(() => {
  const g: { type: string; label: string; items: typeof reportOrdered.value }[] = []
  for (const r of reportOrdered.value) {
    let s = g.find((x) => x.type === r.q!.question_type)
    if (!s) { s = { type: r.q!.question_type, label: TYPE_LABEL[r.q!.question_type] || r.q!.question_type, items: [] }; g.push(s) }
    s.items.push(r)
  }
  return g
})

function isChoice(q: TrainingQuestion) { return q.question_type === 'single_choice' }
function isJudge(q: TrainingQuestion) { return q.question_type === 'judge' }
function judgeText(key: string) {
  return JUDGE_OPTS.find((o) => o.key === key)?.text || key
}

async function loadHistory() {
  try {
    history.value = (await listTrainingSessions()).filter((s) => s.status === 'graded')
  } catch {
    history.value = []
  }
}

onMounted(async () => {
  try {
    subjects.value = await listSubjects()
    pick.subject = subjects.value[0]?.subject || ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载科目失败'
  } finally {
    loadingSubjects.value = false
  }
  loadHistory()
})

async function openRecord(id: number) {
  busy.value = true
  busyText.value = '正在调取记录…'
  try {
    report.value = await getTrainingReport(id)
    step.value = 'report'
    window.scrollTo({ top: 0 })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '调取失败'
  } finally {
    busy.value = false
  }
}

async function start() {
  if (!canStart.value) return
  error.value = ''
  busy.value = true
  busyText.value = '正在组卷…'
  try {
    const res = await startExam({ subject: pick.subject, difficulty: pick.difficulty, count: EXAM_SIZE })
    sessionId.value = res.session.id
    questions.value = res.questions
    Object.keys(answers).forEach((k) => delete answers[Number(k)])
    res.questions.forEach((q) => (answers[q.id] = ''))
    report.value = null
    step.value = 'answer'
    window.scrollTo({ top: 0 })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '组卷失败'
  } finally {
    busy.value = false
  }
}

async function submit() {
  if (!sessionId.value) return
  if (answeredCount.value === 0) { error.value = '请至少作答一题再交卷。'; return }
  error.value = ''
  busy.value = true
  busyText.value = '正在批改…'
  try {
    const payload = questions.value.map((q) => ({ question_id: q.id, answer: answers[q.id] || '' }))
    report.value = await gradeTrainingSession(sessionId.value, payload)
    step.value = 'report'
    window.scrollTo({ top: 0 })
    loadHistory()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '批改失败'
  } finally {
    busy.value = false
  }
}

function restart() {
  step.value = 'pick'
  questions.value = []
  report.value = null
  sessionId.value = null
  error.value = ''
}

function scrollToQ(id: number) {
  document.getElementById(`q-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// ---- 成绩单 ----
const reportRows = computed(() => {
  if (!report.value) return []
  const byId: Record<number, TrainingQuestion> = {}
  report.value.questions.forEach((q) => (byId[q.id] = q))
  return report.value.answers
    .map((a) => ({ ...a, q: byId[a.question_id] }))
    .filter((r) => r.q)
    .sort((x, y) => (x.q!.seq ?? 0) - (y.q!.seq ?? 0))
})
const totalScore = computed(() => report.value?.session.total_score ?? 0)
const scoreLevel = computed(() => {
  const s = totalScore.value
  if (s >= 85) return { label: '优秀', color: '#2f8f5b' }
  if (s >= 70) return { label: '良好', color: '#2c5d8a' }
  if (s >= 60) return { label: '合格', color: '#c69a4b' }
  return { label: '待提升', color: '#c0392b' }
})
function optText(q: TrainingQuestion, key: string): string {
  if (isJudge(q)) return judgeText(key)
  const o = (q.options || []).find((x) => x.key === key)
  return o ? `${o.key}. ${o.text}` : key
}
function reportMarkdown(): string {
  if (!report.value) return ''
  const s = report.value.session
  const lines: string[] = [`# 豫章书院 · 答题成绩单`, '']
  lines.push(`- 科目：${s.topic || '综合'}　难度：${s.difficulty}　题量：${s.question_count}`)
  lines.push(`- 总分：${s.total_score ?? 0} / 100（${scoreLevel.value.label}）`)
  lines.push(`- 时间：${new Date(s.updated_at).toLocaleString()}`, '')
  reportOrdered.value.forEach((r, i) => {
    lines.push(`## 第 ${i + 1} 题（${r.score} / ${r.q!.max_score} 分 · ${TYPE_LABEL[r.q!.question_type] || ''}）`, '')
    lines.push(`**题目**：${r.q!.question}`)
    if (isJudge(r.q!)) lines.push(`\n选项：${JUDGE_OPTS.map((o) => o.text).join('　')}`)
    else if (r.q!.options?.length) lines.push(`\n选项：${r.q!.options.map((o) => `${o.key}.${o.text}`).join('　')}`)
    lines.push('', `**我的作答**：${r.answer || '（未作答）'}`, '')
    lines.push(`**参考答案**：${r.q!.reference_answer}`, '')
    lines.push(`**点评**：${r.feedback}`, '', `**建议**：${r.suggestion}`, '')
  })
  return lines.join('\n')
}
function download() {
  const blob = new Blob([reportMarkdown()], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `豫章书院_成绩单_${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}
function print() { window.print() }
</script>

<template>
  <div class="tr">
    <!-- 选科目 + 难度 -->
    <template v-if="step === 'pick'">
      <div class="tr__hero">
        <div class="shell">
          <p class="eyebrow">书院答题</p>
          <h1 class="h-serif">选择科目，开始考试</h1>
          <p class="tr__lead">题目均由书院题库精选，含单选、判断、简答与论述。选定科目与难度，即可开卷。</p>
        </div>
      </div>

      <div class="shell pick">
        <p v-if="loadingSubjects" class="pick__hint">正在载入科目…</p>
        <p v-else-if="!subjects.length" class="pick__hint">题库暂未配置科目，请联系管理员在后台「题库管理」中添加。</p>

        <template v-else>
          <h3 class="pick__h">① 选择科目</h3>
          <div class="subjects">
            <button
              v-for="s in subjects"
              :key="s.subject"
              class="subj"
              :class="{ 'is-on': pick.subject === s.subject }"
              @click="pick.subject = s.subject"
            >
              <span class="subj__name h-serif">{{ s.subject }}</span>
            </button>
          </div>

          <h3 class="pick__h">② 选择难度</h3>
          <div class="diffs">
            <button
              v-for="d in diffOptions"
              :key="d.value"
              class="diff"
              :class="{ 'is-on': pick.difficulty === d.value }"
              @click="pick.difficulty = d.value"
            >
              <strong>{{ d.label }}</strong>
            </button>
          </div>

          <div class="pick__go">
            <p class="pick__avail">每卷固定 {{ EXAM_SIZE }} 题　·　单选/判断即时判分，简答/论述 AI 批阅</p>
            <button class="btn-solid pick__btn" :disabled="!canStart" @click="start">
              {{ busy ? '组卷中…' : '开始考试' }}
            </button>
            <p v-if="availForPick === 0 && pick.subject" class="pick__warn">该难度暂无题目，请换个难度或科目。</p>
            <p v-if="error" class="pick__warn">{{ error }}</p>
          </div>

          <!-- 历史答题记录 -->
          <div v-if="history.length" class="hist">
            <h3 class="pick__h">历史答题记录</h3>
            <button v-for="h in history" :key="h.id" class="hrec" @click="openRecord(h.id)">
              <div class="hrec__main">
                <strong>{{ h.title }}</strong>
                <small>{{ new Date(h.updated_at).toLocaleString() }}</small>
              </div>
              <span class="hrec__score" :style="{ color: (h.total_score ?? 0) >= 60 ? '#2f8f5b' : '#c0392b' }">
                {{ h.total_score ?? 0 }} 分
              </span>
            </button>
          </div>
        </template>
      </div>
    </template>

    <!-- 答卷 -->
    <div v-else-if="step === 'answer'" class="shell exam">
      <div class="exam__paper print-area">
        <header class="paper__head">
          <h1 class="h-serif">豫章书院 · {{ report?.session.topic || pick.subject }}测验</h1>
          <p class="paper__meta">
            难度 {{ diffOptions.find((d) => d.value === pick.difficulty)?.label }}　·　共 {{ questions.length }} 题　·　满分 {{ totalScoreMax }} 分
          </p>
          <p class="paper__tip no-print">单选/判断即时判分，简答/论述由书院 AI 批阅。作答后点「交卷」。</p>
        </header>

        <section v-for="(sec, si) in examSections" :key="sec.type" class="qsec">
          <h2 class="qsec__h">{{ CN_NUM[si] || si + 1 }}、{{ sec.label }}<small>（每题 {{ sec.max }} 分，共 {{ sec.items.length }} 题）</small></h2>

          <article v-for="q in sec.items" :id="`q-${q.id}`" :key="q.id" class="q">
            <header class="q__head">
              <span class="q__no">{{ numById[q.id] }}</span>
              <div class="q__title">
                <span class="q__type">{{ TYPE_LABEL[q.question_type] || q.question_type }} · {{ q.max_score }}分</span>
                <p class="q__text">{{ q.question }}</p>
              </div>
            </header>

            <div v-if="isChoice(q)" class="opts">
              <label v-for="o in q.options || []" :key="o.key" class="opt" :class="{ 'is-on': answers[q.id] === o.key }">
                <input type="radio" :name="`q${q.id}`" :value="o.key" v-model="answers[q.id]" />
                <span class="opt__key">{{ o.key }}</span><span class="opt__text">{{ o.text }}</span>
              </label>
            </div>
            <div v-else-if="isJudge(q)" class="opts opts--judge">
              <label v-for="o in JUDGE_OPTS" :key="o.key" class="opt" :class="{ 'is-on': answers[q.id] === o.key }">
                <input type="radio" :name="`q${q.id}`" :value="o.key" v-model="answers[q.id]" />
                <span class="opt__text opt__text--single">{{ o.text }}</span>
              </label>
            </div>
            <textarea v-else v-model="answers[q.id]" class="q__input" rows="4" placeholder="在此作答…" />
          </article>
        </section>
      </div>

      <!-- 答题卡 -->
      <aside class="card no-print">
        <h3 class="card__h">答题卡</h3>
        <p class="card__sub">已答 {{ answeredCount }} / {{ questions.length }}</p>
        <div class="card__grid">
          <button
            v-for="q in orderedQuestions"
            :key="q.id"
            class="card__n"
            :class="{ 'is-done': (answers[q.id] || '').trim() }"
            @click="scrollToQ(q.id)"
          >{{ numById[q.id] }}</button>
        </div>
        <button class="btn-navy card__submit" :disabled="busy" @click="submit">交卷批改</button>
        <button class="card__quit" @click="restart">放弃本卷</button>
        <p v-if="error" class="pick__warn">{{ error }}</p>
      </aside>
    </div>

    <!-- 成绩单 -->
    <div v-else-if="step === 'report' && report" class="shell exam">
      <div class="report print-area">
        <div class="report__top">
          <div class="gauge" :style="{ '--c': scoreLevel.color, '--p': totalScore }">
            <strong>{{ totalScore }}</strong><small>/ 100</small>
          </div>
          <div class="report__sum">
            <p class="eyebrow" :style="{ color: scoreLevel.color }">{{ scoreLevel.label }}</p>
            <h2 class="h-serif">{{ report.session.title }}</h2>
            <p class="report__meta">科目 {{ report.session.topic || '综合' }} · 难度 {{ report.session.difficulty }} · {{ report.session.question_count }} 题</p>
            <div class="report__btns no-print">
              <button class="btn-gold" @click="download">下载成绩单</button>
              <button class="btn-outline" @click="print">打印 / 存为 PDF</button>
              <button class="btn-outline" @click="restart">再考一次</button>
            </div>
          </div>
        </div>

        <section v-for="(sec, si) in reportSections" :key="sec.type" class="qsec">
          <h2 class="qsec__h">{{ CN_NUM[si] || si + 1 }}、{{ sec.label }}</h2>
          <article v-for="r in sec.items" :key="r.id" class="rcard">
            <header class="rcard__head">
              <span class="rcard__no">第 {{ reportNumById[r.q!.id] }} 题 · {{ TYPE_LABEL[r.q!.question_type] || '' }}</span>
              <span class="rcard__score" :style="{ color: r.score >= r.q!.max_score * 0.6 ? '#2f8f5b' : '#c0392b' }">{{ r.score }} / {{ r.q!.max_score }}</span>
            </header>
            <p class="rcard__q">{{ r.q!.question }}</p>
            <p v-if="isJudge(r.q!)" class="rcard__opts"><span v-for="o in JUDGE_OPTS" :key="o.key">{{ o.text }}　</span></p>
            <p v-else-if="r.q!.options?.length" class="rcard__opts"><span v-for="o in r.q!.options" :key="o.key">{{ o.key }}.{{ o.text }}　</span></p>
            <div class="rcard__block"><b>我的作答</b><p>{{ r.q!.options?.length ? optText(r.q!, r.answer) : (r.answer || '（未作答）') }}</p></div>
            <div class="rcard__block"><b>参考答案</b><p>{{ r.q!.options?.length ? optText(r.q!, r.q!.reference_answer) : r.q!.reference_answer }}</p></div>
            <div class="rcard__block rcard__block--fb"><b>点评</b><p>{{ r.feedback }}</p></div>
            <div class="rcard__block rcard__block--sg"><b>建议</b><p>{{ r.suggestion }}</p></div>
          </article>
        </section>
      </div>
    </div>

    <!-- 忙碌遮罩 -->
    <Teleport to="body">
      <div v-if="busy" class="mask">
        <span class="spinner" /><p>{{ busyText }}</p>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.tr { background: var(--bg); min-height: 100%; }
.tr__hero {
  padding: 46px 0 30px;
  background: radial-gradient(circle at 88% 0%, rgba(237, 183, 79, 0.12), transparent 42%), linear-gradient(180deg, #fff, var(--bg));
}
.tr__hero h1 { margin: 12px 0 0; font-size: clamp(26px, 3.6vw, 38px); font-weight: 800; color: var(--ink); }
.tr__lead { margin-top: 14px; max-width: 720px; color: var(--sub); line-height: 1.85; }

/* 选科目 */
.pick { padding: 12px 0 72px; }
.pick__hint { padding: 50px 0; text-align: center; color: var(--muted); }
.pick__h { margin: 26px 0 14px; font-size: 16px; font-weight: 800; color: var(--ink); }
.subjects { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; }
.subj {
  display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
  padding: 20px; border-radius: 14px; border: 1px solid var(--line); background: var(--panel);
  box-shadow: var(--shadow-soft); transition: all 0.2s var(--ease);
}
.subj:hover { transform: translateY(-4px); box-shadow: var(--shadow-lift); }
.subj.is-on { border-color: var(--navy); box-shadow: 0 0 0 2px var(--navy), var(--shadow-soft); }
.subj__name { font-size: 20px; font-weight: 800; color: var(--ink); }
.subj__count { font-size: 13px; color: var(--gold-deep); font-weight: 700; }

.diffs { display: flex; gap: 12px; flex-wrap: wrap; }
.diff {
  flex: 1 1 120px; display: flex; flex-direction: column; gap: 4px; align-items: center;
  padding: 16px; border-radius: 12px; border: 1px solid var(--line); background: var(--panel); transition: all 0.18s var(--ease);
}
.diff strong { font-size: 16px; color: var(--ink); }
.diff small { font-size: 12px; color: var(--muted); }
.diff.is-on { border-color: var(--navy); background: rgba(44, 62, 80, 0.07); }
.diff.is-on strong { color: var(--navy); }

.pick__go { margin-top: 28px; text-align: center; }
.pick__avail { color: var(--sub); font-size: 14px; }
.pick__btn { margin-top: 14px; font-size: 17px; padding: 14px 44px; }
.pick__warn { margin-top: 10px; color: var(--red); font-size: 13.5px; }

.hist { margin-top: 40px; max-width: 640px; }
.hrec {
  width: 100%;
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 14px 18px; margin-bottom: 10px;
  border-radius: 12px; border: 1px solid var(--line); background: var(--panel); box-shadow: var(--shadow-soft);
  transition: all 0.18s var(--ease);
}
.hrec:hover { transform: translateX(3px); border-color: var(--navy); }
.hrec__main { display: flex; flex-direction: column; gap: 3px; text-align: left; }
.hrec__main strong { font-size: 15px; color: var(--ink); }
.hrec__main small { font-size: 12px; color: var(--muted); }
.hrec__score { font-size: 18px; font-weight: 900; flex: none; }

/* 答卷布局 */
.exam { display: grid; grid-template-columns: 1fr 220px; gap: 24px; align-items: start; padding: 32px 0 72px; }
.exam__paper, .report {
  background: #fff; border: 1px solid var(--line); border-radius: 14px; box-shadow: var(--shadow-soft); padding: 36px 40px;
}
.paper__head { text-align: center; padding-bottom: 22px; margin-bottom: 22px; border-bottom: 2px solid var(--navy); }
.paper__head h1 { font-size: clamp(22px, 3vw, 30px); font-weight: 800; color: var(--ink); }
.paper__meta { margin-top: 10px; color: var(--sub); font-size: 14.5px; }
.paper__tip { margin-top: 8px; color: var(--muted); font-size: 12.5px; }

.qsec { margin-top: 6px; }
.qsec + .qsec { margin-top: 18px; }
.qsec__h {
  display: flex; align-items: baseline; gap: 8px;
  margin: 18px 0 4px; padding-bottom: 8px;
  font-family: var(--font-serif); font-size: 19px; font-weight: 800; color: var(--navy);
  border-bottom: 1px solid var(--line);
}
.qsec__h small { font-size: 13px; font-weight: 600; color: var(--muted); }
.q { padding: 20px 0; border-bottom: 1px dashed var(--line); }
.q:last-child { border-bottom: 0; }
.q__head { display: flex; gap: 12px; }
.q__no { flex: none; display: grid; place-items: center; height: 28px; width: 28px; border-radius: 8px; background: var(--navy); color: #fff; font-weight: 800; }
.q__type { font-size: 12px; color: var(--gold-deep); font-weight: 700; }
.q__text { margin-top: 4px; font-size: 16px; font-weight: 600; color: var(--ink); line-height: 1.7; }
.q__input { width: 100%; margin-top: 12px; padding: 12px; border-radius: 12px; border: 1px solid var(--line); background: var(--bg); font-size: 14.5px; line-height: 1.7; color: var(--ink); resize: vertical; }
.q__input:focus { outline: none; border-color: var(--navy); }
.opts { margin-top: 12px; padding-left: 40px; display: flex; flex-direction: column; gap: 9px; }
.opts--judge { flex-direction: row; }
.opt { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--bg); cursor: pointer; transition: all 0.16s var(--ease); }
.opts--judge .opt { flex: 1; }
.opt:hover { border-color: var(--navy); }
.opt.is-on { border-color: var(--navy); background: rgba(44, 62, 80, 0.07); }
.opt input { accent-color: var(--navy); }
.opt__key { display: grid; place-items: center; height: 24px; width: 24px; border-radius: 6px; background: #fff; border: 1px solid var(--line); font-weight: 800; font-size: 13px; color: var(--navy); }
.opt.is-on .opt__key { background: var(--navy); color: #fff; border-color: var(--navy); }
.opt__text { font-size: 14.5px; color: var(--ink); }

/* 答题卡 */
.card { position: sticky; top: calc(var(--header-h) + 16px); padding: 18px; border-radius: 14px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.card__h { font-weight: 800; color: var(--ink); }
.card__sub { margin: 4px 0 12px; font-size: 12.5px; color: var(--muted); }
.card__grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; }
.card__n { height: 34px; border-radius: 8px; border: 1px solid var(--line); background: #fff; font-size: 13px; font-weight: 700; color: var(--sub); transition: all 0.15s var(--ease); }
.card__n:hover { border-color: var(--navy); }
.card__n.is-done { background: var(--navy); color: #fff; border-color: var(--navy); }
.card__submit { width: 100%; margin-top: 16px; }
.card__quit { width: 100%; margin-top: 8px; padding: 8px; font-size: 12.5px; color: var(--muted); }
.card__quit:hover { color: var(--red); }

/* 成绩单 */
.report__top { display: flex; gap: 26px; align-items: center; padding-bottom: 22px; margin-bottom: 18px; border-bottom: 2px solid var(--navy); }
.gauge { flex: none; display: grid; place-items: center; height: 118px; width: 118px; border-radius: 50%; background: conic-gradient(var(--c) calc(var(--p, 0) * 1%), var(--line) 0); position: relative; }
.gauge::before { content: ''; position: absolute; inset: 9px; border-radius: 50%; background: #fff; }
.gauge strong { position: relative; font-size: 34px; font-weight: 900; color: var(--c); line-height: 1; }
.gauge small { position: relative; font-size: 12px; color: var(--muted); }
.report__sum h2 { margin: 4px 0 6px; font-size: 24px; font-weight: 800; color: var(--ink); }
.report__meta { color: var(--sub); font-size: 13.5px; }
.report__btns { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.rcard { padding: 20px 0; border-bottom: 1px dashed var(--line); }
.rcard:last-child { border-bottom: 0; }
.rcard__head { display: flex; align-items: center; justify-content: space-between; }
.rcard__no { font-family: var(--font-serif); font-weight: 800; color: var(--navy); }
.rcard__score { font-size: 18px; font-weight: 900; }
.rcard__q { margin: 10px 0 8px; font-size: 16px; font-weight: 600; color: var(--ink); line-height: 1.6; }
.rcard__opts { margin-bottom: 12px; font-size: 13.5px; color: var(--sub); }
.rcard__block { margin-top: 10px; padding: 12px 14px; border-radius: 12px; background: var(--bg); }
.rcard__block b { display: block; margin-bottom: 5px; font-size: 12.5px; color: var(--muted); }
.rcard__block p { font-size: 14.5px; line-height: 1.75; color: var(--ink); white-space: pre-wrap; }
.rcard__block--fb { background: rgba(44, 93, 138, 0.07); }
.rcard__block--sg { background: rgba(198, 154, 75, 0.1); }

.mask { position: fixed; inset: 0; z-index: 80; display: grid; place-items: center; gap: 14px; background: rgba(15, 23, 33, 0.4); color: #fff; }
.mask p { color: #fff; }
.spinner { height: 42px; width: 42px; border-radius: 50%; border: 3px solid rgba(255, 255, 255, 0.3); border-top-color: var(--gold); animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .exam { grid-template-columns: 1fr; }
  .card { position: static; order: -1; }
  .card__grid { grid-template-columns: repeat(10, 1fr); }
  .exam__paper, .report { padding: 24px 18px; }
  .opts { padding-left: 0; }
}
@media print {
  .exam { display: block; }
  .exam__paper, .report { border: 0; box-shadow: none; padding: 0; }
}
</style>
