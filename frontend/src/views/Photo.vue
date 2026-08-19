<script setup lang="ts">
import { reactive, ref } from 'vue'

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}
function thumbUrl(src: string, w = 640, h = 480) {
  return '/api/v1/assets/thumb/academy/' + src.split('/').map(encodeURIComponent).join('/') + `?w=${w}&h=${h}`
}

interface Item {
  id: string
  name: string
  src: string
}

const figures: Item[] = [
  { id: 'zhuxi', name: '朱熹', src: assetUrl('历史名人立绘/zhuxi.png') },
  { id: 'wangyangming', name: '王阳明', src: assetUrl('历史名人立绘/wangyangming.png') },
  { id: 'luxiangshan', name: '陆九渊', src: assetUrl('历史名人立绘/luxiangshan.png') },
  { id: 'jiangwanli', name: '江万里', src: assetUrl('历史名人立绘/jiangwanli.png') },
  { id: 'lvzuqian', name: '吕祖谦', src: assetUrl('历史名人立绘/lvzuqian.png') },
]

const backgrounds: Item[] = [
  { id: 'bailudong', name: '白鹿洞', src: thumbUrl('组织拍摄了江西遗存书院/江西四大书院/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG') },
  { id: 'bailuzhou', name: '白鹭洲', src: thumbUrl('组织拍摄了江西遗存书院/江西四大书院/白鹭洲书院/白鹭洲书院风月楼.JPG') },
  { id: 'ehu', name: '鹅湖', src: thumbUrl('组织拍摄了江西遗存书院/江西四大书院/鹅湖书院/鹅湖书院全景图.jpg') },
]

const W = 1200
const H = 900

const figureId = ref('zhuxi')
const bgId = ref('bailudong')
const userFile = ref<File | null>(null)
const userPreview = ref('')
const error = ref('')
const busy = ref(false)
const done = ref(false)
const canvas = ref<HTMLCanvasElement | null>(null)

let bgImg: HTMLImageElement | null = null
let figImg: HTMLImageElement | null = null
let userImg: HTMLImageElement | null = null

const figRect = reactive({ x: 0, y: 0, w: 0, h: 0 })
const userRect = reactive({ x: 0, y: 0, w: 0, h: 0 })
let dragTarget: 'fig' | 'user' | null = null
let dragStart = { px: 0, py: 0, ox: 0, oy: 0 }

function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  if (!f.type.startsWith('image/')) {
    error.value = '请选择图片文件'
    return
  }
  userFile.value = f
  if (userPreview.value) URL.revokeObjectURL(userPreview.value)
  userPreview.value = URL.createObjectURL(f)
  error.value = ''
  done.value = false
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('图片加载失败'))
    img.src = src
  })
}

async function removeBg(file: File): Promise<Blob> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch('/api/v1/photo/bg-remove', { method: 'POST', body: form })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(t || '抠图失败')
  }
  return await resp.blob()
}

function draw() {
  const cv = canvas.value
  if (!cv || !bgImg || !figImg || !userImg) return
  cv.width = W
  cv.height = H
  const ctx = cv.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, W, H)

  const s = Math.max(W / bgImg.width, H / bgImg.height)
  const bw = bgImg.width * s
  const bh = bgImg.height * s
  ctx.drawImage(bgImg, (W - bw) / 2, (H - bh) / 2, bw, bh)

  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, 'rgba(0,0,0,0.16)')
  g.addColorStop(0.5, 'rgba(0,0,0,0)')
  g.addColorStop(1, 'rgba(0,0,0,0.28)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, W, H)

  ctx.drawImage(figImg, figRect.x, figRect.y, figRect.w, figRect.h)
  ctx.drawImage(userImg, userRect.x, userRect.y, userRect.w, userRect.h)

  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.font = '600 30px "Noto Serif SC", serif'
  ctx.textAlign = 'center'
  ctx.fillText('豫章书院 · 与先贤合影', W / 2, 54)
}

function layout() {
  if (!figImg || !userImg) return
  const figH = Math.round(H * 0.74)
  const userH = Math.round(H * 0.72)
  const margin = 90
  const bottom = 24
  const figW = Math.round((figImg.width * figH) / figImg.height)
  const userW = Math.round((userImg.width * userH) / userImg.height)
  figRect.w = figW
  figRect.h = figH
  userRect.w = userW
  userRect.h = userH
  figRect.x = margin
  userRect.x = W - margin - userW
  figRect.y = H - bottom - figH
  userRect.y = H - bottom - userH
}

async function generate() {
  if (!userFile.value) {
    error.value = '请先上传一张照片'
    return
  }
  error.value = ''
  busy.value = true
  done.value = false
  try {
    const fig = figures.find((x) => x.id === figureId.value)!
    const bg = backgrounds.find((x) => x.id === bgId.value)!
    const cutoutBlob = await removeBg(userFile.value)
    const [f, b, u] = await Promise.all([
      loadImage(fig.src),
      loadImage(bg.src),
      loadImage(URL.createObjectURL(cutoutBlob)),
    ])
    figImg = f
    bgImg = b
    userImg = u
    layout()
    draw()
    done.value = true
  } catch (e: any) {
    error.value = e?.message || '生成失败'
  } finally {
    busy.value = false
  }
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v))
}

function canvasPoint(e: PointerEvent) {
  const cv = canvas.value!
  const r = cv.getBoundingClientRect()
  return {
    x: (e.clientX - r.left) * (W / r.width),
    y: (e.clientY - r.top) * (H / r.height),
  }
}

function hit(rect: { x: number; y: number; w: number; h: number }, p: { x: number; y: number }) {
  return p.x >= rect.x && p.x <= rect.x + rect.w && p.y >= rect.y && p.y <= rect.y + rect.h
}

