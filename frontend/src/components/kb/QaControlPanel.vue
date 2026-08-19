<script setup lang="ts">
import type { DocumentRow, KnowledgeBase, QaStats } from '@/api/kb'
import type { OllamaModel } from '@/api/models'

defineProps<{
  kb: KnowledgeBase | null
  activeDoc: DocumentRow | undefined
  qaStats: QaStats | null
  docQaStats: QaStats | null
  qaBusy: boolean
  qaToggleBusy: boolean
  qaModelSaving: boolean
  qaMsg: string
  modelValue: string
  models: OllamaModel[]
  defaultChatModel: string
}>()

const emit = defineEmits<{
  (e: 'toggleQa', enabled: boolean): void
  (e: 'changeQaCount', count: number): void
  (e: 'generateDocQa'): void
  (e: 'generateKbQa'): void
  (e: 'update:modelValue', value: string): void
  (e: 'changeQaModel', value: string): void
}>()

function onModelChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  emit('update:modelValue', value)
  emit('changeQaModel', value)
}
</script>

<template>
  <div class="border-b border-claude-border px-3 py-3">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-1.5 text-sm font-medium">
        <svg class="h-4 w-4 text-claude-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></svg>
        Q&A
      </div>
      <label class="inline-flex cursor-pointer items-center gap-1.5 text-xs text-claude-muted">
        <input
          type="checkbox"
          class="h-3.5 w-3.5 accent-claude-accent"
          :checked="!!kb?.qa_enabled"
          :disabled="qaToggleBusy"
          @change="emit('toggleQa', ($event.target as HTMLInputElement).checked)"
        />
        启用
      </label>
    </div>

    <div v-if="kb?.qa_enabled" class="mt-3 space-y-3">
      <div class="rounded-lg border border-claude-border bg-white/70 px-3 py-2">
        <div class="mb-1 flex items-center justify-between gap-2 text-[11px] text-claude-muted">
          <span class="truncate">当前文献</span>
          <span class="max-w-[180px] truncate font-medium text-claude-ink" :title="activeDoc?.filename">
            {{ activeDoc?.filename || '未选择' }}
          </span>
        </div>
        <div v-if="docQaStats" class="flex items-center justify-between text-[11px] text-claude-muted">
          <span>{{ docQaStats.covered_chunks }}/{{ docQaStats.total_chunks }} chunks</span>
          <span class="font-mono">{{ docQaStats.pairs }} pairs</span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[11px] text-claude-muted">
        <span>每块生成数量</span>
        <div class="flex items-center gap-1 rounded-md border border-claude-border bg-white p-0.5">
          <button
            v-for="n in [1, 2, 3]"
            :key="n"
            class="rounded px-2 py-0.5 transition-colors"
            :class="kb.qa_pairs_per_chunk === n ? 'bg-claude-accent/20 text-claude-accent font-medium' : 'text-claude-muted hover:text-claude-ink'"
            @click="emit('changeQaCount', n)"
          >
            {{ n }}
          </button>
        </div>
      </div>

      <div class="flex items-center justify-between gap-2 text-[11px] text-claude-muted">
        <span class="shrink-0">生成模型</span>
        <select
          :value="modelValue"
          class="min-w-0 flex-1 rounded-md border border-claude-border bg-white px-2 py-1 text-[11px] text-claude-ink outline-none focus:border-claude-accent/60 disabled:opacity-60"
          :disabled="qaModelSaving"
          :title="modelValue ? `已保存：${modelValue}` : `未指定，使用默认：${defaultChatModel}`"
          @change="onModelChange"
        >
          <option value="">默认（{{ defaultChatModel || '未知' }}）</option>
          <option v-for="m in models" :key="m.name" :value="m.name">{{ m.name }}</option>
        </select>
      </div>

      <button
        class="flex w-full items-center justify-center gap-1.5 rounded-lg border border-claude-accent/30 bg-claude-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-claude-accentHover disabled:opacity-60"
        :disabled="qaBusy || !activeDoc"
        @click="emit('generateDocQa')"
      >
        <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.39 4.84L20 8l-4 3.89.94 5.5L12 14.77l-5 2.62L8 11.9 4 8l5.61-1.16z" /></svg>
        {{ qaBusy ? '入队中...' : '为当前文献生成 Q&A' }}
      </button>

      <button
        class="flex w-full items-center justify-center gap-1.5 rounded-lg border border-claude-border bg-white px-3 py-1.5 text-xs text-claude-muted transition-colors hover:border-claude-accent/60 hover:text-claude-ink disabled:opacity-60"
        :disabled="qaBusy"
        @click="emit('generateKbQa')"
      >
        为整个知识库生成
      </button>

      <div v-if="qaStats" class="flex items-center justify-between text-[11px] text-claude-muted">
        <span>整库 {{ qaStats.covered_chunks }}/{{ qaStats.total_chunks }} chunks</span>
        <span class="font-mono">{{ qaStats.pairs }} pairs</span>
      </div>
      <p v-if="qaMsg" class="text-[11px] text-claude-accent">{{ qaMsg }}</p>
    </div>
    <p v-else class="mt-1 text-[11px] text-claude-muted">
      Q&A 用于增强特定知识库召回。启用后可优先为当前文献生成，必要时再整库生成。
    </p>
  </div>
</template>
