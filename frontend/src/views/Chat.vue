<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue'
import ConversationList from '@/components/chat/ConversationList.vue'
import Composer from '@/components/chat/Composer.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { listKBs, type KnowledgeBase } from '@/api/kb'

const chat = useChatStore()
const settings = useSettingsStore()
const MessageBubble = defineAsyncComponent(() => import('@/components/chat/MessageBubble.vue'))

const scroller = ref<HTMLDivElement | null>(null)
const kbs = ref<KnowledgeBase[]>([])
const kbPickerOpen = ref(false)

const empty = computed(() => chat.messages.length === 0 && !chat.streaming)
const selectedKbLabel = computed(() => {
  if (!settings.state.rag_enabled) return 'RAG 已关闭'
  const ids = settings.state.kb_ids || []
  if (!ids.length) return '未选择知识库'
  if (ids.length === 1) {
    const kb = kbs.value.find((item) => item.id === ids[0])
    return kb ? kb.name : `知识库 #${ids[0]}`
  }
  return `${ids.length} 个知识库`
})

async function scrollToBottom() {
  await nextTick()
  const el = scroller.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}

watch(
  () => chat.messages.map((m) => m.content.length).join('|'),
  () => scrollToBottom(),
)
watch(
  () => chat.activeId,
  () => scrollToBottom(),
)

onMounted(async () => {
  await Promise.all([chat.loadList(), settings.loadModels()])
  try {
    kbs.value = await listKBs()
    settings.reconcileKbIds(kbs.value.map((kb) => kb.id))
  } catch {
    kbs.value = []
    settings.reconcileKbIds([])
  }
})

function toggleKb(id: number) {
  const set = new Set(settings.state.kb_ids || [])
  if (set.has(id)) set.delete(id)
  else set.add(id)
  settings.state.kb_ids = Array.from(set)
}

function onSubmit(text: string) {
  chat.send(text)
}
</script>

<template>
  <div class="chat-page">
    <ConversationList />

    <section class="chat-main">
      <header class="chat-toolbar">
        <div class="min-w-0">
          <p>智能问答</p>
          <h1>{{ chat.active?.title ?? '新的书院问答' }}</h1>
        </div>

        <select v-model="settings.state.model" class="toolbar-select">
          <option v-if="!settings.models.length" :value="settings.state.model">
            {{ settings.state.model || '默认模型' }}
          </option>
          <option v-for="m in settings.models" :key="m.name" :value="m.name">
            {{ m.name }}
          </option>
        </select>

        <label class="toolbar-toggle" :class="{ active: settings.state.rag_enabled }">
          <input v-model="settings.state.rag_enabled" type="checkbox" />
          RAG
        </label>

        <label class="toolbar-toggle" :class="{ active: settings.state.think }" title="开启后显示模型思考过程">
          <input v-model="settings.state.think" type="checkbox" />
          思考
        </label>

        <div class="relative">
          <button
            class="kb-picker-button"
            :disabled="!settings.state.rag_enabled"
            @click="kbPickerOpen = !kbPickerOpen"
          >
            {{ selectedKbLabel }}
          </button>
          <div v-if="kbPickerOpen" class="fixed inset-0 z-20" @click="kbPickerOpen = false" />
          <div v-if="kbPickerOpen" class="kb-picker-menu">
            <div v-if="!kbs.length" class="px-3 py-2 text-xs text-claude-muted">还没有知识库</div>
            <label v-for="kb in kbs" :key="kb.id" class="kb-picker-item">
              <input
                type="checkbox"
                :checked="(settings.state.kb_ids || []).includes(kb.id)"
                @change="toggleKb(kb.id)"
              />
              <span>{{ kb.name }}</span>
              <small>{{ kb.chunk_count }} 切片</small>
            </label>
          </div>
        </div>

        <div class="ml-auto text-xs text-claude-muted">
          温度 {{ settings.state.temperature.toFixed(2) }}
        </div>
      </header>

      <div ref="scroller" class="chat-scroll">
        <div v-if="chat.loading && !chat.messages.length" class="chat-centered">
          <div class="chat-pill">正在加载历史会话...</div>
        </div>
        <div v-else-if="empty" class="chat-empty">
          <p>豫章书院智能问答</p>
          <h2>可以问书院历史、人物、事件，也可以追问图片中的细节</h2>
          <span>开启 RAG 并选择知识库后，回答会尽量附带引用与相关图像。</span>
        </div>
        <div v-else class="chat-message-list">
          <MessageBubble
            v-for="m in chat.messages"
            :key="m.id"
            v-memo="[m.id, m.content.length, m.pending, m.images?.length, m.citations?.length]"
            :msg="m"
            @regenerate="chat.regenerateResponse"
          />
        </div>
      </div>

      <Composer :streaming="chat.streaming" @submit="onSubmit" @stop="chat.stopStreaming()" />
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  background: var(--bg);
}

.chat-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  background: var(--bg);
}

.chat-toolbar {
  display: flex;
  min-height: 68px;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
  padding: 10px 22px;
  backdrop-filter: blur(12px);
}

.chat-toolbar p {
  color: var(--gold-deep);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
  margin: 0 0 2px;
}

.chat-toolbar h1 {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 18px;
  margin: 0;
  color: var(--ink);
}

.toolbar-select,
.toolbar-toggle,
.kb-picker-button {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: var(--ink);
  font-size: 12px;
  padding: 7px 10px;
}

.toolbar-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
}

.toolbar-toggle.active,
.kb-picker-button:hover {
  border-color: var(--navy);
  color: var(--navy);
}

.kb-picker-menu {
  position: absolute;
  left: 0;
  top: calc(100% + 8px);
  z-index: 30;
  min-width: 250px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fff;
  box-shadow: var(--shadow-lift);
}

.kb-picker-item {
  display: flex;
  cursor: pointer;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
}

.kb-picker-item:hover {
  background: rgba(44, 62, 80, 0.07);
}

.kb-picker-item span {
  flex: 1;
}

.kb-picker-item small {
  color: var(--muted);
}

.chat-scroll {
  flex: 1;
  overflow-y: auto;
}

.chat-centered,
.chat-empty {
  display: grid;
  height: 100%;
  place-items: center;
  text-align: center;
}

.chat-pill {
  border-radius: 999px;
  background: #fff;
  color: var(--sub);
  padding: 9px 14px;
  box-shadow: var(--shadow-soft);
}

.chat-empty {
  align-content: center;
  color: var(--sub);
  padding: 24px;
}

.chat-empty p {
  color: var(--gold-deep);
  font-weight: 900;
  letter-spacing: 0.12em;
}

.chat-empty h2 {
  max-width: 620px;
  color: var(--ink);
  font-family: var(--font-serif);
  font-size: 34px;
  line-height: 1.28;
  margin: 10px 0;
}

.chat-message-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin: 0 auto;
  max-width: 850px;
  padding: 30px 18px;
}
</style>
