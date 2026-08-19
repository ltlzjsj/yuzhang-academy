<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const newPresetName = ref('')

onMounted(() => settings.loadModels())

function pick(id: string) {
  settings.applyPreset(id)
}

function saveAsPreset() {
  const name = newPresetName.value.trim()
  if (!name) return
  settings.saveCustomPreset(name, settings.state.system_prompt)
  newPresetName.value = ''
}

function onPromptInput() {
  settings.state.active_preset_id = null
}

const nav = [
  { id: 'model', label: '模型' },
  { id: 'prompt', label: '提示词' },
  { id: 'rag', label: 'RAG' },
  { id: 'retrieval', label: '增强' },
]
</script>

<template>
  <section class="flex h-full min-w-0 bg-claude-bg">
    <aside class="hidden w-48 shrink-0 border-r border-claude-border bg-claude-panel/70 px-4 py-8 md:block">
      <h2 class="mb-6 text-lg font-semibold tracking-normal">设置</h2>
      <nav class="space-y-1 text-sm">
        <a
          v-for="item in nav"
          :key="item.id"
          :href="`#${item.id}`"
          class="block rounded-md px-3 py-2 text-claude-muted transition-colors hover:bg-white hover:text-claude-ink"
        >
          {{ item.label }}
        </a>
      </nav>
    </aside>

    <div class="settings-scroll flex-1 overflow-y-auto">
      <div class="mx-auto w-full max-w-4xl px-6 py-8 lg:px-10">
        <header class="mb-8">
          <p class="text-xs font-medium uppercase tracking-[0.18em] text-claude-accent">赣书院·智典</p>
          <h1 class="mt-2 text-2xl font-semibold">系统设置</h1>
          <p class="mt-2 max-w-2xl text-sm leading-relaxed text-claude-muted">
            调整模型行为、默认提示词和检索策略。这里的设置会作为新会话的默认值，也会影响当前聊天栏的快捷开关。
          </p>
        </header>

        <div class="divide-y divide-claude-border rounded-lg border border-claude-border bg-white/65">
          <section id="model" class="p-5">
            <div class="mb-5 flex items-start justify-between gap-4">
              <div>
                <h3 class="text-base font-medium">模型行为</h3>
                <p class="mt-1 text-xs text-claude-muted">控制默认对话模型和生成采样参数。</p>
              </div>
              <button class="btn-ghost px-3 py-1.5 text-xs" @click="settings.loadModels(true)">刷新模型</button>
            </div>

            <div class="grid gap-4 lg:grid-cols-2">
              <label class="block">
                <span class="mb-1 block text-xs text-claude-muted">对话模型</span>
                <select v-model="settings.state.model" class="input">
                  <option v-for="m in settings.models" :key="m.name" :value="m.name">
                    {{ m.name }}{{ m.parameter_size ? ` · ${m.parameter_size}` : '' }}
                  </option>
                </select>
              </label>

              <div class="rounded-md border border-claude-border bg-claude-bg/50 px-3 py-2 text-xs text-claude-muted">
                <div>嵌入模型</div>
                <div class="mt-1 truncate font-mono text-claude-ink">{{ settings.embed || '未加载' }}</div>
              </div>

              <div>
                <div class="mb-1 flex items-center justify-between text-xs">
                  <span class="text-claude-muted">Temperature</span>
                  <span class="font-mono">{{ settings.state.temperature.toFixed(2) }}</span>
                </div>
                <input v-model.number="settings.state.temperature" type="range" min="0" max="1.5" step="0.05" class="w-full" />
              </div>

              <div>
                <div class="mb-1 flex items-center justify-between text-xs">
                  <span class="text-claude-muted">Top P</span>
                  <span class="font-mono">{{ settings.state.top_p.toFixed(2) }}</span>
                </div>
                <input v-model.number="settings.state.top_p" type="range" min="0.1" max="1" step="0.05" class="w-full" />
              </div>
            </div>

            <label class="mt-4 flex cursor-pointer items-center gap-2 text-sm">
              <input v-model="settings.state.think" type="checkbox" class="accent-claude-accent" />
              显示/启用思考过程
              <span class="text-xs text-claude-muted">关闭时 reasoning 模型通常更快出现首个可见 token。</span>
            </label>
          </section>

          <section id="prompt" class="p-5">
            <div class="mb-4 flex items-baseline justify-between gap-4">
              <div>
                <h3 class="text-base font-medium">系统提示词</h3>
                <p class="mt-1 text-xs text-claude-muted">新会话默认使用，可保存为自定义预设。</p>
              </div>
              <span class="text-xs text-claude-muted">{{ settings.state.system_prompt.length }} 字符</span>
            </div>

            <div class="mb-3 flex flex-wrap gap-2">
              <button
                v-for="p in settings.allPresets"
                :key="p.id"
                class="group flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs transition-colors"
                :class="
                  settings.state.active_preset_id === p.id
                    ? 'border-claude-accent bg-claude-accent/10 text-claude-accent'
                    : 'border-claude-border bg-white text-claude-ink hover:border-claude-accent/40'
                "
                @click="pick(p.id)"
              >
                {{ p.name }}
                <span
                  v-if="!p.builtin"
                  class="ml-1 text-claude-muted hover:text-red-600"
                  title="删除"
                  @click.stop="settings.deletePreset(p.id)"
                >
                  x
                </span>
              </button>
            </div>

            <textarea
              v-model="settings.state.system_prompt"
              rows="11"
              class="input resize-y font-mono text-xs leading-relaxed"
              placeholder="定义模型的角色、能力范围和输出风格"
              @input="onPromptInput"
            />

            <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
              <input
                v-model="newPresetName"
                class="input flex-1 text-xs"
                placeholder="预设名称，例如：书院 · 沿革讲学助手"
                @keyup.enter="saveAsPreset"
              />
              <button
                class="btn-primary px-3 py-1.5 text-xs"
                :disabled="!newPresetName.trim() || !settings.state.system_prompt.trim()"
                @click="saveAsPreset"
              >
                保存为预设
              </button>
            </div>
          </section>

          <section id="rag" class="p-5">
            <div class="mb-4">
              <h3 class="text-base font-medium">RAG 基础设置</h3>
              <p class="mt-1 text-xs text-claude-muted">控制默认是否使用知识库，以及每次注入多少上下文。</p>
            </div>

            <div class="space-y-4">
              <label class="flex cursor-pointer items-center gap-2 text-sm">
                <input v-model="settings.state.rag_enabled" type="checkbox" class="accent-claude-accent" />
                新会话默认开启 RAG
                <span class="text-xs text-claude-muted">Chat 顶栏仍可临时切换。</span>
              </label>

              <div>
                <div class="mb-1 flex items-center justify-between text-xs">
                  <span class="text-claude-muted">top_k · 每次检索返回的块数</span>
                  <span class="font-mono">{{ settings.state.top_k }}</span>
                </div>
                <input v-model.number="settings.state.top_k" type="range" min="1" max="20" step="1" class="w-full" />
                <p class="mt-1 text-[11px] text-claude-muted">建议 4-6。越大上下文越长，模型响应压力也越大。</p>
              </div>

              <div class="rounded-md border border-claude-border bg-claude-bg/50 px-3 py-2 text-xs text-claude-muted">
                当前选中知识库：
                <span v-if="!(settings.state.kb_ids || []).length">无，请在 Chat 顶栏选择</span>
                <span v-else class="font-mono text-claude-ink">{{ (settings.state.kb_ids || []).join(', ') }}</span>
              </div>
            </div>
          </section>

          <section id="retrieval" class="p-5">
            <div class="mb-4">
              <h3 class="text-base font-medium">增强检索</h3>
              <p class="mt-1 text-xs text-claude-muted">提升召回或排序质量，但会增加后台或聊天时延。</p>
            </div>

            <div class="space-y-4">
              <label class="flex cursor-pointer items-center gap-2 text-sm">
                <input v-model="settings.state.rerank" type="checkbox" class="accent-claude-accent" />
                启用 Rerank 重排
                <span class="text-xs text-claude-muted">仅在检索相关后运行。</span>
              </label>

              <p class="rounded-md border border-claude-border bg-claude-bg/50 px-3 py-2 text-xs leading-relaxed text-claude-muted">
                Q&A 增强按需生成。聊天检索会优先使用高置信 Q&A 命中，再回溯原文 chunk/PDF 作为证据；低置信 Q&A 只参与排序增强。
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  </section>
</template>
