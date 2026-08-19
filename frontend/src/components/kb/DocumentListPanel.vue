<script setup lang="ts">
import type { DocumentRow, KnowledgeBase } from '@/api/kb'

defineProps<{
  kb: KnowledgeBase | null
  docs: DocumentRow[]
  activeDocId: number | null
  uploading: boolean
  uploadProgress: number
  uploadErr: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'pickFile'): void
  (e: 'selectDoc', id: number): void
  (e: 'reingest', doc: DocumentRow, event: Event): void
  (e: 'generateDocQa', doc: DocumentRow, event: Event): void
  (e: 'deleteDoc', doc: DocumentRow, event: Event): void
}>()

const statusLabel: Record<string, string> = {
  pending: '排队中',
  parsing: '解析中',
  chunking: '切分中',
  embedding: '嵌入中',
  qa_generating: '生成 Q&A',
  done: '完成',
  failed: '失败',
}

const statusColor: Record<string, string> = {
  done: 'text-emerald-600 bg-emerald-50',
  failed: 'text-red-600 bg-red-50',
}

function statusCls(s: string) {
  return statusColor[s] || 'text-claude-accent bg-claude-accent/10'
}

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

function metadataEntries(doc: DocumentRow) {
  return Object.entries(doc.metadata || {}).filter(([, v]) => v !== null && v !== '').slice(0, 3)
}

function docImageUrl(im: { src: string; kind?: string }) {
  const root = im.kind === 'academy' ? '/api/v1/assets/academy/' : '/api/v1/assets/mineru/'
  return root + im.src
}
</script>

<template>
  <div class="flex items-center gap-2 border-b border-claude-border px-4 py-3">
    <button class="btn-ghost -ml-2 h-8 w-8 p-0" title="返回" @click="emit('back')">
      <svg class="mx-auto h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" /></svg>
    </button>
    <h2 class="truncate font-medium">{{ kb?.name ?? '知识库' }}</h2>
  </div>

  <div class="border-b border-claude-border p-3">
    <button
      class="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-claude-border px-3 py-3 text-sm text-claude-muted transition-colors hover:border-claude-accent/60 hover:bg-white hover:text-claude-ink"
      :disabled="uploading"
      @click="emit('pickFile')"
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M17 8l-5-5-5 5" /><path d="M12 3v12" /></svg>
      <span v-if="!uploading">上传 PDF</span>
      <span v-else>上传中 {{ uploadProgress }}%</span>
    </button>
    <p v-if="uploadErr" class="mt-2 text-xs text-red-600">{{ uploadErr }}</p>
  </div>

  <div class="flex-1 overflow-y-auto p-2">
    <p v-if="!docs.length" class="px-3 py-8 text-center text-xs text-claude-muted">
      还没有文档。上传一个 PDF 开始吧。
    </p>
    <ul v-else class="space-y-1">
      <li
        v-for="d in docs"
        :key="d.id"
        class="group cursor-pointer rounded-lg p-2 transition-colors"
        :class="activeDocId === d.id ? 'bg-claude-border/80' : 'hover:bg-claude-border/50'"
        @click="emit('selectDoc', d.id)"
      >
        <div class="flex items-start gap-2">
          <div class="mt-0.5 h-4 w-4 shrink-0 text-claude-muted">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium">{{ d.filename }}</p>
            <div class="mt-0.5 flex items-center gap-2 text-[11px]">
              <span :class="statusCls(d.status)" class="rounded-full px-1.5 py-0.5">
                {{ statusLabel[d.status] || d.status }}
              </span>
              <span v-if="d.status !== 'done' && d.status !== 'failed'" class="text-claude-muted">{{ d.progress }}%</span>
              <span v-else class="text-claude-muted">{{ d.pages }}页 · {{ fmtBytes(d.size_bytes) }}</span>
            </div>
            <div v-if="d.status !== 'done' && d.status !== 'failed'" class="mt-1 h-1 overflow-hidden rounded-full bg-claude-border/60">
              <div class="h-full bg-claude-accent transition-all" :style="{ width: `${d.progress}%` }" />
            </div>
            <p v-if="d.error" class="mt-1 line-clamp-2 text-[11px] text-red-600">{{ d.error }}</p>
            <div v-if="d.image_preview?.length" class="mt-2 flex items-center gap-1.5">
              <img
                v-for="im in d.image_preview.slice(0, 4)"
                :key="im.src"
                :src="docImageUrl(im)"
                :alt="im.caption || d.filename"
                class="h-9 w-9 rounded-md border border-white object-cover shadow-sm"
                loading="lazy"
              />
              <span class="ml-1 rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-claude-muted">
                {{ d.image_count }} 张图
              </span>
            </div>
            <div v-if="metadataEntries(d).length" class="mt-1 flex flex-wrap gap-1">
              <span
                v-for="[key, value] in metadataEntries(d)"
                :key="key"
                class="max-w-[140px] truncate rounded bg-white/70 px-1.5 py-0.5 text-[10px] text-claude-muted"
                :title="`${key}: ${value}`"
              >
                {{ key }}: {{ value }}
              </span>
            </div>
          </div>
          <div class="flex shrink-0 flex-col opacity-0 transition-opacity group-hover:opacity-100">
            <button class="h-6 w-6 rounded text-claude-muted hover:bg-white hover:text-claude-ink" title="重新解析" @click="emit('reingest', d, $event)">
              <svg class="mx-auto h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg>
            </button>
            <button v-if="kb?.qa_enabled" class="h-6 w-6 rounded text-claude-muted hover:bg-white hover:text-claude-accent" title="为该文档重新生成 Q&A" @click="emit('generateDocQa', d, $event)">
              <svg class="mx-auto h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.39 4.84L20 8l-4 3.89.94 5.5L12 14.77l-5 2.62L8 11.9 4 8l5.61-1.16z" /></svg>
            </button>
            <button class="h-6 w-6 rounded text-claude-muted hover:bg-white hover:text-red-600" title="删除" @click="emit('deleteDoc', d, $event)">
              <svg class="mx-auto h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
            </button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>
