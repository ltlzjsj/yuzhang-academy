<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChunkViewer from '@/components/kb/ChunkViewer.vue'
import DocumentListPanel from '@/components/kb/DocumentListPanel.vue'
import QaControlPanel from '@/components/kb/QaControlPanel.vue'
import { useKBStore } from '@/stores/kb'
import {
  deleteQaPair,
  getDocQaStats,
  generateDocQA,
  generateKbQA,
  getKB,
  getKbQaStats,
  listChunks,
  listQaPairs,
  updateKB,
  type ChunkRow,
  type DocumentRow,
  type KnowledgeBase,
  type QaPair,
  type QaStats,
} from '@/api/kb'
import { fetchModels, type OllamaModel } from '@/api/models'

const route = useRoute()
const router = useRouter()
const kbStore = useKBStore()
const kbId = computed(() => Number(route.params.id))

const kb = ref<KnowledgeBase | null>(null)
const err = ref('')
const docs = computed<DocumentRow[]>(() => kbStore.docsByKb[kbId.value] || [])
const activeDocId = ref<number | null>(null)

const chunks = ref<ChunkRow[]>([])
const chunksLoading = ref(false)
const chunksTotal = ref(0)
const chunksPage = ref(1)
const pageSize = 20

const rightTab = ref<'chunks' | 'qa'>('chunks')
const qaItems = ref<QaPair[]>([])
const qaTotal = ref(0)
const qaPage = ref(1)
const qaLoading = ref(false)
const qaQuery = ref('')
const qaScope = ref<'doc' | 'kb'>('doc')

const qaStats = ref<QaStats | null>(null)
const docQaStats = ref<QaStats | null>(null)
const qaBusy = ref(false)
const qaToggleBusy = ref(false)
const qaMsg = ref('')
const models = ref<OllamaModel[]>([])
const defaultChatModel = ref('')
const qaModelSel = ref('')
const qaModelSaving = ref(false)

const uploading = ref(false)
const uploadProgress = ref(0)
const uploadErr = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const metadataRows = ref<Array<{ key: string; value: string }>>([])
const metadataSaving = ref(false)
const metadataMsg = ref('')

let pollTimer: number | null = null
let qaPollTimer: number | null = null

async function loadModels() {
  try {
    const resp = await fetchModels()
    models.value = resp.items || []
    defaultChatModel.value = resp.default_chat || ''
  } catch {
    models.value = []
  }
}

async function loadKB() {
  try {
    kb.value = await getKB(kbId.value)
  } catch (e: any) {
    err.value = e.response?.data?.detail || e.message
  }
}

async function loadQaStats() {
  try {
    qaStats.value = await getKbQaStats(kbId.value)
  } catch {
    qaStats.value = null
  }
}

async function loadDocQaStats() {
  if (!activeDocId.value) {
    docQaStats.value = null
    return
  }
  try {
    docQaStats.value = await getDocQaStats(activeDocId.value)
  } catch {
    docQaStats.value = null
  }
}

async function refresh() {
  await Promise.all([loadKB(), kbStore.loadDocs(kbId.value), loadQaStats()])
  await loadDocQaStats()
}

async function loadChunks() {
  if (!activeDocId.value) {
    chunks.value = []
    chunksTotal.value = 0
    return
  }
  chunksLoading.value = true
  try {
    const resp = await listChunks(activeDocId.value, chunksPage.value, pageSize)
    chunks.value = resp.items
    chunksTotal.value = resp.total
  } finally {
    chunksLoading.value = false
  }
}

function setChunksPage(page: number) {
  chunksPage.value = page
  loadChunks()
}

async function loadQaList() {
  if (rightTab.value !== 'qa') return
  qaLoading.value = true
  try {
    const resp = await listQaPairs({
      kb_id: kbId.value,
      document_id: qaScope.value === 'doc' ? activeDocId.value ?? undefined : undefined,
      q: qaQuery.value.trim() || undefined,
      page: qaPage.value,
      size: pageSize,
    })
    qaItems.value = resp.items
    qaTotal.value = resp.total
  } finally {
    qaLoading.value = false
  }
}

