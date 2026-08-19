<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useAgentChat } from '@/composables/useAgentChat'
import { renderMarkdown } from '@/utils/markdown'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    avatar?: string | null
    accent?: string
    seal?: string
    systemPrompt: string
    kbIds?: number[]
    ragEnabled?: boolean
    suggestions?: string[]
    placeholder?: string
    initial?: string
  }>(),
  { accent: '#2c3e50', ragEnabled: true, placeholder: '输入你的问题…' },
)

const { messages, streaming, send, stop, reset } = useAgentChat(() => ({
  systemPrompt: props.systemPrompt,
  kbIds: props.kbIds,
  ragEnabled: props.ragEnabled,
}))

defineExpose({ reset, send })

const draft = ref('')
const scroller = ref<HTMLElement | null>(null)
const sentInitial = ref('')

function sendInitial(value?: string) {
  const text = (value || '').trim()
  if (!text || text === sentInitial.value) return
  sentInitial.value = text
  reset()
  send(text)
}

onMounted(() => sendInitial(props.initial))
watch(() => props.initial, sendInitial)

async function scrollDown() {
  await nextTick()
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
}
watch(messages, scrollDown, { deep: true })

function submit() {
  const text = draft.value
  draft.value = ''
  send(text)
}
function pick(q: string) {
  draft.value = ''
  send(q)
}
function onEnter(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

const accentStyle = computed(() => ({ '--ac': props.accent }) as Record<string, string>)
</script>

<template>
  <div class="ac" :style="accentStyle">
    <header class="ac__head">
      <div class="ac__avatar">
        <img v-if="avatar" :src="avatar" :alt="title" />
        <span v-else>{{ seal ?? title.slice(0, 1) }}</span>
      </div>
      <div class="ac__id">
        <strong>{{ title }}</strong>
        <small v-if="subtitle">{{ subtitle }}</small>
      </div>
    </header>

    <div ref="scroller" class="ac__body">
      <div v-if="!messages.length" class="ac__empty">
        <p>{{ subtitle || '开始对话吧。' }}</p>
        <div v-if="suggestions?.length" class="ac__chips">
          <button v-for="q in suggestions" :key="q" class="ac__chip" @click="pick(q)">{{ q }}</button>
        </div>
      </div>

      <div v-for="(m, i) in messages" :key="i" class="ac__row" :class="`ac__row--${m.role}`">
        <div class="ac__bubble" :class="`ac__bubble--${m.role}`">
          <div v-if="m.role === 'assistant'">
            <div v-if="m.content" class="md-body" v-html="renderMarkdown(m.content)" />
            <span v-else-if="m.pending" class="ac__typing"><i /><i /><i /></span>
            <p v-if="m.error" class="ac__err">{{ m.error }}</p>
            <p v-if="m.sources" class="ac__src">引用 {{ m.sources }} 条书院资料</p>
          </div>
          <span v-else>{{ m.content }}</span>
        </div>
      </div>
    </div>

    <footer class="ac__foot">
      <textarea
        v-model="draft"
        :placeholder="placeholder"
        rows="1"
        class="ac__input"
        @keydown="onEnter"
      />
      <button v-if="streaming" class="ac__send ac__send--stop" @click="stop">停止</button>
      <button v-else class="ac__send" :disabled="!draft.trim()" @click="submit">发送</button>
    </footer>
  </div>
</template>

<style scoped>
.ac {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}
.ac__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: linear-gradient(135deg, var(--ac), color-mix(in srgb, var(--ac) 65%, black));
  color: #fff;
}
.ac__avatar {
  height: 42px;
  width: 42px;
  border-radius: 50%;
  overflow: hidden;
  flex: none;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.2);
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 800;
  border: 2px solid rgba(255, 255, 255, 0.5);
}
.ac__avatar img { height: 100%; width: 100%; object-fit: cover; }
.ac__id strong { display: block; font-family: var(--font-serif); font-size: 16px; }
.ac__id small { display: block; margin-top: 2px; font-size: 12px; color: rgba(255, 255, 255, 0.78); }
.ac__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg);
}
.ac__empty { margin: auto 0; text-align: center; color: var(--muted); }
.ac__empty > p { margin-bottom: 14px; font-size: 14px; }
.ac__chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.ac__chip {
  padding: 7px 13px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--sub);
  font-size: 12.5px;
  transition: all 0.18s var(--ease);
}
.ac__chip:hover { border-color: var(--ac); color: var(--ac); transform: translateY(-1px); }
.ac__row { display: flex; }
.ac__row--user { justify-content: flex-end; }
.ac__bubble {
  max-width: 86%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14.5px;
  line-height: 1.7;
}
.ac__bubble--user {
  background: var(--ac);
  color: #fff;
  border-bottom-right-radius: 4px;
  white-space: pre-wrap;
}
.ac__bubble--assistant {
  background: var(--panel);
  color: var(--ink);
  border: 1px solid var(--line);
  border-bottom-left-radius: 4px;
}
.ac__err { color: var(--red); font-size: 13px; }
.ac__src { margin-top: 6px; color: var(--muted); font-size: 11.5px; }
.ac__typing { display: inline-flex; gap: 4px; padding: 4px 0; }
.ac__typing i {
  height: 7px; width: 7px; border-radius: 50%;
  background: var(--muted);
  animation: blink 1.2s infinite ease-in-out;
}
.ac__typing i:nth-child(2) { animation-delay: 0.2s; }
.ac__typing i:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 80%, 100% { opacity: 0.25; } 40% { opacity: 1; } }
.ac__foot {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--line);
  background: var(--panel);
}
.ac__input {
  flex: 1;
  resize: none;
  max-height: 120px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--bg);
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink);
}
.ac__input:focus { outline: none; border-color: var(--ac); }
.ac__send {
  flex: none;
  padding: 10px 18px;
  border-radius: 12px;
  background: var(--ac);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  transition: opacity 0.2s var(--ease);
}
.ac__send:disabled { opacity: 0.45; }
.ac__send--stop { background: var(--red); }
</style>
