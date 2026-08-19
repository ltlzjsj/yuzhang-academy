import { http } from './http'

export interface Conversation {
  id: number
  title: string
  model: string
  system_prompt: string
  rag_enabled: boolean
  kb_ids: number[] | null
  temperature: number
  top_p: number
  top_k: number
  rerank: boolean
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  citations: any[] | null
  images?: any[] | null
  created_at: string
}

export async function listConversations() {
  const { data } = await http.get<Conversation[]>('/conversations')
  return data
}

export async function createConversation(payload: Partial<Conversation> = {}) {
  const { data } = await http.post<Conversation>('/conversations', payload)
  return data
}

export async function updateConversation(id: number, payload: Partial<Conversation>) {
  const { data } = await http.patch<Conversation>(`/conversations/${id}`, payload)
  return data
}

export async function deleteConversation(id: number) {
  await http.delete(`/conversations/${id}`)
}

export async function fetchMessages(id: number) {
  const { data } = await http.get<Message[]>(`/conversations/${id}/messages`)
  return data
}

export async function deleteMessageTail(conversationId: number, messageId: number) {
  await http.delete(`/conversations/${conversationId}/messages/${messageId}/tail`)
}
