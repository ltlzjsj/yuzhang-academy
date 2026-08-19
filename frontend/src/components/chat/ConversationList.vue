<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

const grouped = computed(() => {
  const now = new Date()
  const today: typeof chat.conversations = []
  const week: typeof chat.conversations = []
  const older: typeof chat.conversations = []
  for (const c of chat.conversations) {
    const d = new Date(c.updated_at)
    const diffDays = (now.getTime() - d.getTime()) / 86_400_000
    if (diffDays < 1) today.push(c)
    else if (diffDays < 7) week.push(c)
    else older.push(c)
  }
  return { today, week, older }
})

async function onDelete(id: number, e: Event) {
  e.stopPropagation()
  if (!confirm('删除此会话？')) return
  await chat.remove(id)
}
</script>

<template>
  <div class="flex h-full w-64 flex-col border-r border-claude-border bg-claude-panel">
    <div class="flex items-center justify-between px-4 pb-2 pt-4">
      <h2 class="font-serif text-lg">赣书院·智典</h2>
    </div>
    <button
      class="mx-3 mb-3 flex items-center gap-2 rounded-xl border border-claude-border bg-white px-3 py-2 text-sm text-claude-ink shadow-soft transition-colors hover:border-claude-accent/40 hover:bg-claude-bubbleUser"
      @click="chat.startNew()"
    >
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
      新建对话
    </button>

    <div class="flex-1 overflow-y-auto px-2 pb-4 text-sm">
      <template v-for="(list, label) in grouped" :key="label">
        <div v-if="list.length" class="mb-2">
          <div class="px-2 py-1 text-[11px] font-medium uppercase tracking-wider text-claude-muted">
            {{ label === 'today' ? '今天' : label === 'week' ? '最近 7 天' : '更早' }}
          </div>
          <ul>
            <li
              v-for="c in list"
              :key="c.id"
              class="group mb-0.5 flex min-h-8 cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 transition-colors"
              :class="c.id === chat.activeId ? 'bg-claude-border/80 font-medium' : 'hover:bg-claude-border/50'"
              @click="chat.selectConversation(c.id)"
            >
              <span class="min-w-0 flex-1 truncate leading-5">{{ c.title }}</span>
              <button
                class="flex h-6 w-6 shrink-0 items-center justify-center rounded text-claude-muted opacity-0 transition-opacity hover:bg-claude-border hover:text-red-600 group-hover:opacity-100 focus:opacity-100"
                title="删除"
                @click="onDelete(c.id, $event)"
              >
                <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
              </button>
            </li>
          </ul>
        </div>
      </template>
      <p v-if="!chat.conversations.length" class="px-3 py-6 text-center text-xs text-claude-muted">
        还没有对话
      </p>
    </div>
  </div>
</template>
