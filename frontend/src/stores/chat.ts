import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  listConversations,
  fetchMessages,
  deleteConversation as apiDelete,
  deleteMessageTail,
  updateConversation as apiUpdate,
  type Conversation,
  type Message,
} from '@/api/conversations'
import { streamSSE } from '@/api/sse'
import { useAuthStore } from './auth'
import { useSettingsStore } from './settings'

export interface UiMessage {
  id: number | string
  role: 'user' | 'assistant' | 'system'
  content: string
  thinking?: string
  citations?: any[] | null
  images?: any[] | null
  pending?: boolean
  error?: string
  stage?: 'starting' | 'retrieving' | 'thinking' | 'generating'
  statusText?: string
}

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const activeId = ref<number | null>(null)
  const messages = ref<UiMessage[]>([])
  const streaming = ref(false)
  const loading = ref(false)
  let abortCtrl: AbortController | null = null

  const active = computed<Conversation | null>(
    () => conversations.value.find((c) => c.id === activeId.value) ?? null,
  )

  async function loadList() {
    conversations.value = await listConversations()
  }

  async function selectConversation(id: number | null) {
    stopStreaming()
    activeId.value = id
    messages.value = []
    if (id == null) return
    loading.value = true
    try {
      const rows = await fetchMessages(id)
      messages.value = rows.map((m: Message) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations,
        images: m.images,
      }))
    } finally {
      loading.value = false
    }
  }

  function startNew() {
    stopStreaming()
    activeId.value = null
    messages.value = []
  }

  function stopStreaming() {
    if (abortCtrl) {
      abortCtrl.abort()
      abortCtrl = null
    }
    streaming.value = false
  }

  async function send(text: string) {
    if (!text.trim() || streaming.value) return
    const auth = useAuthStore()
    const settings = useSettingsStore()

    messages.value.push({
      id: `tmp-u-${Date.now()}`,
      role: 'user',
      content: text,
    })
    messages.value.push({
      id: `tmp-a-${Date.now()}`,
      role: 'assistant',
      content: '',
      pending: true,
      stage: 'starting',
      statusText: '准备中',
    })
    // Use the reactive proxies that Vue created on push; mutating the raw
    // local objects would NOT trigger per-delta re-renders.
    const userMsg = messages.value[messages.value.length - 2]
    const assistantMsg = messages.value[messages.value.length - 1]
    streaming.value = true

    const payload = {
      conversation_id: activeId.value,
      message: text,
      model: settings.state.model,
      system_prompt: settings.state.system_prompt,
      temperature: settings.state.temperature,
      top_p: settings.state.top_p,
      rag_enabled: settings.state.rag_enabled,
      kb_ids: settings.state.kb_ids,
      top_k: settings.state.top_k,
      rerank: settings.state.rerank,
      think: settings.state.think,
    }

    abortCtrl = streamSSE(
      '/api/v1/chat/stream',
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },
        body: payload,
      },
      {
        onEvent: async (event, data) => {
          if (event === 'meta') {
            if (!activeId.value && data.conversation_id) {
              activeId.value = data.conversation_id
              loadList().catch(() => {})
            }
            userMsg.id = data.user_message_id ?? userMsg.id
            assistantMsg.stage = 'starting'
            assistantMsg.statusText = '连接模型'
          } else if (event === 'retrieving') {
            assistantMsg.stage = 'retrieving'
            assistantMsg.statusText = '检索知识库'
          } else if (event === 'rag_skipped') {
            assistantMsg.stage = 'generating'
            assistantMsg.statusText = '直接生成'
          } else if (event === 'citations') {
            assistantMsg.citations = data.items ?? []
          } else if (event === 'images') {
            assistantMsg.images = data.items ?? []
          } else if (event === 'warning') {
            assistantMsg.stage = 'generating'
            assistantMsg.statusText = '继续生成'
          } else if (event === 'thinking') {
            assistantMsg.stage = 'thinking'
            assistantMsg.statusText = '思考中'
            assistantMsg.thinking = (assistantMsg.thinking || '') + (data.content ?? '')
          } else if (event === 'delta') {
            assistantMsg.stage = 'generating'
            assistantMsg.statusText = '生成中'
            assistantMsg.content += data.content ?? ''
          } else if (event === 'error') {
            assistantMsg.error = data.message
          } else if (event === 'done') {
            assistantMsg.id = data.assistant_message_id ?? assistantMsg.id
            assistantMsg.pending = false
            assistantMsg.stage = undefined
            assistantMsg.statusText = undefined
            streaming.value = false
            abortCtrl = null
            loadList().catch(() => {})
          }
        },
        onError: (e) => {
          if (/SSE 403:/.test(e.message) && /知识库|鐭ヨ瘑搴/.test(e.message)) {
            settings.state.kb_ids = []
          }
          assistantMsg.error = e.message
          assistantMsg.pending = false
          assistantMsg.stage = undefined
          assistantMsg.statusText = undefined
          streaming.value = false
          abortCtrl = null
        },
        onClose: () => {
          assistantMsg.pending = false
          assistantMsg.stage = undefined
          assistantMsg.statusText = undefined
          streaming.value = false
        },
      },
    )
  }

  async function regenerateResponse(assistantMessageId: number | string) {
    if (streaming.value) return
    const assistantIdx = messages.value.findIndex((m) => m.id === assistantMessageId)
    if (assistantIdx <= 0 || messages.value[assistantIdx]?.role !== 'assistant') return

    let userIdx = assistantIdx - 1
    while (userIdx >= 0 && messages.value[userIdx]?.role !== 'user') userIdx -= 1
    if (userIdx < 0) return

    const userMsg = messages.value[userIdx]
    const text = userMsg.content
    if (!text.trim()) return

    if (activeId.value && typeof userMsg.id === 'number') {
      await deleteMessageTail(activeId.value, userMsg.id)
    }
    messages.value.splice(userIdx)
    await send(text)
  }

  async function remove(id: number) {
    await apiDelete(id)
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (activeId.value === id) startNew()
  }

  async function rename(id: number, title: string) {
    const updated = await apiUpdate(id, { title } as any)
    const idx = conversations.value.findIndex((c) => c.id === id)
    if (idx >= 0) conversations.value[idx] = updated
  }

  return {
    conversations,
    activeId,
    active,
    messages,
    streaming,
    loading,
    loadList,
    selectConversation,
    startNew,
    send,
    regenerateResponse,
    stopStreaming,
    remove,
    rename,
  }
})
