import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  listKBs,
  createKB,
  deleteKB as apiDeleteKB,
  listDocuments,
  uploadDocument as apiUpload,
  deleteDocument as apiDeleteDoc,
  reingestDocument,
  updateDocumentMetadata,
  getDocument,
  type KnowledgeBase,
  type DocumentRow,
} from '@/api/kb'

export const useKBStore = defineStore('kb', () => {
  const list = ref<KnowledgeBase[]>([])
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      list.value = await listKBs()
    } finally {
      loading.value = false
    }
  }

  async function create(payload: Parameters<typeof createKB>[0]) {
    const kb = await createKB(payload)
    list.value.unshift(kb)
    return kb
  }

  async function remove(id: number) {
    await apiDeleteKB(id)
    list.value = list.value.filter((k) => k.id !== id)
  }

  // Documents are kept keyed by kb id
  const docsByKb = ref<Record<number, DocumentRow[]>>({})

  async function loadDocs(kbId: number) {
    docsByKb.value[kbId] = await listDocuments(kbId)
  }

  async function upload(kbId: number, file: File, onProgress?: (p: number) => void) {
    const row = await apiUpload(kbId, file, onProgress)
    const arr = docsByKb.value[kbId] || []
    docsByKb.value[kbId] = [row, ...arr]
    return row
  }

  async function removeDoc(doc: DocumentRow) {
    await apiDeleteDoc(doc.id)
    const arr = docsByKb.value[doc.kb_id] || []
    docsByKb.value[doc.kb_id] = arr.filter((d) => d.id !== doc.id)
  }

  async function reingest(doc: DocumentRow) {
    const row = await reingestDocument(doc.id)
    _replaceDoc(row)
    return row
  }

  async function refreshDoc(doc: DocumentRow): Promise<DocumentRow | null> {
    try {
      const row = await getDocument(doc.id)
      _replaceDoc(row)
      return row
    } catch {
      return null
    }
  }

  async function saveDocMetadata(
    doc: DocumentRow,
    metadata: Record<string, string | number | boolean | null>,
  ) {
    const row = await updateDocumentMetadata(doc.id, metadata)
    _replaceDoc(row)
    return row
  }

  function _replaceDoc(row: DocumentRow) {
    const arr = docsByKb.value[row.kb_id] || []
    const idx = arr.findIndex((d) => d.id === row.id)
    if (idx >= 0) arr[idx] = row
    else arr.unshift(row)
    docsByKb.value[row.kb_id] = [...arr]
  }

  return {
    list,
    loading,
    docsByKb,
    load,
    create,
    remove,
    loadDocs,
    upload,
    removeDoc,
    reingest,
    refreshDoc,
    saveDocMetadata,
  }
})
