import { nextTick, ref } from 'vue'
import { streamSSE } from '@/api/sse'
import { useAuthStore } from '@/stores/auth'

export interface AgentMessage {
  role: 'user' | 'assistant'
  content: string
  pending?: boolean
  error?: string
  sources?: number
}

export interface AgentChatOptions {
  systemPrompt: string
  kbIds?: number[]
  ragEnabled?: boolean
}

/**
 * Stateless persona chat — talks to `/agent/stream`, which persists nothing.
 * Kept deliberately independent from the main `chat` store / conversation list.
 */
export function useAgentChat(opts: () => AgentChatOptions) {
  const messages = ref<AgentMessage[]>([])
  const streaming = ref(false)
  let abort: AbortController | null = null

  function reset() {
    stop()
    messages.value = []
  }

  function stop() {
    if (abort) {
      abort.abort()
      abort = null
    }
    streaming.value = false
    const last = messages.value[messages.value.length - 1]
    if (last && last.pending) last.pending = false
  }

  async function send(text: string) {
    const content = text.trim()
    if (!content || streaming.value) return
    const auth = useAuthStore()
    const cfg = opts()

    messages.value.push({ role: 'user', content })
    const assistant: AgentMessage = { role: 'assistant', content: '', pending: true }
    messages.value.push(assistant)
    const live = messages.value[messages.value.length - 1]
    streaming.value = true
    await nextTick()

    const payload = {
      messages: messages.value
        .filter((m) => !m.error)
        .map((m) => ({ role: m.role, content: m.content })),
      system_prompt: cfg.systemPrompt,
      kb_ids: cfg.kbIds ?? [],
      rag_enabled: cfg.ragEnabled ?? true,
    }
    // The assistant placeholder we just pushed must not be sent as content.
    payload.messages = payload.messages.slice(0, -1)

    abort = streamSSE(
      '/api/v1/agent/stream',
      { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: payload },
      {
        onEvent: (event, data) => {
          if (event === 'citations') {
            live.sources = (data.items ?? []).length
          } else if (event === 'delta') {
            live.content += data.content ?? ''
          } else if (event === 'error') {
            live.error = data.message
          } else if (event === 'done') {
            live.pending = false
            streaming.value = false
            abort = null
          }
        },
        onError: (e) => {
          live.error = e.message
          live.pending = false
          streaming.value = false
          abort = null
        },
        onClose: () => {
          live.pending = false
          streaming.value = false
        },
      },
    )
  }

  return { messages, streaming, send, stop, reset }
}
