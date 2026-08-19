<script setup lang="ts">
import { ref } from 'vue'
import PanoramaViewer from '@/components/panorama/PanoramaViewer.vue'

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}

interface Scene {
  id: string
  name: string
  desc: string
  src: string
}

const scenes: Scene[] = [
  { id: 'pano', name: '测试全景', desc: '2:1 等距柱状全景测试', src: assetUrl('360全景/测试图/panorama.jpg') },
  { id: 'gate', name: '书院正门', desc: '书院入口实景', src: assetUrl('360全景/正门/scene.jpg') },
  { id: 'aerial', name: '书院俯瞰', desc: '书院整体俯瞰实景', src: assetUrl('360全景/俯瞰图/scene.jpg') },
]

const active = ref<Scene>(scenes[0])
</script>

<template>
  <div class="tour">
    <section class="shell tour__head">
      <p class="eyebrow">书院实况</p>
      <h1 class="h-serif">实景导览</h1>
      <p class="tour__lead">
        拖动画面查看书院实景。放入 2:1 的 360° 全景图时，系统会自动切换为沉浸式环视模式。
      </p>
    </section>

    <section class="shell tour__body">
      <div class="tour__tabs">
        <button
          v-for="s in scenes"
          :key="s.id"
          type="button"
          class="tour__tab"
          :class="{ 'is-on': s.id === active.id }"
          @click="active = s"
        >{{ s.name }}</button>
      </div>

      <div class="tour__stage">
        <PanoramaViewer :src="active.src" :alt="active.name" />
      </div>

      <p class="tour__caption">{{ active.name }} · {{ active.desc }}</p>
    </section>
  </div>
</template>

<style scoped>
.tour {
  min-height: 100vh;
  background: var(--bg);
}
.tour__head {
  padding: 52px 0 16px;
  text-align: center;
}
.eyebrow {
  color: var(--gold-deep);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.tour__head h1 {
  margin: 8px 0 0;
  font-size: clamp(26px, 3.4vw, 40px);
  color: var(--ink);
}
.tour__lead {
  margin: 14px auto 0;
  max-width: 640px;
  color: var(--sub);
  font-size: 14.5px;
  line-height: 1.8;
}
.tour__body {
  padding-bottom: 56px;
}
.tour__tabs {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 16px;
}
.tour__tab {
  padding: 9px 22px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--sub);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s var(--ease);
}
.tour__tab.is-on {
  background: var(--navy);
  border-color: var(--navy);
  color: #fff;
}
.tour__stage {
  height: min(64vh, 640px);
  min-height: 420px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
  background: #10151c;
}
.tour__caption {
  margin-top: 12px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}
</style>