async function onToggleQa(v: boolean) {
  if (!kb.value || qaToggleBusy.value) return
  qaToggleBusy.value = true
  try {
    kb.value = await updateKB(kbId.value, { qa_enabled: v })
  } catch (e: any) {
    qaMsg.value = e.response?.data?.detail || e.message
  } finally {
    qaToggleBusy.value = false
  }
}

async function onChangeQaCount(v: number) {
  if (!kb.value) return
  try {
    kb.value = await updateKB(kbId.value, { qa_pairs_per_chunk: v })
  } catch (e: any) {
    qaMsg.value = e.response?.data?.detail || e.message
  }
}

async function onChangeQaModel(v: string) {
  if (!kb.value || qaModelSaving.value) return
  qaModelSaving.value = true
  try {
    kb.value = await updateKB(kbId.value, { qa_model: v || null } as any)
    qaModelSel.value = kb.value.qa_model || ''
    qaMsg.value = v ? `已保存 QA 模型：${v}` : '已清除 QA 模型，将使用默认模型'
  } catch (e: any) {
    qaMsg.value = e.response?.data?.detail || e.message
  } finally {
    qaModelSaving.value = false
  }
}

async function onGenerateKbQa() {
  if (!kb.value?.qa_enabled) {
    qaMsg.value = '请先启用 Q&A'
    return
  }
  qaBusy.value = true
  qaMsg.value = ''
  try {
    await generateKbQA(kbId.value, qaModelSel.value || undefined)
    qaMsg.value = `已入队：手动生成 Q&A（${qaModelSel.value || kb.value?.qa_model || defaultChatModel.value || 'default'}）`
    scheduleQaPoll()
    schedulePoll()
  } catch (e: any) {
    qaMsg.value = e.response?.data?.detail || e.message
  } finally {
    qaBusy.value = false
  }
}

async function onGenerateDocQa(doc: DocumentRow, e: Event) {
  e.stopPropagation()
  await generateQaForDoc(doc)
}

async function onGenerateSelectedDocQa() {
  if (!activeDoc.value) {
    qaMsg.value = '请先选择一篇文献'
    return
  }
  await generateQaForDoc(activeDoc.value)
}

async function generateQaForDoc(doc: DocumentRow) {
  if (!kb.value?.qa_enabled) {
    qaMsg.value = '请先启用 Q&A'
    return
  }
  qaBusy.value = true
  qaMsg.value = ''
  try {
    await generateDocQA(doc.id, qaModelSel.value || undefined)
    qaMsg.value = `已为《${doc.filename}》入队 Q&A 生成`
    scheduleQaPoll()
    schedulePoll()
  } catch (err: any) {
    qaMsg.value = err.response?.data?.detail || err.message
  } finally {
    qaBusy.value = false
  }
}

async function onDeleteQa(pair: QaPair) {
  if (!confirm('删除该 Q&A?')) return
  await deleteQaPair(pair.id)
  await loadQaList()
  await loadQaStats()
  await loadDocQaStats()
}

function scheduleQaPoll() {
  clearQaPoll()
  let ticks = 0
  qaPollTimer = window.setInterval(async () => {
    ticks += 1
    await loadQaStats()
    await loadDocQaStats()
    if (rightTab.value === 'qa') await loadQaList()
    if (ticks > 60) clearQaPoll()
  }, 2000)
}

function clearQaPoll() {
  if (qaPollTimer) {
    clearInterval(qaPollTimer)
    qaPollTimer = null
  }
}

function schedulePoll() {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    const busyDocs = docs.value.filter((d) =>
      ['pending', 'parsing', 'chunking', 'embedding', 'qa_generating'].includes(d.status),
    )
    if (!busyDocs.length) {
      clearPoll()
      return
    }
    for (const d of busyDocs) await kbStore.refreshDoc(d)
    await loadKB()
    if (activeDocId.value && docs.value.find((d) => d.id === activeDocId.value)?.status === 'done' && !chunks.value.length) {
      loadChunks()
    }
  }, 1500)
}

function clearPoll() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function onPickFile() {
  fileInput.value?.click()
}

