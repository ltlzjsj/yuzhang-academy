<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { listKBs, type KnowledgeBase } from '@/api/kb'
import {
  buildQuestionBank,
  listQuestionBank,
  deleteBankItem,
  listSubjects,
  type BankItem,
  type Subject,
} from '@/api/training'

const PAGE = 20

const kbs = ref<KnowledgeBase[]>([])
const subjects = ref<Subject[]>([])
const items = ref<BankItem[]>([])
const total = ref(0)
const page = ref(0)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE)))
const loading = ref(false)
const buildBusy = ref(false)
const msg = ref('')
const error = ref('')

const filterKb = ref<number | 'all'>('all')
const form = reactive({
  kb_ids: [] as number[],
  topic: '',
  question_type: 'mixed',
  difficulty: 'normal',
  count: 10,
})

const typeOptions = [
  { value: 'mixed', label: '综合' },
  { value: 'single_choice', label: '单选' },
  { value: 'judge', label: '判断' },
  { value: 'short_answer', label: '简答' },
  { value: 'essay', label: '论述' },
]
const TYPE_LABEL: Record<string, string> = {
  single_choice: '单选', judge: '判断', short_answer: '简答', essay: '论述', compare: '辨析', mixed: '综合',
}
const kbName = (id: number) => kbs.value.find((k) => k.id === id)?.name || `#${id}`
const canBuild = computed(() => form.kb_ids.length > 0 && !buildBusy.value)

function toggleKb(id: number) {
  const i = form.kb_ids.indexOf(id)
  if (i >= 0) form.kb_ids.splice(i, 1)
  else form.kb_ids.push(id)
}

