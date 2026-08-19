<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createActivity,
  deleteActivity,
  listActivities,
  updateActivity,
  type Activity,
  type ActivityInput,
  type ActivityStatus,
} from '@/api/activities'

const rows = ref<Activity[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const editingId = ref<number | null>(null)
const showForm = ref(false)

const categories = ['书院公告', '讲会论道', '研学体验', '文化交流']
const statuses: { v: ActivityStatus; label: string }[] = [
  { v: 'open', label: '报名中' },
  { v: 'ongoing', label: '进行中' },
  { v: 'closed', label: '已结束' },
]
const statusLabel = (s: ActivityStatus) => statuses.find((x) => x.v === s)?.label ?? s

function blankForm(): ActivityInput & { highlightsText: string } {
  return {
    category: '书院公告',
    title: '',
    summary: '',
    body: '',
    event_date: '',
    period: '',
    place: '',
    audience: '',
    status: 'open',
    highlights: [],
    highlightsText: '',
    image: '',
    is_published: true,
    sort_order: 0,
  }
}
const form = reactive(blankForm())

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await listActivities({ include_unpublished: true })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, blankForm())
  editingId.value = null
  showForm.value = true
}
function openEdit(a: Activity) {
  Object.assign(form, {
    category: a.category,
    title: a.title,
    summary: a.summary,
    body: a.body,
    event_date: a.event_date,
    period: a.period,
    place: a.place,
    audience: a.audience,
    status: a.status,
    highlights: a.highlights || [],
    highlightsText: (a.highlights || []).join('\n'),
    image: a.image,
    is_published: a.is_published,
    sort_order: a.sort_order,
  })
  editingId.value = a.id
  showForm.value = true
}