async function onFile(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files || !files.length) return
  uploadErr.value = ''
  uploading.value = true
  uploadProgress.value = 0
  try {
    for (const f of Array.from(files)) {
      await kbStore.upload(kbId.value, f, (p) => (uploadProgress.value = p))
      uploadProgress.value = 0
    }
    await loadKB()
    schedulePoll()
    if (!activeDocId.value && docs.value.length) activeDocId.value = docs.value[0].id
  } catch (err: any) {
    uploadErr.value = err.response?.data?.detail || err.message
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function onDeleteDoc(doc: DocumentRow, e: Event) {
  e.stopPropagation()
  if (!confirm(`删除 "${doc.filename}"？`)) return
  await kbStore.removeDoc(doc)
  if (activeDocId.value === doc.id) activeDocId.value = docs.value[0]?.id ?? null
  await loadKB()
}

async function onReingest(doc: DocumentRow, e: Event) {
  e.stopPropagation()
  await kbStore.reingest(doc)
  schedulePoll()
}

function back() {
  router.push('/admin/kb')
}

const activeDoc = computed(() => docs.value.find((d) => d.id === activeDocId.value))
const qaTotalPages = computed(() => Math.max(1, Math.ceil(qaTotal.value / pageSize)))

function syncMetadataRows() {
  const meta = activeDoc.value?.metadata || {}
  metadataRows.value = Object.entries(meta).map(([key, value]) => ({
    key,
    value: value == null ? '' : String(value),
  }))
  metadataMsg.value = ''
}

function addMetadataRow() {
  metadataRows.value.push({ key: '', value: '' })
}

function removeMetadataRow(idx: number) {
  metadataRows.value.splice(idx, 1)
}

function parseMetadataValue(raw: string): string | number | boolean | null {
  const value = raw.trim()
  if (value === '') return ''
  if (value === 'true') return true
  if (value === 'false') return false
  if (value === 'null') return null
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value)
  return value
}

async function saveMetadata() {
  if (!activeDoc.value || metadataSaving.value) return
  metadataSaving.value = true
  metadataMsg.value = ''
  try {
    const metadata: Record<string, string | number | boolean | null> = {}
    for (const row of metadataRows.value) {
      const key = row.key.trim()
      if (!key) continue
      metadata[key] = parseMetadataValue(row.value)
    }
    await kbStore.saveDocMetadata(activeDoc.value, metadata)
    metadataMsg.value = 'Metadata 已保存'
    syncMetadataRows()
  } catch (e: any) {
    metadataMsg.value = e.response?.data?.detail || e.message
  } finally {
    metadataSaving.value = false
  }
}

watch(
  docs,
  (rows) => {
    const busy = rows.some((d) => ['pending', 'parsing', 'chunking', 'embedding', 'qa_generating'].includes(d.status))
    if (busy) schedulePoll()
    else clearPoll()
  },
  { deep: true },
)

watch(activeDocId, () => {
  chunksPage.value = 1
  loadChunks()
  loadDocQaStats()
  syncMetadataRows()
  if (rightTab.value === 'qa') {
    qaPage.value = 1
    loadQaList()
  }
})

watch(
  () => activeDoc.value?.metadata,
  () => syncMetadataRows(),
  { deep: true },
)

watch(rightTab, () => {
  if (rightTab.value === 'qa') {
    qaPage.value = 1
    loadQaList()
  }
})

watch(qaScope, () => {
  qaPage.value = 1
  loadQaList()
})

watch(
  () => kb.value?.qa_model,
  (v) => {
    qaModelSel.value = v || ''
  },
)

onMounted(async () => {
  await Promise.all([refresh(), loadModels()])
  if (docs.value.length) activeDocId.value = docs.value[0].id
  syncMetadataRows()
  qaModelSel.value = kb.value?.qa_model || ''
})

onUnmounted(() => {
  clearPoll()
  clearQaPoll()
})
</script>

