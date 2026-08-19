<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{ streaming: boolean }>()
const emit = defineEmits<{
  (e: 'submit', text: string): void
  (e: 'stop'): void
}>()

const value = ref('')
const taRef = ref<HTMLTextAreaElement | null>(null)

function autoGrow() {
  const el = taRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 240) + 'px'
}

watch(value, () => nextTick(autoGrow))

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

function submit() {
  const text = value.value.trim()
  if (!text || props.streaming) return
  emit('submit', text)
  value.value = ''
  nextTick(autoGrow)
}
</script>

<template>
  <div class="mx-auto w-full max-w-3xl px-4 pb-6">
    <div
      class="flex items-end gap-2 rounded-3xl border border-claude-border bg-white p-2 shadow-soft transition-shadow focus-within:shadow-md"
    >
      <textarea
        ref="taRef"
        v-model="value"
        rows="1"
        placeholder="向豫章书院智能体发送消息..."
        class="flex-1 resize-none bg-transparent px-3 py-2 text-[15px] leading-6 text-claude-ink placeholder:text-claude-muted focus:outline-none"
        @keydown="onKey"
        @input="autoGrow"
      />
      <button
        v-if="!streaming"
        class="h-9 w-9 shrink-0 rounded-full bg-claude-accent text-white transition-colors duration-200 ease-claude hover:bg-claude-accentHover disabled:opacity-40"
        :disabled="!value.trim()"
        title="发送"
        @click="submit"
      >
        <svg viewBox="0 0 24 24" class="mx-auto h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>
      </button>
      <button
        v-else
        class="h-9 w-9 shrink-0 rounded-full bg-claude-ink text-white hover:bg-claude-ink/80"
        title="停止"
        @click="emit('stop')"
      >
        <svg viewBox="0 0 24 24" class="mx-auto h-4 w-4" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="1.5"/></svg>
      </button>
    </div>
    <p class="mt-2 text-center text-xs text-claude-muted">
      Enter 发送 · Shift + Enter 换行
    </p>
  </div>
</template>
