<script setup lang="ts">
import { computed } from 'vue'
import type { ChunkRow, DocumentRow } from '@/api/kb'

const props = defineProps<{
  activeDocId: number | null
  docs: DocumentRow[]
  chunks: ChunkRow[]
  chunksLoading: boolean
  chunksTotal: number
  chunksPage: number
  pageSize: number
}>()

const emit = defineEmits<{
  (e: 'page', page: number): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.chunksTotal / props.pageSize)))
const activeDoc = computed(() => props.docs.find((d) => d.id === props.activeDocId))
</script>

<template>
  <div class="flex-1 overflow-y-auto px-6 py-6">
    <p v-if="!activeDocId" class="py-12 text-center text-sm text-claude-muted">
      选择左侧的文档查看 chunks
    </p>
    <p v-else-if="chunksLoading && !chunks.length" class="py-12 text-center text-sm text-claude-muted">
      加载中…
    </p>
    <p v-else-if="!chunksLoading && !chunks.length" class="py-12 text-center text-sm text-claude-muted">
      <span v-if="activeDoc?.status !== 'done'">文档尚未处理完成</span>
      <span v-else>没有 chunks</span>
    </p>
    <div v-else class="mx-auto max-w-3xl space-y-3">
      <article v-for="c in chunks" :key="c.id" class="card p-4">
        <header class="mb-2 flex items-center gap-3 text-xs text-claude-muted">
          <span class="rounded bg-claude-bg px-1.5 py-0.5 font-mono">#{{ c.seq }}</span>
          <span>p.{{ c.page ?? '?' }}</span>
          <span>{{ c.token_count }} chars</span>
          <span
            v-if="c.metadata?.tables?.length"
            class="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700"
            :title="`携带 ${c.metadata.tables.length} 张结构化表格`"
          >
            表×{{ c.metadata.tables.length }}
          </span>
          <span
            v-if="c.metadata?.formulas?.length"
            class="rounded bg-indigo-50 px-1.5 py-0.5 text-indigo-700"
            :title="`携带 ${c.metadata.formulas.length} 条公式 LaTeX`"
          >
            公式×{{ c.metadata.formulas.length }}
          </span>
          <span v-if="c.metadata?.parser_version" class="rounded bg-claude-bg px-1.5 py-0.5">
            {{ c.metadata.parser_version }}
          </span>
          <span class="ml-auto text-[10px] font-mono text-claude-muted/70">id:{{ c.id }}</span>
        </header>

        <p class="whitespace-pre-wrap text-[14px] leading-relaxed">{{ c.text }}</p>

        <div v-if="c.metadata?.tables?.length || c.metadata?.formulas?.length" class="mt-3 space-y-2 border-t border-claude-border pt-3">
          <details
            v-for="(t, idx) in (c.metadata?.tables || [])"
            :key="`table-${idx}`"
            class="rounded-md border border-claude-border bg-white/70"
          >
            <summary class="cursor-pointer px-3 py-1.5 text-xs font-medium text-emerald-700">
              表格 {{ idx + 1 }}{{ t.caption ? ` · ${t.caption}` : '' }}
            </summary>
            <pre class="whitespace-pre-wrap px-3 pb-3 pt-1 font-mono text-xs leading-relaxed text-claude-ink">{{ t.text || '（表格文本为空，已保留 HTML 元数据）' }}</pre>
          </details>
          <details
            v-for="(f, idx) in (c.metadata?.formulas || [])"
            :key="`formula-${idx}`"
            class="rounded-md border border-claude-border bg-white/70"
          >
            <summary class="cursor-pointer px-3 py-1.5 text-xs font-medium text-indigo-700">
              公式 {{ idx + 1 }}
            </summary>
            <pre class="whitespace-pre-wrap px-3 pb-3 pt-1 font-mono text-xs leading-relaxed text-claude-ink">{{ f.latex }}</pre>
          </details>
        </div>
      </article>

      <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 pt-3 text-sm">
        <button class="btn-ghost" :disabled="chunksPage <= 1" @click="emit('page', chunksPage - 1)">上一页</button>
        <span class="text-claude-muted">{{ chunksPage }} / {{ totalPages }}</span>
        <button class="btn-ghost" :disabled="chunksPage >= totalPages" @click="emit('page', chunksPage + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>