function onDown(e: PointerEvent) {
  if (!done.value || !canvas.value) return
  const p = canvasPoint(e)
  if (hit(userRect, p)) dragTarget = 'user'
  else if (hit(figRect, p)) dragTarget = 'fig'
  else return
  const rect = dragTarget === 'fig' ? figRect : userRect
  dragStart = { px: p.x, py: p.y, ox: rect.x, oy: rect.y }
  canvas.value.setPointerCapture(e.pointerId)
}

function onMove(e: PointerEvent) {
  if (!dragTarget) return
  const p = canvasPoint(e)
  const rect = dragTarget === 'fig' ? figRect : userRect
  rect.x = clamp(dragStart.ox + (p.x - dragStart.px), 0, W - rect.w)
  rect.y = clamp(dragStart.oy + (p.y - dragStart.py), 0, H - rect.h)
  draw()
}

function onUp() {
  dragTarget = null
}

function download() {
  const cv = canvas.value
  if (!cv || !done.value) return
  cv.toBlob((blob) => {
    if (!blob) return
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = '与先贤合影.png'
    a.click()
    URL.revokeObjectURL(a.href)
  }, 'image/png')
}

</script>

<template>
  <div class="ph">
    <section class="shell ph__head">
      <p class="eyebrow">合影留念</p>
      <h1 class="h-serif">与历史先贤合影</h1>
      <p class="ph__lead">上传一张你的照片，自动抠图后与历史人物立绘合成一张纪念照。</p>
    </section>

    <section class="shell ph__grid">
      <aside class="ph__panel">
        <label class="ph__up">
          <input type="file" accept="image/*" @change="onPick" />
          <img v-if="userPreview" :src="userPreview" class="ph__upImg" alt="上传预览" />
          <span v-else class="ph__upTip">＋ 上传你的照片</span>
        </label>

        <div class="ph__field">
          <span class="ph__lbl">历史人物</span>
          <div class="ph__chips">
            <button
              v-for="f in figures"
              :key="f.id"
              type="button"
              :class="{ 'is-on': figureId === f.id }"
              @click="figureId = f.id"
            >{{ f.name }}</button>
          </div>
        </div>

        <div class="ph__field">
          <span class="ph__lbl">背景模板</span>
          <div class="ph__chips">
            <button
              v-for="b in backgrounds"
              :key="b.id"
              type="button"
              :class="{ 'is-on': bgId === b.id }"
              @click="bgId = b.id"
            >{{ b.name }}</button>
          </div>
        </div>

        <p v-if="error" class="ph__err">{{ error }}</p>

        <div class="ph__actions">
          <button type="button" class="ph__btn ph__btn--main" :disabled="busy" @click="generate">
            {{ busy ? '生成中…' : '生成合照' }}
          </button>
          <button type="button" class="ph__btn" :disabled="!done" @click="download">导出下载</button>
        </div>
      </aside>

      <div class="ph__stage">
        <div v-if="!done" class="ph__placeholder">生成后的合照会显示在这里</div>
        <canvas
          ref="canvas"
          class="ph__canvas"
          :class="{ 'is-hide': !done }"
          @pointerdown="onDown"
          @pointermove="onMove"
          @pointerup="onUp"
          @pointercancel="onUp"
        />
        <p v-if="done" class="ph__tip">拖动画面中的人物可调整位置，再点“导出下载”保存。</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ph {
  min-height: 100vh;
  background: var(--bg);
}
.ph__head {
  padding: 52px 0 16px;
  text-align: center;
}
.eyebrow {
  color: var(--gold-deep);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.ph__head h1 {
  margin: 8px 0 0;
  font-size: clamp(26px, 3.4vw, 40px);
  color: var(--ink);
}
.ph__lead {
  margin: 14px auto 0;
  max-width: 640px;
  color: var(--sub);
  font-size: 14.5px;
  line-height: 1.8;
}
.ph__grid {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
  padding-bottom: 64px;
}
.ph__panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 20px;
  border-radius: 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
  align-self: start;
}
.ph__up {
  position: relative;
  display: grid;
  place-items: center;
  aspect-ratio: 4 / 3;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(44, 62, 80, 0.06);
  border: 1px dashed var(--line);
  cursor: pointer;
}
.ph__up input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.ph__upImg {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.ph__upTip {
  color: var(--muted);
  font-size: 14px;
}
.ph__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ph__lbl {
  font-size: 13px;
  font-weight: 700;
  color: var(--sub);
}
.ph__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ph__chips button {
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--sub);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.ph__chips button.is-on {
  background: var(--navy);
  border-color: var(--navy);
  color: #fff;
}
.ph__err {
  color: var(--red);
  font-size: 13px;
}
.ph__actions {
  display: flex;
  gap: 10px;
  margin-top: 2px;
}
.ph__btn {
  flex: 1;
  padding: 11px 14px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--ink);
  font-size: 14px;
  cursor: pointer;
}
.ph__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ph__btn--main {
  background: var(--navy);
  border-color: var(--navy);
  color: #fff;
}
.ph__stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 480px;
  padding: 16px;
  border-radius: 16px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
}
.ph__placeholder {
  color: var(--muted);
  font-size: 14px;
}
.ph__canvas {
  display: block;
  max-width: 100%;
  height: auto;
  border-radius: 12px;
  touch-action: none;
  cursor: move;
}
.ph__canvas.is-hide {
  display: none;
}
.ph__tip {
  color: var(--muted);
  font-size: 12.5px;
}
@media (max-width: 820px) {
  .ph__grid {
    grid-template-columns: 1fr;
  }
}
</style>
