<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AgentChat from '@/components/agent/AgentChat.vue'
import { listKBs, type KnowledgeBase } from '@/api/kb'

const route = useRoute()
const kbs = ref<KnowledgeBase[]>([])
const ready = ref(false)
const kbIds = computed(() => kbs.value.map((k) => k.id))
const initial = computed(() => (route.query.q as string) || '')
const chatKey = computed(() => route.fullPath)

const prompt = `你是豫章书院的文字问答助手「问书院」，负责为学生、教师和游客解答江西书院文化相关问题。
要求：
1. 只输出文字回答，不要承诺“下方已附图”“稍后附图”“如图所示”等图片相关内容。
2. 优先依据知识库内容作答；凡使用资料，请在对应句末标注来源编号，例如 [1][3]。
3. 资料不足时，明确说明“资料中未明确记载”或“资料不足以确认”，不要臆造书院史实、开放时间、票价、电话等实时信息。
4. 语气亲切、典雅、清晰，回答宜分段，适合学习和参观前了解。
5. 不要暴露你是 AI 模型，保持“书院问答助手”的身份。`

onMounted(async () => {
  try {
    kbs.value = await listKBs()
  } catch {
    kbs.value = []
  } finally {
    ready.value = true
  }
})
</script>

<template>
  <div class="qa">
    <div class="qa__hero">
      <div class="shell">
        <p class="eyebrow">问书院</p>
        <h1 class="h-serif">向豫章书院请教</h1>
        <p class="qa__lead">书院典籍、人物事迹、讲学源流、研学路线……尽可问来，即问即答，并尽量附上出处。</p>
      </div>
    </div>

    <div class="shell qa__body">
      <div class="qa__panel">
        <AgentChat
          v-if="ready"
          :key="chatKey"
          title="问书院 · 智能问答"
          subtitle="基于豫章书院知识库的问答"
          seal="问"
          accent="#2c3e50"
          :system-prompt="prompt"
          :kb-ids="kbIds"
          :initial="initial"
          :suggestions="['豫章书院的由来？', '白鹿洞书院揭示讲了什么？', '江右理学有哪些代表人物？']"
          placeholder="向书院请教，例如：鹅湖之会是怎么回事？"
        />
      </div>
      <p class="qa__tip">提示：问答内容由 AI 依据书院资料生成，仅供学习参考。</p>
    </div>
  </div>
</template>

<style scoped>
.qa { background: var(--bg); }
.qa__hero {
  padding: 56px 0 0;
  background:
    radial-gradient(circle at 88% 10%, rgba(237, 183, 79, 0.1), transparent 45%),
    var(--bg);
}
.qa__hero h1 { margin: 12px 0 0; font-size: clamp(28px, 3.6vw, 40px); font-weight: 800; color: var(--ink); }
.qa__lead { margin-top: 14px; max-width: 640px; color: var(--sub); line-height: 1.85; }
.qa__body { padding: 28px 0 72px; }
.qa__panel { height: 600px; }
.qa__tip { margin-top: 14px; text-align: center; color: var(--muted); font-size: 12.5px; }
@media (max-width: 680px) {
  .qa__panel { height: 70vh; }
}
</style>
