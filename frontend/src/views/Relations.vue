<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

// 关系图已改为一张实拍+立绘合成的图谱，点击可放大查看
const zoomOpen = ref(false)
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') zoomOpen.value = false
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

const timeline = [
  { year: '北宋', title: '周敦颐开理学之端', desc: '濂学兴于江右，为宋明理学导夫先路。' },
  { year: '南宋 · 淳熙二年（1175）', title: '鹅湖之会', desc: '吕祖谦邀朱熹、陆九渊会讲，论“尊德性”与“道问学”。' },
  { year: '南宋', title: '朱熹重兴白鹿洞书院', desc: '亲订《白鹿洞书院揭示》，确立为学之序与修身之要。' },
  { year: '南宋', title: '陆九渊象山讲学', desc: '倡“心即理”“发明本心”，心学自成体系。' },
  { year: '南宋', title: '白鹭洲书院兴学', desc: '庐陵“文章节义”之教兴，文天祥曾就读于此。' },
  { year: '明', title: '王阳明倡知行合一', desc: '承接陆九渊心学，以“致良知”成一代之教。' },
]
</script>

<template>
  <div class="rel">
    <section class="shell rel__head">
      <p class="eyebrow">理学图谱</p>
      <h1 class="h-serif">江右理学 · 人物与脉络</h1>
      <p class="rel__lead">从朱陆论辩到阳明心学，看江西书院与理学的传承脉络。</p>
    </section>

    <section class="shell rel__panel">
      <h2 class="rel__h">人物关系图</h2>
      <div class="rel__graph">
        <img
          class="rel__mapImg"
          src="/assets/relations/lixue-relations-map.png"
          alt="江右理学人物与脉络图：罗从彦、朱熹、吕祖谦、陆九渊、王阳明，及白鹿洞、鹅湖、象山、白鹭洲四座书院"
          @click="zoomOpen = true"
        />
        <p class="rel__hint">点击图片放大查看</p>
      </div>
    </section>

    <div
      v-if="zoomOpen"
      class="rel__zoom"
      role="dialog"
      aria-label="人物关系图放大预览"
      @click="zoomOpen = false"
    >
      <img src="/assets/relations/lixue-relations-map.png" alt="江右理学人物与脉络图" />
      <p class="rel__zoomHint">点击任意位置关闭</p>
    </div>

    <section class="shell rel__panel">
      <h2 class="rel__h">理学时间轴</h2>
      <ol class="rel__timeline">
        <li v-for="t in timeline" :key="t.title" class="rel__item">
          <span class="rel__dot" />
          <div>
            <span class="rel__year">{{ t.year }}</span>
            <h3 class="h-serif">{{ t.title }}</h3>
            <p>{{ t.desc }}</p>
          </div>
        </li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.rel { min-height: 100vh; background: var(--bg); padding-bottom: 64px; }
.rel__head { padding: 48px 0 24px; text-align: center; }
.eyebrow { color: var(--gold-deep); font-size: 13px; font-weight: 700; letter-spacing: .08em; }
.rel__head h1 { margin: 8px 0 0; font-size: clamp(26px, 3.4vw, 40px); font-weight: 800; color: var(--ink); }
.rel__lead { margin: 12px auto 0; color: var(--sub); font-size: 14.5px; }
.rel__panel { margin-bottom: 24px; padding: 24px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.rel__h { font-size: 20px; font-weight: 800; color: var(--ink); }
.rel__graph { margin-top: 16px; }
.rel__mapImg {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 12px;
  cursor: zoom-in;
}
.rel__hint {
  margin: 10px 0 0;
  text-align: center;
  color: var(--muted);
  font-size: 12.5px;
}

/* 点击放大：铺满整屏看图，点任意位置（或 Esc）关闭 */
.rel__zoom {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 2vh 2vw;
  background: rgba(6, 10, 14, 0.92);
  cursor: zoom-out;
}
.rel__zoom img {
  max-width: 96vw;
  max-height: 88vh;
  border-radius: 10px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
}
.rel__zoomHint { margin: 0; color: rgba(255, 255, 255, 0.74); font-size: 13px; }
.rel__timeline { list-style: none; padding: 0; margin: 18px 0 0; }
.rel__item { position: relative; display: flex; gap: 16px; padding: 0 0 24px 10px; }
.rel__item::before { content: ''; position: absolute; left: 7px; top: 16px; bottom: 0; width: 2px; background: var(--line); }
.rel__item:last-child::before { display: none; }
.rel__dot { flex: none; width: 12px; height: 12px; margin-top: 4px; border-radius: 50%; background: var(--gold); }
.rel__year { color: var(--gold-deep); font-size: 13px; font-weight: 700; }
.rel__item h3 { margin: 4px 0; font-size: 18px; font-weight: 800; color: var(--ink); }
.rel__item p { color: var(--sub); font-size: 14px; line-height: 1.7; }
</style>
