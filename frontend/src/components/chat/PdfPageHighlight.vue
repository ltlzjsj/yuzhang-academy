<script setup lang="ts">
/**
 * Renders a single PDF page with bbox overlays for citation targets.
 *
 * Why inline PDF.js instead of an <iframe src="pdf">:
 * - The `/documents/:id/file` endpoint is bearer-authed; iframe can't carry
 *   Authorization. PDF.js consumes a typed-array, so we fetch bytes ourselves
 *   with the token and feed them in.
 * - We want to draw overlays *inside* the canvas container — possible only
 *   when PDF.js owns the render surface in our DOM.
 *
 * bbox contract: MinerU emits `[x0, y0, x1, y1]` normalized to 0-1000.
 * We render overlays via percentages over the canvas wrapper, so they
 * survive any scale/resize without recomputation.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

// Resolve worker via `?url` — Vite inlines a stable URL and copies the worker
// into the bundle. This is the officially recommended wiring for Vite + pdfjs.
// @ts-ignore — Vite asset import
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
// Keep the import specifier as a deep path so Vite pre-bundling stays happy.
import * as pdfjsLib from 'pdfjs-dist'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const props = defineProps<{
  docId: number
  page: number
  /** Array of `{page, bbox}` from the chunk; only entries matching `props.page` are drawn */
  bboxes: Array<{ page: number; bbox: [number, number, number, number] }>
  /** 0-1000 normalization base. MinerU = 1000. Overridable in case we add
   * another parser later with a different convention. */
  bboxBase?: number
}>()

const emit = defineEmits<{
  (e: 'pages', total: number): void
}>()

const authStore = useAuthStore()
const canvasEl = ref<HTMLCanvasElement | null>(null)
const wrapperEl = ref<HTMLDivElement | null>(null)
const loading = ref(true)
const errorMsg = ref<string | null>(null)
const totalPages = ref(0)

// Per-document PDF handle — cached so paging within the same doc is instant
let pdfHandle: any = null
let pdfDocId: number | null = null
let renderTask: any = null
let renderSeq = 0
let resizeObserver: ResizeObserver | null = null
let resizeTimer: number | null = null

async function loadPdf(docId: number) {
  if (pdfHandle && pdfDocId === docId) return pdfHandle
  // Destroy previous doc's handle
  if (pdfHandle) {
    try { await pdfHandle.destroy() } catch {}
    pdfHandle = null
  }
  const resp = await fetch(`/api/v1/documents/${docId}/file`, {
    headers: { Authorization: `Bearer ${authStore.token}` },
  })
  if (!resp.ok) throw new Error(`PDF 加载失败 (${resp.status})`)
  const buf = await resp.arrayBuffer()
  // cMap/font URLs: the copy-pdfjs-assets.mjs postinstall script stages these
  // under /public/pdfjs. Without them, Chinese CJK PDFs render as dots or
  // blank — PDF.js can't resolve CIDType/Type0 font character maps.
  const task = pdfjsLib.getDocument({
    data: new Uint8Array(buf),
    cMapUrl: '/pdfjs/cmaps/',
    cMapPacked: true,
    standardFontDataUrl: '/pdfjs/standard_fonts/',
  })
  pdfHandle = await task.promise
  pdfDocId = docId
  totalPages.value = pdfHandle.numPages
  emit('pages', pdfHandle.numPages)
  return pdfHandle
}

async function renderPage() {
  const seq = ++renderSeq
  loading.value = true
  errorMsg.value = null
  try {
    await nextTick()
    const pdf = await loadPdf(props.docId)
    const pageNum = Math.min(Math.max(1, props.page || 1), pdf.numPages)
    if (props.page && props.page > pdf.numPages) {
      throw new Error(`PDF 只有 ${pdf.numPages} 页，无法定位到第 ${props.page} 页`)
    }
    const page = await pdf.getPage(pageNum)

    const canvas = canvasEl.value
    const wrapper = wrapperEl.value
    if (!canvas || !wrapper) {
      loading.value = false
      return
    }

    // Render at the wrapper's current CSS width; HiDPI-friendly via DPR scaling
    const cssWidth = wrapper.clientWidth || wrapper.getBoundingClientRect().width || 520
    if (cssWidth < 40) {
      throw new Error("PDF 容器宽度异常，请稍后重试")
    }
    const baseViewport = page.getViewport({ scale: 1 })
    const cssScale = cssWidth / baseViewport.width
    const dpr = window.devicePixelRatio || 1
    const viewport = page.getViewport({ scale: cssScale * dpr })

    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.width = `${viewport.width / dpr}px`
    canvas.style.height = `${viewport.height / dpr}px`
    // Keep wrapper height in sync so overlays use its box
    wrapper.style.height = `${viewport.height / dpr}px`

    // Cancel any in-flight render (user clicked fast)
    if (renderTask) {
      try { renderTask.cancel() } catch {}
    }
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    renderTask = page.render({ canvasContext: ctx, viewport })
    await renderTask.promise
    if (seq !== renderSeq) return
    renderTask = null
    loading.value = false
  } catch (e: any) {
    if (e?.name === 'RenderingCancelledException') return
    errorMsg.value = e?.message || String(e)
    loading.value = false
  }
}

function scheduleRender() {
  if (resizeTimer) window.clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(() => {
    renderPage()
  }, 80)
}

const pageBoxes = computed(() => {
  const base = props.bboxBase ?? 1000
  return (props.bboxes || [])
    .filter((b) => b.page === props.page)
    .map((b) => {
      const [x0, y0, x1, y1] = b.bbox
      return {
        left: `${(x0 / base) * 100}%`,
        top: `${(y0 / base) * 100}%`,
        width: `${((x1 - x0) / base) * 100}%`,
        height: `${((y1 - y0) / base) * 100}%`,
      }
    })
})

watch(() => [props.docId, props.page], renderPage, { immediate: true })

onMounted(() => {
  if (!wrapperEl.value || typeof ResizeObserver === 'undefined') return
  resizeObserver = new ResizeObserver(() => scheduleRender())
  resizeObserver.observe(wrapperEl.value)
})

onBeforeUnmount(async () => {
  if (resizeTimer) window.clearTimeout(resizeTimer)
  if (resizeObserver) resizeObserver.disconnect()
  if (renderTask) {
    try { renderTask.cancel() } catch {}
  }
  if (pdfHandle) {
    try { await pdfHandle.destroy() } catch {}
    pdfHandle = null
  }
})
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      ref="wrapperEl"
      class="relative w-full overflow-hidden rounded-md border border-claude-border bg-white shadow-sm"
    >
      <canvas ref="canvasEl" class="block h-auto w-full" />
      <!-- Highlight overlays (absolute positioning over the canvas) -->
      <div
        v-for="(box, i) in pageBoxes"
        :key="i"
        class="pointer-events-none absolute rounded-sm border-2 border-claude-accent bg-claude-accent/20 transition-all"
        :style="box"
      />
      <div
        v-if="loading"
        class="absolute inset-0 flex items-center justify-center bg-white/60 text-xs text-claude-muted"
      >
        正在加载 PDF…
      </div>
      <div
        v-if="errorMsg"
        class="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-white/90 px-4 text-center text-xs text-red-600"
      >
        <span>{{ errorMsg }}</span>
        <button class="rounded-md border border-red-200 bg-white px-2 py-1 text-[11px] text-red-600 hover:bg-red-50" @click="renderPage">
          重新加载 PDF
        </button>
      </div>
    </div>
    <div class="text-right text-[11px] text-claude-muted">
      第 {{ page }} 页 / 共 {{ totalPages || '—' }} 页
    </div>
  </div>
</template>
