<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'

const PdfPageHighlight = defineAsyncComponent(() => import('./PdfPageHighlight.vue'))

export interface Citation {
  idx: number
  chunk_id: number
  document_id: number
  kb_id: number
  page: number | null
  bbox: any
  filename: string
  text_preview: string
  score: number
  retrieval?: {
    rrf?: number
    vector?: number
    bm25?: number
    qa?: number
    gate_reason?: string
    matched_qa?: {
      qa_id?: number
      question?: string
      answer?: string
      score?: number
    }
  }
  matched_qa?: {
    qa_id?: number
    question?: string
    answer?: string
    score?: number
  }
  has_table?: boolean
  has_formula?: boolean
  structured_preview?: string
}

const props = defineProps<{
  open: boolean
  citation: Citation | null
  allCitations?: Citation[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', idx: number): void
}>()

const others = computed(() =>
  (props.allCitations || []).filter((c) => c.idx !== props.citation?.idx),
)

// Tab switch — "原文" (PDF view) / "预览" / structured table-formula payload.
const tab = ref<'pdf' | 'preview' | 'structured'>('pdf')
// Reset tab on each new citation open
watch(
  () => [props.open, props.citation?.idx],
  () => {
    if (props.open) tab.value = 'pdf'
  },
)

// Normalise bbox to the shape PdfPageHighlight expects:
// Chunk.bbox in DB is `[{page: n, bbox: [x0,y0,x1,y1]}, ...]` (see ingest.py).
const normalisedBboxes = computed(() => {
  const raw = props.citation?.bbox
  if (!Array.isArray(raw)) return []
  return raw
    .filter((r: any) => r && Array.isArray(r.bbox) && r.bbox.length >= 4)
    .map((r: any) => ({
      page: r.page,
      bbox: [r.bbox[0], r.bbox[1], r.bbox[2], r.bbox[3]] as [number, number, number, number],
    }))
})

// The page we render in the PDF viewer — prefer the citation's own page,
// falling back to the first bbox range.
const viewerPage = computed(() => {
  if (props.citation?.page) return props.citation.page
  if (normalisedBboxes.value.length) return normalisedBboxes.value[0].page
  return 1
})

const canShowPdf = computed(() => !!props.citation?.document_id)
const matchedQa = computed(() => props.citation?.matched_qa || props.citation?.retrieval?.matched_qa || null)
</script>

<template>
  <!-- Backdrop -->
  <div
    v-if="open"
    class="fixed inset-0 z-40 bg-black/20 transition-opacity"
    @click="emit('close')"
  />

  <!-- Drawer -->
  <aside
    class="fixed right-0 top-0 z-50 flex h-full w-[560px] max-w-[90vw] flex-col border-l border-claude-border bg-white shadow-xl transition-transform duration-200 ease-claude"
    :class="open ? 'translate-x-0' : 'translate-x-full'"
  >
    <header class="flex items-center justify-between border-b border-claude-border px-5 py-3">
      <div class="flex items-center gap-2">
        <span
          class="flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-claude-accent/10 px-1.5 text-xs font-semibold text-claude-accent"
        >
          {{ citation?.idx ?? '·' }}
        </span>
        <span class="text-sm font-medium">引用详情</span>
      </div>
      <button class="text-claude-muted hover:text-claude-ink" @click="emit('close')">
        ✕
      </button>
    </header>

    <div v-if="citation" class="flex-1 overflow-y-auto px-5 py-4">
      <div class="mb-3 text-xs text-claude-muted">
        <div class="truncate">📄 {{ citation.filename }}</div>
        <div class="mt-0.5">
          第 {{ citation.page ?? '?' }} 页 · 相关度 {{ citation.score.toFixed(3) }}
        </div>
        <div v-if="citation.retrieval" class="mt-1 flex flex-wrap gap-1 text-[11px]">
          <span class="rounded bg-claude-bg px-1.5 py-0.5">RRF {{ Number(citation.retrieval.rrf || 0).toFixed(4) }}</span>
          <span class="rounded bg-claude-bg px-1.5 py-0.5">V {{ Number(citation.retrieval.vector || 0).toFixed(3) }}</span>
          <span class="rounded bg-claude-bg px-1.5 py-0.5">BM25 {{ Number(citation.retrieval.bm25 || 0).toFixed(2) }}</span>
          <span class="rounded bg-claude-bg px-1.5 py-0.5">QA {{ Number(citation.retrieval.qa || 0).toFixed(3) }}</span>
          <span v-if="citation.retrieval.gate_reason" class="rounded bg-claude-bg px-1.5 py-0.5">{{ citation.retrieval.gate_reason }}</span>
        </div>
        <div v-if="citation.has_table || citation.has_formula" class="mt-2 flex flex-wrap gap-1.5">
          <span
            v-if="citation.has_table"
            class="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700"
          >
            表格
          </span>
          <span
            v-if="citation.has_formula"
            class="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] font-medium text-indigo-700"
          >
            公式
          </span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="mb-3 flex gap-1 border-b border-claude-border">
        <button
          class="px-3 py-1.5 text-xs transition-colors"
          :class="
            tab === 'pdf'
              ? 'border-b-2 border-claude-accent text-claude-accent'
              : 'text-claude-muted hover:text-claude-ink'
          "
          :disabled="!canShowPdf"
          @click="tab = 'pdf'"
        >
          在原文中查看
        </button>
        <button
          class="px-3 py-1.5 text-xs transition-colors"
          :class="
            tab === 'preview'
              ? 'border-b-2 border-claude-accent text-claude-accent'
              : 'text-claude-muted hover:text-claude-ink'
          "
          @click="tab = 'preview'"
        >
          Chunk 文本
        </button>
        <button
          v-if="citation.structured_preview"
          class="px-3 py-1.5 text-xs transition-colors"
          :class="
            tab === 'structured'
              ? 'border-b-2 border-claude-accent text-claude-accent'
              : 'text-claude-muted hover:text-claude-ink'
          "
          @click="tab = 'structured'"
        >
          表格/公式
        </button>
      </div>

      <div v-if="matchedQa" class="mb-3 rounded-lg border border-claude-accent/25 bg-claude-accent/5 px-3 py-2 text-sm">
        <div class="mb-1 flex items-center justify-between text-[11px] font-medium text-claude-accent">
          <span>命中 Q&A</span>
          <span class="font-mono">score {{ Number(matchedQa.score || 0).toFixed(3) }}</span>
        </div>
        <div class="space-y-1 text-xs leading-relaxed">
          <p><span class="font-medium text-claude-muted">问：</span>{{ matchedQa.question }}</p>
          <p><span class="font-medium text-claude-muted">答：</span>{{ matchedQa.answer }}</p>
        </div>
      </div>

      <!-- PDF view -->
      <div v-if="tab === 'pdf' && canShowPdf">
        <PdfPageHighlight
          :doc-id="citation.document_id"
          :page="viewerPage"
          :bboxes="normalisedBboxes"
        />
        <p v-if="!normalisedBboxes.length" class="mt-2 text-[11px] text-claude-muted">
          （该 chunk 无 bbox 记录，仅定位到页；重新解析已入库的旧文档可补齐）
        </p>
      </div>

      <!-- Preview text tab -->
      <div v-show="tab === 'preview'">
        <div
          class="whitespace-pre-wrap rounded-md border border-claude-border bg-claude-bg/50 px-3 py-2.5 text-sm leading-relaxed text-claude-ink"
        >
          {{ citation.text_preview }}
        </div>
        <div class="mt-3 text-xs text-claude-muted">
          <span v-if="citation.bbox">坐标: 共 {{ citation.bbox.length }} 处原文区块</span>
          <span v-else>（此 chunk 无 bbox 信息）</span>
        </div>
      </div>

      <!-- Structured table/formula tab -->
      <div v-show="tab === 'structured'">
        <pre
          class="whitespace-pre-wrap rounded-md border border-claude-border bg-slate-50 px-3 py-2.5 font-mono text-xs leading-relaxed text-claude-ink"
        >{{ citation.structured_preview }}</pre>
      </div>
    </div>

    <div v-if="others.length" class="border-t border-claude-border px-5 py-3">
      <div class="mb-2 text-xs text-claude-muted">其他引用</div>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="c in others"
          :key="c.idx"
          class="rounded-full border border-claude-border bg-white px-2 py-0.5 text-xs hover:bg-claude-bg"
          @click="emit('select', c.idx)"
        >
          [{{ c.idx }}] {{ c.filename.slice(0, 16) }}{{ c.filename.length > 16 ? '…' : '' }}
        </button>
      </div>
    </div>
  </aside>
</template>
