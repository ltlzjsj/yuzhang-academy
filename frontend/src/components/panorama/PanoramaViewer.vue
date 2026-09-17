<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ src: string; alt?: string }>()

const wrap = ref<HTMLDivElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const photoEl = ref<HTMLImageElement | null>(null)
const mode = ref<'loading' | 'panorama' | 'photo' | 'error'>('loading')

// 全屏（点击画面即切换）：优先浏览器原生全屏，不支持时用 CSS 覆盖层兜底，
// 两种模式共用 .pv--full 控制尺寸。
const isFullscreen = ref(false)
const fullMode = ref(false)
let nativeFsActive = false
let pressInfo = { x: 0, y: 0, t: 0, moved: false, inside: false }

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

// ---- 全屏 ----
function syncFullscreenSize() {
  isFullscreen.value = fullMode.value
  // 容器尺寸变化：等布局稳定后重算（照片模式重新适配、全景模式更新相机比例）
  nextTick(() => onResize())
  requestAnimationFrame(() => onResize())
  window.setTimeout(() => onResize(), 260)
}

function onFullscreenChange() {
  if (document.fullscreenElement) {
    nativeFsActive = true
    fullMode.value = true
  } else if (nativeFsActive) {
    // 只有「本来在原生全屏、现在退出」才关闭；请求被浏览器拒绝时保留兜底状态
    nativeFsActive = false
    fullMode.value = false
  }
  syncFullscreenSize()
}

async function toggleFullscreen() {
  const root = wrap.value
  if (!root) return
  if (fullMode.value && !document.fullscreenElement) {
    fullMode.value = false
    syncFullscreenSize()
    return
  }
  if (document.fullscreenElement) {
    await document.exitFullscreen().catch(() => {})
    return
  }
  fullMode.value = true
  syncFullscreenSize()
  const req: ((o?: any) => Promise<void>) | undefined =
    root.requestFullscreen?.bind(root) || (root as any).webkitRequestFullscreen?.bind(root)
  if (req) {
    try {
      await req({ navigationUI: 'hide' })
      nativeFsActive = true
      return
    } catch {
      nativeFsActive = false
    }
  }
}

function onFsKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && fullMode.value && !document.fullscreenElement) {
    fullMode.value = false
    syncFullscreenSize()
  }
}

// 点击画面切换全屏：按下到抬起之间几乎没移动才算「点击」，避免与拖动环视冲突
function trackDown(e: PointerEvent) {
  pressInfo = { x: e.clientX, y: e.clientY, t: performance.now(), moved: false, inside: true }
}
function trackMove(e: PointerEvent) {
  if (pressInfo.moved) return
  if (Math.abs(e.clientX - pressInfo.x) > 6 || Math.abs(e.clientY - pressInfo.y) > 6) pressInfo.moved = true
}
function trackUp(e: PointerEvent) {
  if (!pressInfo.inside) return
  pressInfo.inside = false
  const el = e.target as HTMLElement | null
  if (el?.closest('.pv__fs') || el?.closest('.pv__controls')) return
  if (pressInfo.moved || performance.now() - pressInfo.t > 500) return
  void toggleFullscreen()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange as EventListener)
  window.addEventListener('keydown', onFsKeydown)
  wrap.value?.addEventListener('pointerdown', trackDown)
  window.addEventListener('pointermove', trackMove)
  window.addEventListener('pointerup', trackUp)
})
onBeforeUnmount(() => {
  teardown()
  window.removeEventListener('resize', onResize)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange as EventListener)
  window.removeEventListener('keydown', onFsKeydown)
  wrap.value?.removeEventListener('pointerdown', trackDown)
  window.removeEventListener('pointermove', trackMove)
  window.removeEventListener('pointerup', trackUp)
})
watch(() => props.src, () => load())
</script>

<template>
  <div ref="wrap" class="pv" :class="[`pv--${mode}`, { 'pv--full': fullMode }]">
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

    <div v-if="mode === 'photo'" class="pv__badge">
      {{ isFullscreen ? '普通照片 · 再次点击画面 / 按 Esc 退出全屏' : '普通照片 · 点击画面全屏 · 拖动查看 / 滚轮缩放' }}
    </div>
    <div v-else-if="mode === 'panorama'" class="pv__badge">
      {{ isFullscreen ? '360° 全景 · 再次点击画面 / 按 Esc 退出全屏' : '360° 全景 · 点击画面全屏 · 拖动环视 / 滚轮缩放' }}
    </div>

    <button
      type="button"
      class="pv__fs"
      :title="isFullscreen ? '退出全屏（Esc）' : '全屏查看实景（也可以直接点击画面）'"
      :aria-label="isFullscreen ? '退出全屏' : '全屏查看'"
      @click.stop="toggleFullscreen"
      @pointerdown.stop
    >
      <span class="pv__fsIcon">{{ isFullscreen ? '✕' : '⛶' }}</span>
      <span>{{ isFullscreen ? '退出全屏' : '全屏' }}</span>
    </button>

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

/* 右上角全屏按钮 */
.pv__fs {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 5;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  backdrop-filter: blur(4px);
  transition: background 0.15s ease;
}
.pv__fs:hover {
  background: rgba(0, 0, 0, 0.78);
}
.pv__fsIcon {
  font-size: 13px;
}

/* 全屏展示：铺满整屏（原生全屏与 CSS 兜底共用） */
.pv--full {
  position: fixed;
  inset: 0;
  z-index: 3000;
  width: 100vw;
  height: 100vh;
  border-radius: 0;
}
.pv--full .pv__fs {
  top: 18px;
  right: 20px;
  padding: 8px 14px;
  font-size: 13px;
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
