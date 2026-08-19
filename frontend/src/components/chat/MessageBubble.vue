<script setup lang="ts">
import { computed, ref } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import type { UiMessage } from '@/stores/chat'
import CitationDrawer, { type Citation } from './CitationDrawer.vue'
import LazyGalleryImage from './LazyGalleryImage.vue'

const props = defineProps<{ msg: UiMessage }>()
const emit = defineEmits<{
  (e: 'regenerate', id: number | string): void
}>()

const html = computed(() => renderMarkdown(props.msg.content || ''))
const isUser = computed(() => props.msg.role === 'user')
const statusClass = computed(() => {
  if (props.msg.stage === 'retrieving') return 'border-claude-accent/25 bg-claude-accent/5 text-claude-accent'
  if (props.msg.stage === 'thinking') return 'border-claude-ink/10 bg-claude-ink/[0.03] text-claude-ink/70'
  return 'border-claude-border bg-white/70 text-claude-muted'
})

const drawerOpen = ref(false)
const activeCitation = ref<Citation | null>(null)
const citations = computed<Citation[]>(() => (props.msg.citations as Citation[]) || [])
const thinkOpen = ref(true)
const copied = ref(false)

// 图文: prefer the live `images` event payload; otherwise reconstruct the
// gallery from persisted citations[].images so saved conversations still show
// figures. Deduped by src, capped for layout.
interface GalleryImage { src: string; page?: number | null; caption?: string; kind?: string }
function encodeAssetPath(src: string): string {
  return String(src)
    .replace(/^\/+/, '')
    .replace(/\\/g, '/')
    .split('/')
    .map((part) => encodeURIComponent(part))
    .join('/')
}
function imageUrl(im: GalleryImage): string {
  const mount = im.kind === 'academy' ? 'academy' : 'mineru'
  return `/api/v1/assets/${mount}/${encodeAssetPath(im.src)}`
}
function thumbUrl(im: GalleryImage): string {
  const mount = im.kind === 'academy' ? 'academy' : 'mineru'
  return `/api/v1/assets/thumb/${mount}/${encodeAssetPath(im.src)}?w=288&h=192`
}
const gallery = computed<GalleryImage[]>(() => {
  const raw: GalleryImage[] =
    (props.msg.images as GalleryImage[] | undefined) ||
    citations.value.flatMap((c: any) => (c.images as GalleryImage[]) || [])
  const seen = new Set<string>()
  const out: GalleryImage[] = []
  for (const im of raw) {
    if (!im?.src || seen.has(im.src)) continue
    seen.add(im.src)
    out.push(im)
    if (out.length >= 4) break
  }
  return out
})
const lightbox = ref<GalleryImage | null>(null)

function selectByIdx(idx: number) {
  const c = citations.value.find((x) => x.idx === idx)
  if (c) activeCitation.value = c
}

async function copyResponse() {
  if (!props.msg.content) return
  try {
    await navigator.clipboard.writeText(props.msg.content)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1200)
  } catch {
    copied.value = false
  }
}
</script>