async function save() {
  if (!form.title.trim()) {
    error.value = '请填写标题'
    return
  }
  saving.value = true
  error.value = ''
  const payload: ActivityInput = {
    category: form.category,
    title: form.title.trim(),
    summary: form.summary,
    body: form.body,
    event_date: form.event_date,
    period: form.period,
    place: form.place,
    audience: form.audience,
    status: form.status,
    highlights: form.highlightsText.split('\n').map((s) => s.trim()).filter(Boolean),
    image: form.image,
    is_published: form.is_published,
    sort_order: Number(form.sort_order) || 0,
  }
  try {
    if (editingId.value == null) await createActivity(payload)
    else await updateActivity(editingId.value, payload)
    showForm.value = false
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(a: Activity) {
  if (!confirm(`确定删除活动「${a.title}」？`)) return
  try {
    await deleteActivity(a.id)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '删除失败'
  }
}

async function togglePublish(a: Activity) {
  try {
    await updateActivity(a.id, { is_published: !a.is_published })
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '操作失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="mng">
    <div class="mng__head">
      <div>
        <h2>活动资讯管理</h2>
        <p>维护公开官网「活动资讯」页与首页动态展示的内容。</p>
      </div>
      <button class="btn-navy" @click="openCreate">+ 新建活动</button>
    </div>

    <p v-if="error" class="alert">{{ error }}</p>

    <div class="surface tablewrap">
      <table>
        <thead>
          <tr>
            <th>排序</th>
            <th>标题</th>
            <th>分类</th>
            <th>状态</th>
            <th>时间</th>
            <th>发布</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="7" class="muted">加载中…</td></tr>
          <tr v-else-if="!rows.length"><td colspan="7" class="muted">暂无活动，点击右上角「新建活动」。</td></tr>
          <tr v-for="a in rows" :key="a.id">
            <td>{{ a.sort_order }}</td>
            <td class="cell-title">{{ a.title }}</td>
            <td><span class="chip">{{ a.category }}</span></td>
            <td><span class="chip" :class="`st-${a.status}`">{{ statusLabel(a.status) }}</span></td>
            <td class="muted">{{ a.period || a.event_date || '—' }}</td>
            <td>
              <button class="toggle" :class="{ on: a.is_published }" @click="togglePublish(a)">
                {{ a.is_published ? '已发布' : '草稿' }}
              </button>
            </td>
            <td class="actions">
              <button class="link" @click="openEdit(a)">编辑</button>
              <button class="link link--danger" @click="remove(a)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 表单弹窗 -->
    <div v-if="showForm" class="dlg" @click.self="showForm = false">
      <div class="dlg__panel surface">
        <header class="dlg__head">
          <h3>{{ editingId == null ? '新建活动' : '编辑活动' }}</h3>
          <button class="dlg__close" @click="showForm = false">✕</button>
        </header>
        <div class="dlg__body">
          <label class="fld fld--full">
            <span>标题 *</span>
            <input v-model="form.title" class="field" placeholder="活动标题" />
          </label>
          <label class="fld">
            <span>分类</span>
            <select v-model="form.category" class="field">
              <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <label class="fld">
            <span>状态</span>
            <select v-model="form.status" class="field">
              <option v-for="s in statuses" :key="s.v" :value="s.v">{{ s.label }}</option>
            </select>
          </label>
          <label class="fld fld--full">
            <span>摘要（列表卡片显示）</span>
            <input v-model="form.summary" class="field" placeholder="一句话摘要" />
          </label>
          <label class="fld fld--full">
            <span>正文（详情弹窗显示）</span>
            <textarea v-model="form.body" class="field" rows="4" placeholder="活动详细介绍" />
          </label>
          <label class="fld"><span>发布日期</span><input v-model="form.event_date" class="field" placeholder="2026-04-01" /></label>
          <label class="fld"><span>时间</span><input v-model="form.period" class="field" placeholder="每周六 14:30 / 长期开放" /></label>
          <label class="fld"><span>地点</span><input v-model="form.place" class="field" placeholder="豫章书院 · 明伦堂" /></label>
          <label class="fld"><span>对象</span><input v-model="form.audience" class="field" placeholder="高校师生 / 社会公众" /></label>
          <label class="fld fld--full">
            <span>活动亮点（每行一条）</span>
            <textarea v-model="form.highlightsText" class="field" rows="3" placeholder="名家主讲&#10;现场会讲问难" />
          </label>
          <label class="fld fld--full">
            <span>封面图（书院资源相对路径，或以 http/ 开头的完整地址）</span>
            <input v-model="form.image" class="field" placeholder="组织画家绘制了十大书院事件图/省会豫章书院的设立.jpg" />
          </label>
          <label class="fld"><span>排序（大在前）</span><input v-model="form.sort_order" type="number" class="field" /></label>
          <label class="fld fld--check">
            <input v-model="form.is_published" type="checkbox" />
            <span>发布（在官网展示）</span>
          </label>
        </div>
        <footer class="dlg__foot">
          <button class="btn-outline" @click="showForm = false">取消</button>
          <button class="btn-navy" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mng { padding: 24px; max-width: 1100px; margin: 0 auto; }
.mng__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.mng__head h2 { font-family: var(--font-serif); font-size: 22px; font-weight: 800; color: var(--ink); }
.mng__head p { margin-top: 6px; color: var(--muted); font-size: 14px; }
.alert { margin-bottom: 14px; padding: 10px 14px; border-radius: 10px; background: rgba(231, 76, 60, 0.1); color: var(--red-deep); font-size: 14px; }

.tablewrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 14px; text-align: left; font-size: 14px; border-bottom: 1px solid var(--line); }
th { background: var(--bg); color: var(--sub); font-weight: 700; white-space: nowrap; }
.cell-title { font-weight: 600; color: var(--ink); max-width: 320px; }
.muted { color: var(--muted); }
.actions { white-space: nowrap; }
.chip { display: inline-block; padding: 3px 10px; border-radius: 999px; background: rgba(44, 62, 80, 0.08); color: var(--navy); font-size: 12.5px; font-weight: 600; }
.chip.st-open { background: rgba(231, 76, 60, 0.12); color: var(--red-deep); }
.chip.st-ongoing { background: rgba(47, 143, 91, 0.14); color: #2f8f5b; }
.chip.st-closed { background: rgba(20, 30, 40, 0.08); color: var(--muted); }
.toggle { padding: 5px 12px; border-radius: 999px; border: 1px solid var(--line); font-size: 12.5px; color: var(--muted); }
.toggle.on { border-color: #2f8f5b; color: #2f8f5b; background: rgba(47, 143, 91, 0.08); }
.link { font-size: 13.5px; font-weight: 600; color: var(--navy); }
.link + .link { margin-left: 14px; }
.link--danger { color: var(--red); }

.dlg { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 24px; background: rgba(15, 23, 33, 0.55); }
.dlg__panel { width: min(640px, 100%); max-height: 90vh; display: flex; flex-direction: column; background: var(--panel); }
.dlg__head { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--line); }
.dlg__head h3 { font-family: var(--font-serif); font-size: 18px; font-weight: 800; color: var(--ink); }
.dlg__close { display: grid; place-items: center; height: 30px; width: 30px; border-radius: 50%; color: var(--sub); }
.dlg__close:hover { background: var(--bg); }
.dlg__body { padding: 20px 22px; overflow: auto; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.fld { display: flex; flex-direction: column; gap: 6px; }
.fld--full { grid-column: 1 / -1; }
.fld > span { font-size: 13px; font-weight: 600; color: var(--sub); }
.fld--check { flex-direction: row; align-items: center; gap: 8px; }
.fld--check span { font-weight: 600; }
textarea.field { resize: vertical; }
.dlg__foot { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 22px; border-top: 1px solid var(--line); }

@media (max-width: 620px) {
  .dlg__body { grid-template-columns: 1fr; }
}
</style>