async function load() {
  loading.value = true
  try {
    const params: any = { limit: PAGE, offset: page.value * PAGE }
    if (filterKb.value !== 'all') params.kb_id = filterKb.value
    const res = await listQuestionBank(params)
    items.value = res.items
    total.value = res.total
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadSubjects() {
  try {
    subjects.value = await listSubjects()
  } catch {
    subjects.value = []
  }
}

function reload() {
  page.value = 0
  load()
}
function prev() {
  if (page.value > 0) {
    page.value--
    load()
  }
}
function next() {
  if ((page.value + 1) * PAGE < total.value) {
    page.value++
    load()
  }
}

async function build() {
  if (!canBuild.value) return
  error.value = ''
  msg.value = ''
  buildBusy.value = true
  try {
    const r = await buildQuestionBank({ ...form })
    msg.value = `已新增 ${r.added} 题，题库现有 ${r.total} 题`
    await loadSubjects()
    reload()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '扩充题库失败'
  } finally {
    buildBusy.value = false
  }
}

async function remove(id: number) {
  if (!confirm('删除这道题库题？')) return
  await deleteBankItem(id)
  items.value = items.value.filter((i) => i.id !== id)
  total.value = Math.max(0, total.value - 1)
}

onMounted(async () => {
  try {
    kbs.value = await listKBs()
  } catch {
    kbs.value = []
  }
  await loadSubjects()
  await load()
})
</script>

<template>
  <div class="bank">
    <div class="bank__head">
      <h2 class="h-serif">题库管理</h2>
      <p>预先用 AI 出题入库，答题培训出卷时即可秒速命中，无需每次现场调用大模型。</p>
    </div>

    <div class="bank__grid">
      <!-- 扩充题库 -->
      <aside class="build">
        <h3>扩充题库</h3>
        <label class="build__lbl">知识库（可多选）</label>
        <div class="chips">
          <button v-for="kb in kbs" :key="kb.id" class="chip" :class="{ 'is-on': form.kb_ids.includes(kb.id) }" @click="toggleKb(kb.id)">
            {{ kb.name }}<span v-if="kb.is_public" class="chip__pub">公开</span>
          </button>
          <p v-if="!kbs.length" class="muted">暂无知识库</p>
        </div>

        <label class="build__lbl">科目（学生按此选择，建议填写）</label>
        <div v-if="subjects.length" class="subjpick">
          <button
            v-for="s in subjects"
            :key="s.subject"
            class="subjpick__c"
            :class="{ 'is-on': form.topic === s.subject }"
            @click="form.topic = s.subject"
          >{{ s.subject }}<small>{{ s.total }}</small></button>
        </div>
        <input v-model="form.topic" class="field" placeholder="点选上方已有科目，或填写新科目名" />

        <label class="build__lbl">题型</label>
        <select v-model="form.question_type" class="field">
          <option v-for="o in typeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>

        <label class="build__lbl">难度</label>
        <select v-model="form.difficulty" class="field">
          <option value="easy">基础</option>
          <option value="normal">进阶</option>
          <option value="hard">挑战</option>
        </select>

        <label class="build__lbl">数量：{{ form.count }}</label>
        <input v-model.number="form.count" type="range" min="1" max="30" class="range" />

        <button class="btn-navy build__go" :disabled="!canBuild" @click="build">
          {{ buildBusy ? 'AI 出题中…' : '扩充题库' }}
        </button>
        <p v-if="msg" class="ok">{{ msg }}</p>
        <p v-if="error" class="err">{{ error }}</p>
      </aside>

      <!-- 题库列表 -->
      <section class="list">
        <div class="list__bar">
          <div class="list__filter">
            <span>筛选知识库：</span>
            <select v-model="filterKb" class="field field--sm" @change="reload">
              <option value="all">全部</option>
              <option v-for="kb in kbs" :key="kb.id" :value="kb.id">{{ kb.name }}</option>
            </select>
          </div>
          <span class="list__total">共 {{ total }} 题</span>
        </div>

        <p v-if="loading" class="muted">加载中…</p>
        <p v-else-if="!items.length" class="muted">题库为空，先在左侧扩充。</p>

        <article v-for="it in items" :key="it.id" class="item">
          <div class="item__main">
            <div class="item__tags">
              <span class="tag tag--type">{{ TYPE_LABEL[it.question_type] || it.question_type }}</span>
              <span class="tag">{{ it.difficulty }}</span>
              <span class="tag tag--kb">{{ kbName(it.kb_id) }}</span>
              <span v-if="it.topic" class="tag tag--topic">{{ it.topic }}</span>
            </div>
            <p class="item__q">{{ it.question }}</p>
            <p v-if="it.options?.length" class="item__opts">{{ it.options.map((o) => `${o.key}.${o.text}`).join('　') }}</p>
            <p class="item__ans"><b>参考答案：</b>{{ it.reference_answer }}</p>
          </div>
          <button class="item__del" title="删除" @click="remove(it.id)">✕</button>
        </article>

        <div v-if="total > PAGE" class="pager">
          <button :disabled="page === 0" @click="prev">‹ 上一页</button>
          <span>第 {{ page + 1 }} / {{ pageCount }} 页</span>
          <button :disabled="(page + 1) * PAGE >= total" @click="next">下一页 ›</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.bank { padding: 24px; }
.bank__head h2 { font-family: var(--font-serif); font-size: 24px; font-weight: 800; color: var(--ink); }
.bank__head p { margin-top: 6px; color: var(--sub); font-size: 14px; }
.bank__grid { margin-top: 22px; display: grid; grid-template-columns: 300px 1fr; gap: 22px; align-items: start; }

.build { position: sticky; top: 16px; padding: 20px; border-radius: 14px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.build h3 { font-weight: 800; color: var(--ink); }
.build__lbl { display: block; margin: 16px 0 7px; font-size: 13px; font-weight: 700; color: var(--sub); }
.chips { display: flex; flex-wrap: wrap; gap: 7px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--line); background: #fff; font-size: 13px; color: var(--sub); }
.chip.is-on { background: var(--navy); border-color: var(--navy); color: #fff; }
.chip__pub { font-size: 10px; padding: 1px 5px; border-radius: 5px; background: rgba(47, 143, 91, 0.15); color: #2f8f5b; }
.chip.is-on .chip__pub { background: rgba(255, 255, 255, 0.25); color: #fff; }
.field--sm { width: auto; display: inline-block; padding: 6px 10px; }
.range { width: 100%; accent-color: var(--navy); }
.build__go { width: 100%; margin-top: 18px; }
.ok { margin-top: 10px; color: #2f8f5b; font-size: 13px; }
.err { margin-top: 10px; color: var(--red); font-size: 13px; }
.muted { color: var(--muted); font-size: 13.5px; padding: 12px 0; }
.subjpick { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.subjpick__c {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 999px; border: 1px solid var(--line); background: #fff; font-size: 12.5px; color: var(--sub);
}
.subjpick__c small { font-size: 10px; padding: 0 5px; border-radius: 5px; background: var(--bg); color: var(--muted); }
.subjpick__c.is-on { background: var(--gold); border-color: var(--gold); color: var(--navy-deep); }
.subjpick__c.is-on small { background: rgba(255, 255, 255, 0.35); color: var(--navy-deep); }
.pager { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; font-size: 13.5px; color: var(--sub); }
.pager button { padding: 7px 14px; border-radius: 8px; border: 1px solid var(--line); background: #fff; color: var(--navy); font-weight: 600; }
.pager button:disabled { opacity: 0.45; cursor: not-allowed; }
.pager button:not(:disabled):hover { border-color: var(--navy); }

.list__bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.list__filter { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--sub); }
.list__total { color: var(--muted); font-size: 13px; }
.item { display: flex; gap: 12px; padding: 16px; margin-bottom: 10px; border-radius: 12px; background: var(--panel); border: 1px solid var(--line); }
.item__main { flex: 1; min-width: 0; }
.item__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.tag { padding: 2px 8px; border-radius: 6px; background: var(--bg); color: var(--muted); font-size: 11.5px; }
.tag--type { background: rgba(44, 62, 80, 0.1); color: var(--navy); font-weight: 700; }
.tag--kb { background: rgba(237, 183, 79, 0.16); color: var(--gold-deep); }
.tag--topic { background: rgba(44, 93, 138, 0.1); color: var(--blue); }
.item__q { font-size: 15px; font-weight: 600; color: var(--ink); line-height: 1.55; }
.item__opts { margin-top: 6px; font-size: 13px; color: var(--sub); }
.item__ans { margin-top: 6px; font-size: 13px; color: var(--muted); }
.item__ans b { color: var(--sub); }
.item__del { flex: none; height: 30px; width: 30px; border-radius: 8px; color: var(--muted); font-size: 14px; }
.item__del:hover { background: rgba(192, 57, 43, 0.1); color: var(--red); }

@media (max-width: 880px) {
  .bank__grid { grid-template-columns: 1fr; }
  .build { position: static; }
}
</style>
