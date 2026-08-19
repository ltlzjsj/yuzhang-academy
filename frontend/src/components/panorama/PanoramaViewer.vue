<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ src: string; alt?: string }>()

const wrap = ref<HTMLDivElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const photoEl = ref<HTMLImageElement | null>(null)
const mode = ref<'loading' | 'panorama' | 'photo' | 'error'>('loading')

// 普通照片：平移 + 缩放状态
let fitScale = 1
let scale = 1
let tx = 0
let ty = 0
let photoDrag = false
let photoStart = { x: 0, y: 0, tx: 0, ty: 0 }
let photoCleanup: (() => void) | null = null

// 360 全景：Three.js 状态
let renderer: any = null
let scene: any = null
let camera: any = null
let yaw = 0
let pitch = 0
let raf = 0
let panoCleanup: (() => void) | null = null

function applyPhoto() {
  if (photoEl.value) {
    photoEl.value.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`
  }
}

function fitPhoto() {
  const w = wrap.value
  const img = photoEl.value
  if (!w || !img || !img.naturalWidth || !img.naturalHeight) return
  const cw = w.clientWidth || 1
  const ch = w.clientHeight || 1
  const iw = img.naturalWidth
  const ih = img.naturalHeight
  fitScale = Math.min(cw / iw, ch / ih)
  scale = fitScale
  tx = (cw - iw * scale) / 2
  ty = (ch - ih * scale) / 2
  applyPhoto()
}

function zoomPhotoBy(factor: number) {
  const w = wrap.value
  if (!w) return
  const cx = w.clientWidth / 2
  const cy = w.clientHeight / 2
  const next = Math.max(fitScale, Math.min(fitScale * 6, scale * factor))
  const k = next / scale
  tx = cx - (cx - tx) * k
  ty = cy - (cy - ty) * k
  scale = next
  applyPhoto()
}

function resetPhoto() {
  fitPhoto()
}

function initPhoto() {
  const w = wrap.value
  if (!w) return
  const img = photoEl.value
  if (img) {
    if (img.complete && img.naturalWidth) fitPhoto()
    else img.addEventListener('load', () => fitPhoto(), { once: true })
  }
  const down = (e: PointerEvent) => {
    photoDrag = true
    photoStart = { x: e.clientX, y: e.clientY, tx, ty }
  }
  const move = (e: PointerEvent) => {
    if (!photoDrag) return
    tx = photoStart.tx + (e.clientX - photoStart.x)
    ty = photoStart.ty + (e.clientY - photoStart.y)
    applyPhoto()
  }
  const up = () => {
    photoDrag = false
  }
  const wheel = (e: WheelEvent) => {
    e.preventDefault()
    zoomPhotoBy(e.deltaY < 0 ? 1.15 : 1 / 1.15)
  }
  w.addEventListener('pointerdown', down)
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
  w.addEventListener('wheel', wheel, { passive: false })
  photoCleanup = () => {
    w.removeEventListener('pointerdown', down)
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
    w.removeEventListener('wheel', wheel)
  }
}

async function initPanorama() {
  const w = wrap.value
  const cv = canvasEl.value
  if (!w || !cv) return
  const THREE = await import('three')
  const cw = w.clientWidth || 1
  const ch = w.clientHeight || 1

  renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true })
  renderer.setSize(cw, ch, false)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(72, cw / ch, 0.1, 1000)
  camera.rotation.order = 'YXZ'

  const texture = new THREE.TextureLoader().load(props.src)
  texture.colorSpace = THREE.SRGBColorSpace
  const geo = new THREE.SphereGeometry(100, 60, 40)
  const mat = new THREE.MeshBasicMaterial({ map: texture, side: THREE.BackSide })
  scene.add(new THREE.Mesh(geo, mat))

  const render = () => {
    raf = requestAnimationFrame(render)
    renderer?.render(scene, camera)
  }
  raf = requestAnimationFrame(render)

  let dragging = false
  let sx = 0
  let sy = 0
  let by = 0
  let bp = 0
  const down = (e: PointerEvent) => {
    dragging = true
    sx = e.clientX
    sy = e.clientY
    by = yaw
    bp = pitch
  }
  const move = (e: PointerEvent) => {
    if (!dragging) return
    yaw = by - (e.clientX - sx) * 0.005
    pitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, bp - (e.clientY - sy) * 0.005))
    camera.rotation.y = yaw
    camera.rotation.x = pitch
  }
  const up = () => {
    dragging = false
  }
  const wheel = (e: WheelEvent) => {
    e.preventDefault()
    camera.fov = Math.max(30, Math.min(95, camera.fov + e.deltaY * 0.05))
    camera.updateProjectionMatrix()
  }
  w.addEventListener('pointerdown', down)
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
  w.addEventListener('wheel', wheel, { passive: false })
  panoCleanup = () => {
    cancelAnimationFrame(raf)
    w.removeEventListener('pointerdown', down)
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
    w.removeEventListener('wheel', wheel)
    renderer?.dispose()
    renderer = null
    scene = null
    camera = null
  }
}

function teardown() {
  photoCleanup?.()
  photoCleanup = null
  panoCleanup?.()
  panoCleanup = null
}

async function load() {
  teardown()
  mode.value = 'loading'
  const img = new Image()
  img.onload = async () => {
    const ratio = (img.naturalWidth || 1) / (img.naturalHeight || 1)
    if (ratio >= 1.9 && ratio <= 2.1) {
      mode.value = 'panorama'
      await nextTick()
      initPanorama()
    } else {
      mode.value = 'photo'
      await nextTick()
      initPhoto()
    }
  }
  img.onerror = () => {
    mode.value = 'error'
  }
  img.src = props.src
}

function onResize() {
  if (mode.value === 'photo') {
    fitPhoto()
  } else if (mode.value === 'panorama' && renderer && camera && wrap.value) {
    const cw = wrap.value.clientWidth || 1
    const ch = wrap.value.clientHeight || 1
    renderer.setSize(cw, ch, false)
    camera.aspect = cw / ch
    camera.updateProjectionMatrix()
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  teardown()
  window.removeEventListener('resize', onResize)
})
watch(() => props.src, () => load())
</script>

<template>
  <div ref="wrap" class="pv" :class="`pv--${mode}`">
    <canvas v-if="mode === 'panorama'" ref="canvasEl" class="pv__canvas" />
    <img
      v-else-if="mode === 'photo'"
      ref="photoEl"
      :src="src"
      :alt="alt"
      class="pv__photo"
      draggable="false"
    />

    <div v-if="mode === 'loading'" class="pv__hint">加载中…</div>
    <div v-else-if="mode === 'error'" class="pv__hint">图片加载失败</div>

    <div v-if="mode === 'photo'" class="pv__badge">普通照片 · 拖动查看 / 滚轮缩放</div>
    <div v-else-if="mode === 'panorama'" class="pv__badge">360° 全景 · 拖动环视 / 滚轮缩放</div>

    <div v-if="mode === 'photo'" class="pv__controls">
      <button type="button" @click="zoomPhotoBy(1.25)">＋</button>
      <button type="button" @click="zoomPhotoBy(0.8)">－</button>
      <button type="button" @click="resetPhoto">复位</button>
    </div>
  </div>
</template>

<style scoped>
.pv {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #10151c;
  touch-action: none;
  cursor: grab;
}
.pv:active {
  cursor: grabbing;
}
.pv__canvas {
  display: block;
  width: 100%;
  height: 100%;
}
.pv__photo {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
  max-width: none;
  user-select: none;
}
.pv__hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(255, 255, 255, 0.72);
  font-size: 14px;
}
.pv__badge {
  position: absolute;
  left: 12px;
  bottom: 12px;
  padding: 5px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 12px;
  pointer-events: none;
}
.pv__controls {
  position: absolute;
  right: 12px;
  bottom: 12px;
  display: flex;
  gap: 6px;
}
.pv__controls button {
  min-width: 34px;
  height: 34px;
  padding: 0 8px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  cursor: pointer;
}
.pv__controls button:hover {
  background: rgba(0, 0, 0, 0.75);
}
</style>
