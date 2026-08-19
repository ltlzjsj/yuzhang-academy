<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useKBStore } from '@/stores/kb'
import { updateKB } from '@/api/kb'

const kb = useKBStore()
const router = useRouter()

async function togglePublic(item: { id: number; is_public: boolean }) {
  await updateKB(item.id, { is_public: !item.is_public })
  await kb.load()
}

const showCreate = ref(false)
const form = ref({
  name: '',
  description: '',
  chunk_size: 512,
  chunk_overlap: 50,
  qa_enabled: false,
})
const creating = ref(false)
const err = ref('')

onMounted(() => kb.load())

async function submit() {
  err.value = ''
  if (!form.value.name.trim()) return
  creating.value = true
  try {
    const created = await kb.create({ ...form.value, name: form.value.name.trim() })
    showCreate.value = false
    form.value = { name: '', description: '', chunk_size: 512, chunk_overlap: 50, qa_enabled: false }
    router.push(`/admin/kb/${created.id}`)
  } catch (e: any) {
    err.value = e.response?.data?.detail || e.message
  } finally {
    creating.value = false
  }
}

async function onDelete(id: number, name: string) {
  if (!confirm(`删除知识库 "${name}" 及其所有文档和向量？此操作不可恢复。`)) return
  await kb.remove(id)
}
</script>

<template>
  <section class="mx-auto h-full w-full max-w-5xl overflow-y-auto px-8 py-10">
    <div class="mb-6 flex items-center justify-between">
      <h2 class="font-serif text-2xl">知识库</h2>
      <button class="btn-primary" @click="showCreate = true">+ 新建知识库</button>
    </div>

    <div v-if="kb.loading" class="py-12 text-center text-sm text-claude-muted">加载中…</div>

    <div v-else-if="!kb.list.length" class="card py-12 text-center text-claude-muted">
      <p class="mb-4">还没有知识库</p>
      <button class="btn-primary" @click="showCreate = true">创建第一个知识库</button>
    </div>

    <div v-else class="grid gap-3">
      <RouterLink
        v-for="item in kb.list"
        :key="item.id"
        :to="`/admin/kb/${item.id}`"
        class="card flex items-center gap-4 p-5 transition-all hover:border-claude-accent/40 hover:shadow-md"
      >
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-claude-accent/10 text-claude-accent">
          <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline gap-2">
            <h3 class="truncate text-base font-medium">{{ item.name }}</h3>
            <span class="text-xs text-claude-muted">#{{ item.id }}</span>
          </div>
          <p v-if="item.description" class="mt-0.5 line-clamp-1 text-sm text-claude-muted">
            {{ item.description }}
          </p>
          <div class="mt-1 flex gap-4 text-xs text-claude-muted">
            <span>{{ item.document_count }} 文档</span>
            <span>{{ item.chunk_count }} chunks</span>
            <span>切块 {{ item.chunk_size }}/{{ item.chunk_overlap }}</span>
          </div>
        </div>
        <button
          class="btn-ghost text-xs"
          :class="item.is_public ? 'text-emerald-600 hover:bg-emerald-50' : 'text-claude-muted hover:bg-claude-border/40'"
          :title="item.is_public ? '已公开（公众可用于问书院/答题）· 点击转为私有' : '私有 · 点击设为公开'"
          @click.prevent.stop="togglePublic(item)"
        >
          {{ item.is_public ? '● 公开' : '○ 私有' }}
        </button>
        <button
          class="btn-ghost text-xs text-red-600 hover:bg-red-50"
          @click.prevent.stop="onDelete(item.id, item.name)"
        >
          删除
        </button>
      </RouterLink>
    </div>

    <!-- Create modal -->
    <div
      v-if="showCreate"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/20 p-4"
      @click.self="showCreate = false"
    >
      <div class="card w-[440px] p-6">
        <h3 class="mb-4 font-serif text-xl">新建知识库</h3>
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-xs text-claude-muted">名称</label>
            <input v-model="form.name" class="input" placeholder="例如：斑岩铜矿文献库" />
          </div>
          <div>
            <label class="mb-1 block text-xs text-claude-muted">描述</label>
            <textarea v-model="form.description" rows="2" class="input resize-none" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-xs text-claude-muted">
                chunk_size <span class="text-claude-ink font-mono">{{ form.chunk_size }}</span>
              </label>
              <input v-model.number="form.chunk_size" type="range" min="256" max="1024" step="64" class="w-full" />
            </div>
            <div>
              <label class="mb-1 block text-xs text-claude-muted">
                overlap <span class="text-claude-ink font-mono">{{ form.chunk_overlap }}</span>
              </label>
              <input v-model.number="form.chunk_overlap" type="range" min="0" max="200" step="10" class="w-full" />
            </div>
          </div>
          <label class="flex items-center gap-2 rounded-lg border border-claude-border bg-claude-bg/40 p-3 text-sm">
            <input v-model="form.qa_enabled" type="checkbox" class="h-4 w-4" />
            <span class="flex-1">
              <span class="font-medium">启用 Q&amp;A 生成</span>
              <span class="ml-2 text-xs text-claude-muted">文档入库后自动基于 chunk 产生问答对,提升召回</span>
            </span>
          </label>
          <p v-if="err" class="text-sm text-red-600">{{ err }}</p>
        </div>
        <div class="mt-5 flex justify-end gap-2">
          <button class="btn-ghost" @click="showCreate = false">取消</button>
          <button class="btn-primary" :disabled="!form.name.trim() || creating" @click="submit">
            {{ creating ? '创建中…' : '创建' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
