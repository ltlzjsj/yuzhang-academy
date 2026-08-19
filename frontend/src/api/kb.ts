import { http } from './http'

export interface KnowledgeBase {
  id: number
  name: string
  description: string
  owner_id: number
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  qa_enabled: boolean
  qa_model: string | null
  qa_pairs_per_chunk: number
  qdrant_collection: string
  is_public: boolean
  created_at: string
  document_count: number
  chunk_count: number
}

export interface DocumentRow {
  id: number
  kb_id: number
  filename: string
  size_bytes: number
  pages: number
  status: string
  progress: number
  error: string | null
  metadata: Record<string, string | number | boolean | null> | null
  image_count: number
  image_preview: Array<{
    src: string
    page?: number | null
    caption?: string
    kind?: string
  }>
  created_at: string
  updated_at: string
}

export interface ChunkRow {
  id: number
  document_id: number
  kb_id: number
  seq: number
  text: string
  page: number | null
  token_count: number
  metadata: Record<string, any> | null
}

export interface ChunkPage {
  total: number
  page: number
  size: number
  items: ChunkRow[]
}

export async function listKBs() {
  return (await http.get<KnowledgeBase[]>('/kb')).data
}

export async function createKB(payload: {
  name: string
  description?: string
  chunk_size?: number
  chunk_overlap?: number
  qa_enabled?: boolean
}) {
  return (await http.post<KnowledgeBase>('/kb', payload)).data
}

export async function getKB(id: number) {
  return (await http.get<KnowledgeBase>(`/kb/${id}`)).data
}

export async function updateKB(id: number, payload: Partial<KnowledgeBase>) {
  return (await http.patch<KnowledgeBase>(`/kb/${id}`, payload)).data
}

export async function deleteKB(id: number) {
  await http.delete(`/kb/${id}`)
}

export async function listDocuments(kbId: number) {
  return (await http.get<DocumentRow[]>('/documents', { params: { kb_id: kbId } })).data
}

export async function uploadDocument(kbId: number, file: File, onProgress?: (p: number) => void) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<DocumentRow>('/documents/upload', form, {
    params: { kb_id: kbId },
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
  return data
}

export async function getDocument(id: number) {
  return (await http.get<DocumentRow>(`/documents/${id}`)).data
}

export async function deleteDocument(id: number) {
  await http.delete(`/documents/${id}`)
}

export async function reingestDocument(id: number) {
  return (await http.post<DocumentRow>(`/documents/${id}/reingest`)).data
}

export async function updateDocumentMetadata(
  id: number,
  metadata: Record<string, string | number | boolean | null>,
) {
  return (await http.patch<DocumentRow>(`/documents/${id}/metadata`, { metadata })).data
}

export async function listChunks(documentId: number, page = 1, size = 20) {
  return (
    await http.get<ChunkPage>('/chunks', {
      params: { document_id: documentId, page, size },
    })
  ).data
}

export interface QaStats {
  kb_id: number
  document_id?: number
  pairs: number
  covered_chunks: number
  total_chunks: number
}

export async function getKbQaStats(kbId: number) {
  return (await http.get<QaStats>(`/kb/${kbId}/qa/stats`)).data
}

export async function getDocQaStats(docId: number) {
  return (await http.get<QaStats>(`/documents/${docId}/qa/stats`)).data
}

export async function generateKbQA(kbId: number, model?: string) {
  return (await http.post(`/kb/${kbId}/qa/generate`, null, {
    params: model ? { model } : undefined,
  })).data
}

export async function generateDocQA(docId: number, model?: string) {
  return (await http.post(`/documents/${docId}/qa/generate`, null, {
    params: model ? { model } : undefined,
  })).data
}

export interface QaPair {
  id: number
  chunk_id: number
  kb_id: number
  document_id: number
  filename: string
  page: number | null
  question: string
  answer: string
  created_at: string | null
}

export interface QaPage {
  total: number
  page: number
  size: number
  items: QaPair[]
}

export async function listQaPairs(params: {
  kb_id: number
  document_id?: number
  q?: string
  page?: number
  size?: number
}) {
  return (await http.get<QaPage>('/qa', { params })).data
}

export async function deleteQaPair(qaId: number) {
  await http.delete(`/qa/${qaId}`)
}