<template>
  <div class="message-bubble group flex w-full" :class="isUser ? 'justify-end' : 'justify-start'">
    <div
      :class="[
        isUser
          ? 'max-w-[78%] rounded-bubble bg-claude-bubbleUser px-4 py-3 text-[15px] leading-relaxed text-claude-ink shadow-soft'
          : 'w-full max-w-[760px] px-1 py-2 text-claude-ink',
      ]"
    >
      <div v-if="isUser" class="whitespace-pre-wrap break-words">{{ msg.content }}</div>

      <template v-else>
        <div
          v-if="msg.pending && !msg.content && msg.statusText"
          class="mb-3 inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
          :class="statusClass"
        >
          <span class="relative flex h-2 w-2">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-20" />
            <span class="relative inline-flex h-2 w-2 rounded-full bg-current opacity-70" />
          </span>
          <span>{{ msg.statusText }}</span>
        </div>

        <details
          v-if="msg.thinking"
          :open="thinkOpen && !msg.content"
          class="mb-3 rounded-md border border-claude-border bg-white/50 text-xs"
        >
          <summary class="cursor-pointer select-none px-2.5 py-1 text-claude-muted">
            <span v-if="msg.pending && !msg.content">思考中...</span>
            <span v-else>思考过程</span>
            <span class="ml-1 text-claude-muted/60">({{ (msg.thinking || '').length }} 字)</span>
          </summary>
          <pre class="whitespace-pre-wrap break-words px-2.5 pb-2 pt-1 font-mono text-[11px] leading-relaxed text-claude-muted">{{ msg.thinking }}</pre>
        </details>

        <div class="md-body assistant-md" v-html="html" />

        <div v-if="gallery.length" class="mt-4">
          <div class="mb-2 text-xs text-claude-muted">相关图片 ›</div>
          <div class="flex flex-wrap gap-2">
            <LazyGalleryImage
              v-for="im in gallery"
              :key="im.src"
              :src="thumbUrl(im)"
              :fallback-src="imageUrl(im)"
              :alt="im.caption || '书院配图'"
              :caption="im.caption"
              :page="im.page"
              @click="lightbox = im"
            />
          </div>
        </div>

        <div v-if="citations.length" class="mt-4">
          <div class="mb-2 text-xs text-claude-muted">相关引用 ›</div>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="c in citations"
              :key="c.idx"
              class="inline-flex max-w-[240px] items-center gap-1 rounded-md border border-transparent bg-claude-bg/70 px-1.5 py-0.5 text-[11px] text-claude-muted transition-colors hover:border-claude-border hover:bg-white hover:text-claude-accent"
              @click="activeCitation = c; drawerOpen = true"
            >
              <span class="font-medium text-claude-accent">[{{ c.idx }}]</span>
              <span class="truncate">{{ c.filename }}</span>
              <span v-if="c.page">p.{{ c.page }}</span>
              <span v-if="c.matched_qa || c.retrieval?.matched_qa" class="rounded bg-claude-accent/10 px-1 text-[10px] text-claude-accent">QA</span>
              <span v-if="c.has_table" class="rounded bg-emerald-50 px-1 text-[10px] text-emerald-700">表</span>
              <span v-if="c.has_formula" class="rounded bg-indigo-50 px-1 text-[10px] text-indigo-700">式</span>
            </button>
          </div>
        </div>

        <div
          v-if="!msg.pending && msg.content"
          class="mt-4 flex items-center gap-1 text-claude-muted opacity-70 transition-opacity group-hover:opacity-100"
        >
          <button
            class="rounded-md p-1.5 hover:bg-claude-border/60 hover:text-claude-ink"
            :title="copied ? '已复制' : '复制'"
            @click="copyResponse"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
          </button>
          <button
            class="rounded-md p-1.5 hover:bg-claude-border/60 hover:text-claude-ink"
            title="重新生成"
            @click="emit('regenerate', msg.id)"
          >
            <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6" /><path d="M20.49 15A9 9 0 1 1 18.36 5.64L23 10" /></svg>
          </button>
        </div>

        <div v-if="msg.pending && !msg.content && !msg.thinking && !msg.statusText" class="flex items-center gap-1 py-1">
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-claude-muted [animation-delay:-0.3s]" />
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-claude-muted [animation-delay:-0.15s]" />
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-claude-muted" />
        </div>
        <span
          v-if="msg.pending && msg.content"
          class="ml-0.5 inline-block h-4 w-[2px] translate-y-[2px] animate-pulse bg-claude-ink/60"
        />
        <p v-if="msg.error" class="mt-2 text-xs text-red-600">{{ msg.error }}</p>
      </template>
    </div>
  </div>

  <CitationDrawer
    :open="drawerOpen"
    :citation="activeCitation"
    :all-citations="citations"
    @close="drawerOpen = false"
    @select="selectByIdx"
  />

  <Teleport to="body">
    <div
      v-if="lightbox"
      class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-6"
      @click="lightbox = null"
    >
      <img
        :src="imageUrl(lightbox)"
        :alt="lightbox.caption || '书院配图'"
        class="max-h-[85vh] max-w-[90vw] rounded-lg object-contain shadow-2xl"
      />
      <div v-if="lightbox.caption || lightbox.page" class="mt-3 max-w-[90vw] text-center text-sm text-white/80">
        {{ lightbox.caption || '' }}<span v-if="lightbox.page" class="ml-2 text-white/50">p.{{ lightbox.page }}</span>
      </div>
    </div>
  </Teleport>
</template>

<style>
.assistant-md {
  font-size: 16px;
  line-height: 1.66;
}
.message-bubble {
  content-visibility: auto;
  contain-intrinsic-size: auto 260px;
}
.assistant-md > *:first-child {
  margin-top: 0;
}
.assistant-md strong {
  font-weight: 700;
}
.assistant-md p {
  margin: 0.75rem 0;
}
.assistant-md ul,
.assistant-md ol {
  margin: 0.75rem 0;
  padding-left: 1.35rem;
}
.assistant-md li {
  margin: 0.3rem 0;
}
.assistant-md h1,
.assistant-md h2,
.assistant-md h3 {
  margin-top: 1.1rem;
  margin-bottom: 0.5rem;
  letter-spacing: 0;
}
.assistant-md blockquote {
  border-left: 2px solid #e8e6dc;
  color: #6b6a63;
  margin: 0.85rem 0;
  padding-left: 0.9rem;
}
.assistant-md table {
  background: rgba(255, 255, 255, 0.6);
  border-radius: 6px;
  overflow: hidden;
}
.assistant-md .katex {
  font-size: 1.02em;
  line-height: normal !important;
  white-space: nowrap;
  vertical-align: baseline;
}
.assistant-md .katex .base,
.assistant-md .katex .strut {
  line-height: normal !important;
}
.assistant-md .katex-display {
  margin: 0.9em 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.25em 0;
  line-height: normal !important;
}
</style>