<template>
  <section class="flex h-full w-full">
    <div class="flex h-full w-96 shrink-0 flex-col border-r border-claude-border bg-claude-panel">
      <DocumentListPanel
        :kb="kb"
        :docs="docs"
        :active-doc-id="activeDocId"
        :uploading="uploading"
        :upload-progress="uploadProgress"
        :upload-err="uploadErr"
        @back="back"
        @pick-file="onPickFile"
        @select-doc="activeDocId = $event"
        @reingest="onReingest"
        @generate-doc-qa="onGenerateDocQa"
        @delete-doc="onDeleteDoc"
      />

      <QaControlPanel
        v-model="qaModelSel"
        :kb="kb"
        :qa-stats="qaStats"
        :doc-qa-stats="docQaStats"
        :active-doc="activeDoc"
        :qa-busy="qaBusy"
        :qa-toggle-busy="qaToggleBusy"
        :qa-model-saving="qaModelSaving"
        :qa-msg="qaMsg"
        :models="models"
        :default-chat-model="defaultChatModel"
        @toggle-qa="onToggleQa"
        @change-qa-count="onChangeQaCount"
        @change-qa-model="onChangeQaModel"
        @generate-doc-qa="onGenerateSelectedDocQa"
        @generate-kb-qa="onGenerateKbQa"
      />

      <input ref="fileInput" type="file" accept="application/pdf" multiple class="hidden" @change="onFile" />
    </div>

    <div class="flex h-full min-w-0 flex-1 flex-col bg-claude-bg">
      <header class="flex h-12 items-center gap-3 border-b border-claude-border bg-claude-bg/80 px-6 text-sm backdrop-blur">
        <span class="truncate font-medium">{{ activeDoc?.filename ?? '选择文档' }}</span>
        <span v-if="rightTab === 'chunks' && activeDocId" class="text-claude-muted">· {{ chunksTotal }} chunks</span>
        <span v-if="rightTab === 'qa'" class="text-claude-muted">· {{ qaTotal }} Q&A</span>
        <p v-if="err" class="ml-2 truncate text-xs text-red-600">{{ err }}</p>

        <div class="ml-auto flex items-center gap-1 rounded-lg border border-claude-border bg-white p-0.5">
          <button
            class="rounded-md px-2.5 py-1 text-xs transition-colors"
            :class="rightTab === 'chunks' ? 'bg-claude-border/70 text-claude-ink' : 'text-claude-muted hover:text-claude-ink'"
            @click="rightTab = 'chunks'"
          >
            Chunks
          </button>
          <button
            class="rounded-md px-2.5 py-1 text-xs transition-colors"
            :class="rightTab === 'qa' ? 'bg-claude-border/70 text-claude-ink' : 'text-claude-muted hover:text-claude-ink'"
            @click="rightTab = 'qa'"
          >
            Q&amp;A
          </button>
        </div>
      </header>

      <details v-if="activeDoc" class="border-b border-claude-border bg-white/50 px-6 py-2 text-xs">
        <summary class="flex cursor-pointer list-none items-center gap-2 text-claude-muted">
          <span class="font-medium text-claude-ink">Metadata</span>
          <span>{{ Object.keys(activeDoc.metadata || {}).length }} fields</span>
          <span v-if="metadataMsg" class="ml-auto text-claude-accent">{{ metadataMsg }}</span>
        </summary>
        <div class="mt-3 space-y-2">
          <div v-for="(row, idx) in metadataRows" :key="idx" class="grid grid-cols-[minmax(0,180px)_1fr_auto] gap-2">
            <input v-model="row.key" class="input py-1.5 text-xs" placeholder="字段名，如 region" />
            <input v-model="row.value" class="input py-1.5 text-xs" placeholder="字段值，如 新疆" />
            <button class="rounded-md px-2 text-claude-muted hover:bg-red-50 hover:text-red-600" title="删除字段" @click="removeMetadataRow(idx)">
              x
            </button>
          </div>
          <div class="flex items-center gap-2">
            <button class="btn-ghost px-2.5 py-1 text-xs" @click="addMetadataRow">添加字段</button>
            <button class="btn-primary px-3 py-1 text-xs" :disabled="metadataSaving" @click="saveMetadata">
              {{ metadataSaving ? '保存中...' : '保存 Metadata' }}
            </button>
            <button class="btn-ghost px-2.5 py-1 text-xs" @click="syncMetadataRows">重置</button>
          </div>
        </div>
      </details>

      <ChunkViewer
        v-if="rightTab === 'chunks'"
        :active-doc-id="activeDocId"
        :docs="docs"
        :chunks="chunks"
        :chunks-loading="chunksLoading"
        :chunks-total="chunksTotal"
        :chunks-page="chunksPage"
        :page-size="pageSize"
        @page="setChunksPage"
      />

      <div v-else class="flex min-h-0 flex-1 flex-col">
        <div class="flex items-center gap-2 border-b border-claude-border bg-white/60 px-6 py-2 text-xs">
          <div class="flex items-center gap-1 rounded-lg border border-claude-border bg-white p-0.5">
            <button
              class="rounded-md px-2 py-1 transition-colors"
              :class="qaScope === 'doc' ? 'bg-claude-border/70 text-claude-ink' : 'text-claude-muted hover:text-claude-ink'"
              :disabled="!activeDocId"
              @click="qaScope = 'doc'"
            >
              本文档
            </button>
            <button
              class="rounded-md px-2 py-1 transition-colors"
              :class="qaScope === 'kb' ? 'bg-claude-border/70 text-claude-ink' : 'text-claude-muted hover:text-claude-ink'"
              @click="qaScope = 'kb'"
            >
              整个知识库
            </button>
          </div>
          <input
            v-model="qaQuery"
            type="text"
            placeholder="搜索问题/答案..."
            class="flex-1 rounded-lg border border-claude-border bg-white px-3 py-1.5 outline-none focus:border-claude-accent/60"
            @keyup.enter="qaPage = 1; loadQaList()"
          />
          <button class="btn-ghost px-2.5 py-1" @click="qaPage = 1; loadQaList()">搜索</button>
        </div>

        <div class="flex-1 overflow-y-auto px-6 py-6">
          <p v-if="qaLoading && !qaItems.length" class="py-12 text-center text-sm text-claude-muted">加载中…</p>
          <p v-else-if="!qaItems.length" class="py-12 text-center text-sm text-claude-muted">
            <span v-if="!kb?.qa_enabled">该知识库未启用 Q&A 生成</span>
            <span v-else-if="qaQuery">没有匹配的 Q&A</span>
            <span v-else-if="qaScope === 'doc' && !activeDocId">选择左侧文档或切换到“整个知识库”</span>
            <span v-else>还没有生成 Q&A。左侧面板可手动生成</span>
          </p>

          <div v-else class="mx-auto max-w-3xl space-y-3">
            <article v-for="qa in qaItems" :key="qa.id" class="card p-4">
              <header class="mb-2 flex items-center gap-3 text-xs text-claude-muted">
                <span class="rounded bg-claude-accent/10 px-1.5 py-0.5 font-medium text-claude-accent">Q&amp;A</span>
                <span class="max-w-[220px] truncate" :title="qa.filename">{{ qa.filename }}</span>
                <span>p.{{ qa.page ?? '?' }}</span>
                <span class="font-mono text-[10px] text-claude-muted/70">chunk:{{ qa.chunk_id }}</span>
                <button class="ml-auto rounded p-1 text-claude-muted hover:bg-red-50 hover:text-red-600" title="删除该 Q&A" @click="onDeleteQa(qa)">
                  <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
                </button>
              </header>
              <div class="space-y-2">
                <div>
                  <div class="mb-0.5 text-[11px] font-medium text-claude-muted">问</div>
                  <p class="whitespace-pre-wrap text-[14px] leading-relaxed">{{ qa.question }}</p>
                </div>
                <div>
                  <div class="mb-0.5 text-[11px] font-medium text-claude-muted">答</div>
                  <p class="whitespace-pre-wrap text-[14px] leading-relaxed text-claude-ink/90">{{ qa.answer }}</p>
                </div>
              </div>
            </article>

            <div v-if="qaTotalPages > 1" class="flex items-center justify-center gap-2 pt-3 text-sm">
              <button class="btn-ghost" :disabled="qaPage <= 1" @click="qaPage--; loadQaList()">上一页</button>
              <span class="text-claude-muted">{{ qaPage }} / {{ qaTotalPages }}</span>
              <button class="btn-ghost" :disabled="qaPage >= qaTotalPages" @click="qaPage++; loadQaList()">下一页</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
