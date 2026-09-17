<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import DigitalHuman3D from '@/components/agent/DigitalHuman3D.vue'

const dh = ref<InstanceType<typeof DigitalHuman3D> | null>(null)
const playing = ref(false)
let timer: number | undefined

const phonemeSeq: Record<string, number>[] = [
  { jawOpen: 0.78, mouthStretchLeft: 0.12, mouthStretchRight: 0.12 },
  { jawOpen: 0.35, mouthFunnel: 0.45 },
  { jawOpen: 0.55, mouthPucker: 0.4 },
  { jawOpen: 0.15, mouthSmileLeft: 0.25, mouthSmileRight: 0.25 },
  { jawOpen: 0.05, mouthClose: 0.25 },
]

function setPhoneme(weights: Record<string, number>) {
  dh.value?.setPhoneme(weights)
}

function startMouthLoop() {
  if (timer) return
  playing.value = true
  let i = 0
  timer = window.setInterval(() => {
    setPhoneme(phonemeSeq[i % phonemeSeq.length])
    i += 1
  }, 170)
}

function stopMouthLoop() {
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
  setPhoneme({})
  playing.value = false
}

function openJawOnce() {
  setPhoneme({ jawOpen: 0.95 })
  window.setTimeout(() => setPhoneme({}), 650)
}

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="test-page">
    <div class="stage">
      <DigitalHuman3D ref="dh" src="/models/zhuxi_ue5.glb" :speaking="playing" :level="0" />
    </div>
    <div class="bar">
      <button type="button" @click="startMouthLoop">连续口型测试</button>
      <button type="button" @click="stopMouthLoop">停止</button>
      <button type="button" @click="openJawOnce">张嘴一次</button>
    </div>
  </div>
</template>

<style scoped>
.test-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #10131c;
  color: #f4f6fb;
}
.stage {
  flex: 1;
  min-height: 62vh;
}
.bar {
  padding: 14px 18px;
  display: flex;
  gap: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}
button {
  border: 0;
  border-radius: 10px;
  padding: 10px 16px;
  background: #c8a15a;
  color: #17120a;
  font-weight: 600;
  cursor: pointer;
}
button:hover {
  filter: brightness(1.06);
}
</style>
