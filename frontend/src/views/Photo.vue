<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

interface Person {
  id: string
  name: string
  era: string
  quote: string
  intro: string
  image2d: string
  image3d: string
  accent: string
}

interface Scene {
  id: string
  name: string
  academy: string
  note: string
  image: string
}

interface Pose {
  id: string
  name: string
  hint: string
  prompt: string
}

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}
function thumbUrl(src: string, w = 1200, h = 900) {
  return '/api/v1/assets/thumb/academy/' + src.split('/').map(encodeURIComponent).join('/') + `?w=${w}&h=${h}`
}

const people: Person[] = [
  { id: 'jiangwanli', name: '江万里', era: '先贤 · 书院人物', quote: '立志宜思真品格，读书须尽苦功夫。', intro: '以笃学与实干影响后世的先贤。', image2d: '/assets/historical/jiangwanli.png', image3d: '/assets/historical-3d/jiangwanli.jpg', accent: '#b44f2f' },
  { id: 'luxiangshan', name: '陆象山', era: '南宋 · 1139—1193', quote: '宇宙便是吾心，吾心即是宇宙。', intro: '以心学思想闻名的理学家、教育家。', image2d: '/assets/historical/luxiangshan.png', image3d: '/assets/historical-3d/luxiangshan.jpg', accent: '#2f716b' },
  { id: 'lvzuqian', name: '吕祖谦', era: '南宋 · 1137—1181', quote: '学者须是务实，不务实则学无所益。', intro: '兼容并蓄、重视经世致用的学者。', image2d: '/assets/historical/lvzuqian.png', image3d: '/assets/historical-3d/lvzuqian.jpg', accent: '#8c6a3e' },
  { id: 'wangyangming', name: '王阳明', era: '明 · 1472—1529', quote: '破山中贼易，破心中贼难。', intro: '知行合一思想的提出者与践行者。', image2d: '/assets/historical/wangyangming.png', image3d: '/assets/historical-3d/wangyangming.jpg', accent: '#6d5b86' },
  { id: 'zhuxi', name: '朱熹', era: '南宋 · 1130—1200', quote: '问渠那得清如许？为有源头活水来。', intro: '理学集大成者，重视读书与实践。', image2d: '/assets/historical/zhuxi.png', image3d: '/assets/historical-3d/zhuxi.jpg', accent: '#356f68' },
  { id: 'luocongyan', name: '罗从彦', era: '两宋之际 · 1072—1135', quote: '潜思力行，任重诣极。', intro: '豫章学派创始人，闽学承上启下的一代儒者。', image2d: '/assets/historical/luocongyan.png', image3d: '/assets/historical-3d/luocongyan.png', accent: '#6b7a3f' },
]

const scenes: Scene[] = [
  { id: 'bailudong', name: '正学之门', academy: '白鹿洞书院', note: '古牌坊 · 入院时刻', image: thumbUrl('组织拍摄了江西遗存书院/江西四大书院/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG') },
  { id: 'bailuzhou', name: '风月楼', academy: '白鹭洲书院', note: '文章节义 · 临江而立', image: thumbUrl('组织拍摄了江西遗存书院/江西四大书院/白鹭洲书院/白鹭洲书院风月楼.JPG') },
  { id: 'ehu', name: '鹅湖全景', academy: '鹅湖书院', note: '朱陆论道 · 全景', image: thumbUrl('组织拍摄了江西遗存书院/江西四大书院/鹅湖书院/鹅湖书院全景图.jpg') },
]

const poses: Pose[] = [
  {
    id: 'stand',
    name: '肃立并肩',
    hint: '并肩近站，面向镜头',
    prompt:
      'Pose: solemn commemorative stance. The sage and the visitor stand close side by side facing the camera, as in a formal two-person group photograph. Keep them near each other; do not leave an exaggerated empty gap between them. The visitor stands upright with arms naturally at the sides or both hands overlapping in front of the body. The sage stands composed and dignified. They do not touch.',
  },
  {
    id: 'salute',
    name: '拱手作揖',
    hint: '游客拱手行礼，先贤端立',
    prompt:
      'Pose: the visitor pays respect with a traditional Chinese cupped-hand salute (拱手作揖). The visitor stands close beside the sage, slightly turned toward him, both hands together in front of the chest, body composed. The sage remains upright and dignified. They do not touch.',
  },
  {
    id: 'study',
    name: '问学执卷',
    hint: '先贤持卷，游客捧书请益',
    prompt:
      'Pose: a student seeking instruction from the sage. They stand close together. The sage holds a scroll; the visitor holds a book with both hands and turns slightly toward the sage. They do not touch, link arms, or lean on each other.',
  },
]

const personId = ref('jiangwanli')
const sceneId = ref('bailudong')
const poseId = ref('stand')
const characterStyle = ref<'2d' | '3d'>('2d')
const costume = ref(false)
const photo = ref('')
const facePhoto = ref('')
const result = ref('')
// 生成成功后弹出全屏预览（点一下关闭）
const previewOpen = ref(false)
const busy = ref(false)
const status = ref('')
const geminiConfigured = ref(false)
const errorModal = ref(false)
const failureCount = ref(0)
const progress = ref(0)
const progressMessage = ref('')
const progressShown = ref(0)
let progressRaf = 0

function stopProgressAnim() {
  if (progressRaf) {
    cancelAnimationFrame(progressRaf)
    progressRaf = 0
  }
}

/**
 * 平滑推进进度条：
 * - 后端里程碑到达时快速追上（不会跳变）
 * - 等待期间缓慢爬升，长时间也不会停在同一个数字上
 * - 上限留有余量，不会提前冲到 100%
 */
function startProgressAnim() {
  stopProgressAnim()
  progressShown.value = 0
  const tick = () => {
    const milestone = progress.value
    const shown = progressShown.value
    if (shown < milestone) {
      progressShown.value = Math.min(milestone, shown + Math.max(0.4, (milestone - shown) * 0.12))
    } else {
      const ceiling = Math.min(97, milestone + 45)
      if (shown < ceiling) {
        progressShown.value = shown + Math.max(0.012, (ceiling - shown) * 0.006)
      }
    }
    progressRaf = requestAnimationFrame(tick)
  }
  progressRaf = requestAnimationFrame(tick)
}

const bodyInput = ref<HTMLInputElement | null>(null)
const faceInput = ref<HTMLInputElement | null>(null)
const video = ref<HTMLVideoElement | null>(null)
const cameraOpen = ref(false)
let stream: MediaStream | null = null

const person = computed(() => people.find((p) => p.id === personId.value) || people[0])
const scene = computed(() => scenes.find((s) => s.id === sceneId.value) || scenes[0])
const pose = computed(() => poses.find((p) => p.id === poseId.value) || poses[0])
const characterImage = computed(() => (characterStyle.value === '3d' ? person.value.image3d : person.value.image2d))

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

async function toDataUrl(src: string): Promise<string> {
  if (src.startsWith('data:')) return src
  const resp = await fetch(src)
  const blob = await resp.blob()
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

async function optimizeDataUrl(src: string, maxDimension: number, quality: number): Promise<string> {
  const dataUrl = src.startsWith('data:') ? src : await toDataUrl(src)
  const image = await loadImage(dataUrl)
  const w = image.naturalWidth || image.width
  const h = image.naturalHeight || image.height
  const scale = Math.min(1, maxDimension / Math.max(w, h))
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(w * scale))
  canvas.height = Math.max(1, Math.round(h * scale))
  canvas.getContext('2d')!.drawImage(image, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', quality)
}

function onPickBody(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (!f.type.startsWith('image/')) {
    status.value = '请选择 JPG、PNG 或 WebP 图片。'
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    photo.value = reader.result as string
    result.value = ''
    status.value = ''
  }
  reader.readAsDataURL(f)
  ;(e.target as HTMLInputElement).value = ''
}

function onPickFace(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (!f.type.startsWith('image/')) {
    status.value = '请选择 JPG、PNG 或 WebP 图片。'
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    facePhoto.value = reader.result as string
    result.value = ''
    status.value = ''
  }
  reader.readAsDataURL(f)
  ;(e.target as HTMLInputElement).value = ''
}

function stopCamera() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  cameraOpen.value = false
}

async function openCamera() {
  status.value = ''
  if (!navigator.mediaDevices?.getUserMedia) {
    status.value = '当前浏览器不支持摄像头，请使用上传照片。'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } },
      audio: false,
    })
    cameraOpen.value = true
    requestAnimationFrame(() => {
      if (video.value) video.value.srcObject = stream
    })
  } catch {
    status.value = '无法打开摄像头，请检查浏览器权限，或改用上传照片。'
  }
}

function capturePhoto() {
  const v = video.value
  if (!v?.videoWidth) return
  const canvas = document.createElement('canvas')
  canvas.width = v.videoWidth
  canvas.height = v.videoHeight
  canvas.getContext('2d')!.drawImage(v, 0, 0, canvas.width, canvas.height)
  photo.value = canvas.toDataURL('image/jpeg', 0.92)
  result.value = ''
  stopCamera()
}

async function generate() {
  if (!photo.value || busy.value) return
  if (!geminiConfigured.value) {
    errorModal.value = true
    return
  }
  busy.value = true
  result.value = ''
  progress.value = 0
  progressMessage.value = '正在准备…'
  startProgressAnim()
  try {
    const [visitorImage, faceImage, backgroundImage, poetImage] = await Promise.all([
      optimizeDataUrl(photo.value, 1400, 0.86),
      facePhoto.value ? optimizeDataUrl(facePhoto.value, 1200, 0.92) : Promise.resolve(null),
      optimizeDataUrl(scene.value.image, 1800, 0.84),
      optimizeDataUrl(characterImage.value, 1400, 0.9),
    ])
    const resp = await fetch('/api/v1/photo/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: 'gemini',
        visitorImage,
        faceImage,
        poetImage,
        backgroundImage,
        person: person.value.name,
        quote: person.value.quote,
        pose: pose.value.prompt,
        costume: costume.value,
      }),
    })
    if (!resp.ok || !resp.body) {
      const text = await resp.text().catch(() => '')
      throw new Error(text || 'API 生成失败')
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let image: string | null = null
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const dataLine = part.split('\n').find((l) => l.startsWith('data:'))
        if (!dataLine) continue
        const text = dataLine.slice(5).trim()
        if (!text) continue
        let ev: any
        try {
          ev = JSON.parse(text)
        } catch {
          continue
        }
        if (ev.error) throw new Error(ev.error)
        if (typeof ev.progress === 'number') progress.value = ev.progress
        if (ev.message) progressMessage.value = ev.message
        if (ev.image) image = ev.image
      }
    }
    if (!image) throw new Error('生成失败：未返回图片')
    progress.value = 100
    progressShown.value = 100
    // 让进度条走满后再出图，视觉上更完整
    await new Promise((resolve) => setTimeout(resolve, 320))
    result.value = await addResultLabel(image, {
      person: person.value.name,
      quote: person.value.quote,
      academy: scene.value.academy,
    })
    failureCount.value = 0
    // 生成成功：弹出全屏预览看效果（点一下即关闭）
    previewOpen.value = true
  } catch (e: any) {
    progress.value = 0
    failureCount.value += 1
    errorModal.value = true
  } finally {
    busy.value = false
    stopProgressAnim()
  }
}

async function addResultLabel(
  src: string,
  meta: { person: string; quote: string; academy: string },
): Promise<string> {
  const image = await loadImage(src.startsWith('data:') ? src : await toDataUrl(src))
  const canvas = document.createElement('canvas')
  canvas.width = image.naturalWidth || image.width
  canvas.height = image.naturalHeight || image.height
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
  const bandHeight = Math.max(170, Math.round(canvas.height * 0.16))
  const gradient = ctx.createLinearGradient(0, canvas.height - bandHeight, 0, canvas.height)
  gradient.addColorStop(0, 'rgba(28, 24, 19, 0.05)')
  gradient.addColorStop(0.28, 'rgba(28, 24, 19, 0.72)')
  gradient.addColorStop(1, 'rgba(28, 24, 19, 0.92)')
  ctx.fillStyle = gradient
  ctx.fillRect(0, canvas.height - bandHeight, canvas.width, bandHeight)
  const pad = Math.round(canvas.width * 0.055)
  const titleSize = Math.max(26, Math.round(canvas.width * 0.033))
  const quoteSize = Math.max(20, Math.round(canvas.width * 0.023))
  const footerSize = Math.max(16, Math.round(canvas.width * 0.017))
  ctx.fillStyle = '#fff8ea'
  ctx.font = `600 ${titleSize}px "Noto Serif SC", serif`
  ctx.fillText(`诗人：${meta.person}`, pad, canvas.height - bandHeight + Math.round(bandHeight * 0.36))
  ctx.fillStyle = 'rgba(255, 248, 234, 0.92)'
  ctx.font = `400 ${quoteSize}px "Noto Serif SC", serif`
  const quoteText = `代表诗句：「${meta.quote}」`
  const quoteLine = quoteText.length > 34 ? `${quoteText.slice(0, 34)}…` : quoteText
  ctx.fillText(quoteLine, pad, canvas.height - bandHeight + Math.round(bandHeight * 0.64))
  ctx.fillStyle = 'rgba(255, 224, 176, 0.84)'
  ctx.font = `500 ${footerSize}px system-ui, sans-serif`
  ctx.fillText(`${meta.academy}数字体验`, pad, canvas.height - Math.round(bandHeight * 0.14))
  return canvas.toDataURL('image/jpeg', 0.95)
}

function download() {
  if (!result.value) return
  const a = document.createElement('a')
  a.href = result.value
  a.download = `与${person.value.name}同游.jpg`
  a.click()
}

onMounted(async () => {
  try {
    const resp = await fetch('/api/v1/photo/config')
    const cfg = await resp.json()
    geminiConfigured.value = Boolean(cfg.providers?.gemini?.configured)
  } catch {
    geminiConfigured.value = false
  }
})

function onPreviewKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && previewOpen.value) previewOpen.value = false
}
onMounted(() => window.addEventListener('keydown', onPreviewKey))

onBeforeUnmount(() => {
  stopCamera()
  window.removeEventListener('keydown', onPreviewKey)
})
</script>

<template>
  <div class="ph">
    <header class="ph__top">
      <div class="shell ph__topIn">
        <div>
          <p class="eyebrow">与先贤同游</p>
          <h1 class="h-serif">书院数字合影体验</h1>
        </div>
        <span class="ph__note">照片仅用于本次生成 · 不保存原始照片</span>
      </div>
    </header>

    <div class="shell ph__grid">
      <section class="ph__panel">
        <div class="ph__head">
          <span class="ph__step">01</span>
          <h2>准备游客照片</h2>
          <span class="ph__quiet">{{ photo ? '已准备' : '等待照片' }}</span>
        </div>

        <div class="ph__photoStage" :class="{ 'has': photo }">
          <template v-if="!photo">
            <div class="ph__empty">
              <strong>站在光线自然的位置</strong>
              <span>建议全身正面、单人入镜，面部清晰</span>
              <div class="ph__actions">
                <button class="ph__btn ph__btn--main" @click="openCamera">打开摄像头</button>
                <button class="ph__btn" @click="bodyInput?.click()">上传照片</button>
              </div>
            </div>
          </template>
          <template v-else>
            <img :src="photo" alt="游客照片" />
            <span class="ph__badge">已上传照片</span>
            <button class="ph__remove" @click="photo = ''; result = ''">×</button>
          </template>
          <input ref="bodyInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onPickBody" />
        </div>

        <div v-if="cameraOpen" class="ph__camera">
          <strong>调整取景</strong>
          <video ref="video" autoplay playsinline muted />
          <button class="ph__btn ph__btn--main" @click="capturePhoto">拍下这一刻</button>
          <button class="ph__btn" @click="stopCamera">关闭</button>
        </div>

        <div class="ph__face">
          <div class="ph__faceHead">
            <strong>补充一张面部近照</strong>
            <span class="ph__quiet">可选 · 增强五官还原</span>
          </div>
          <template v-if="facePhoto">
            <div class="ph__facePrev"><img :src="facePhoto" alt="面部近照" /><button class="ph__remove" @click="facePhoto = ''; result = ''">×</button></div>
          </template>
          <button v-else class="ph__faceBtn" @click="faceInput?.click()">上传清晰面部照片</button>
          <input ref="faceInput" type="file" accept="image/*" hidden @change="onPickFace" />
        </div>
      </section>

      <section class="ph__panel">
        <div class="ph__head">
          <span class="ph__step">02</span>
          <h2>选择你的同行者</h2>
          <span class="ph__quiet">{{ person.era }}</span>
        </div>

        <div class="ph__style">
          <span>人物形象</span>
          <button :class="{ 'is-on': characterStyle === '2d' }" @click="characterStyle = '2d'; result = ''">二维立绘</button>
          <button :class="{ 'is-on': characterStyle === '3d' }" @click="characterStyle = '3d'; result = ''">写实 3D</button>
        </div>

        <div class="ph__people">
          <button
            v-for="p in people"
            :key="p.id"
            class="ph__person"
            :class="{ 'is-on': p.id === personId }"
            @click="personId = p.id; result = ''"
          >
            <img :src="characterStyle === '3d' ? p.image3d : p.image2d" :alt="p.name" />
            <div>
              <strong>{{ p.name }}</strong>
              <span>{{ p.intro }}</span>
              <small>{{ p.quote }}</small>
            </div>
          </button>
        </div>

        <div class="ph__sub">
          <span>选择书院场景</span>
          <span class="ph__quiet">江西书院实拍背景</span>
        </div>
        <div class="ph__scenes">
          <button
            v-for="s in scenes"
            :key="s.id"
            class="ph__scene"
            :class="{ 'is-on': s.id === sceneId }"
            @click="sceneId = s.id; result = ''"
          >
            <img :src="s.image" :alt="s.name" />
            <span><strong>{{ s.name }}</strong><small>{{ s.note }}</small></span>
          </button>
        </div>

        <div class="ph__sub">
          <span>选择互动姿势</span>
          <span class="ph__quiet">遵循书院之礼</span>
        </div>
        <div class="ph__poses">
          <button
            v-for="p in poses"
            :key="p.id"
            :class="{ 'is-on': p.id === poseId }"
            :title="p.hint"
            @click="poseId = p.id; result = ''"
          >{{ p.name }}</button>
        </div>
        <p class="ph__etiquette" title="合影遵循书院之礼：肃立、作揖、问学，不用搭肩、挽手等亲昵动作。">书院之礼：肃立、作揖、问学，不搭肩挽手。</p>

        <div class="ph__sub">
          <span>游客服装</span>
          <span class="ph__quiet">只改游客，先贤衣冠不变</span>
        </div>
        <div class="ph__poses">
          <button :class="{ 'is-on': !costume }" @click="costume = false; result = ''">保持原样</button>
          <button :class="{ 'is-on': costume }" @click="costume = true; result = ''">古装合影</button>
        </div>

        <button class="ph__gen" :disabled="!photo || busy" @click="generate">
          {{ busy ? '正在生成…' : '生成我的合影' }}
        </button>
        <p v-if="!photo" class="ph__req">请先上传或拍摄一张全身照，才能开始生图。</p>
        <p v-if="status" class="ph__status">{{ status }}</p>
      </section>

      <section class="ph__panel ph__resultPanel">
        <div class="ph__head">
          <span class="ph__step">03</span>
          <h2>领取你的书院合影</h2>
          <span class="ph__quiet">{{ result ? '可以下载' : '生成后显示' }}</span>
        </div>
        <div class="ph__result" :class="{ 'has': result }">
          <img v-if="result" :src="result" alt="生成完成的书院合影" />
          <div v-else-if="busy" class="ph__progress">
            <p class="ph__progressLabel">{{ progressMessage || '照片生成中…' }}</p>
            <div class="ph__bar">
              <div class="ph__barFill" :style="{ width: progressShown + '%' }">
                <span class="ph__barEdge" aria-hidden="true" />
              </div>
            </div>
            <strong class="ph__pct">{{ Math.floor(progressShown) }}<i>%</i></strong>
            <p class="ph__progressHint">生成通常需要 15–30 秒，请不要关闭页面</p>
          </div>
          <div v-else class="ph__resultEmpty">你的合影会在这里出现</div>
        </div>
        <div v-if="result" class="ph__resultActions">
          <button class="ph__btn ph__btn--main" @click="download">下载合影</button>
          <button class="ph__btn" @click="result = ''; status = ''">重新生成</button>
        </div>
      </section>
    </div>

    <div v-if="errorModal" class="ph__modal">
      <div class="ph__modalBox">
        <h2>暂时无法生成</h2>
        <p>{{ failureCount >= 3 ? '生图连续异常，请联系工作人员。' : '生图网络异常，请重试。' }}</p>
        <div class="ph__modalActions">
          <button class="ph__btn" @click="errorModal = false">知道了</button>
          <button v-if="failureCount < 3" class="ph__btn ph__btn--main" @click="errorModal = false; generate()">重试</button>
        </div>
      </div>
    </div>

    <!-- 生成成功后的全屏预览：点击任意位置（或按 Esc）关闭 -->
    <div
      v-if="previewOpen && result"
      class="ph__preview"
      role="dialog"
      aria-label="合影预览"
      title="点击关闭"
      @click="previewOpen = false"
    >
      <img :src="result" alt="生成完成的书院合影" />
      <p class="ph__previewHint">点击任意位置关闭</p>
    </div>
  </div>
</template>

<style scoped>
.ph { min-height: 100vh; background: var(--bg); padding-bottom: 64px; }
.ph__top { background: radial-gradient(circle at 85% 10%, rgba(237,183,79,.14), transparent 45%), var(--navy-deep); color: #fff; }
.ph__topIn { display: flex; align-items: flex-end; justify-content: space-between; padding: 36px 0 28px; }
.ph__top h1 { margin: 8px 0 0; font-size: clamp(26px, 3.4vw, 40px); font-weight: 800; }
.ph__note { color: rgba(255,255,255,.72); font-size: 13px; }
.eyebrow { color: var(--gold); font-size: 13px; font-weight: 700; letter-spacing: .08em; }

.ph__grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; padding-top: 28px; }
.ph__panel { padding: 20px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.ph__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 16px; }
.ph__head h2 { font-size: 18px; font-weight: 800; color: var(--ink); }
.ph__step { color: var(--gold-deep); font-weight: 800; }
.ph__quiet { margin-left: auto; color: var(--muted); font-size: 12px; }

.ph__photoStage { display: grid; place-items: center; min-height: 220px; border-radius: 12px; border: 1px dashed var(--line); background: rgba(44,62,80,.05); overflow: hidden; }
.ph__photoStage.has { position: relative; display: block; }
.ph__photoStage img { width: 100%; max-height: 320px; object-fit: contain; display: block; }
.ph__empty { text-align: center; color: var(--sub); padding: 20px; }
.ph__empty strong { display: block; font-size: 16px; color: var(--ink); }
.ph__empty span { display: block; margin: 6px 0 14px; font-size: 13px; color: var(--muted); }
.ph__badge { position: absolute; left: 10px; bottom: 10px; padding: 4px 10px; border-radius: 8px; background: rgba(0,0,0,.55); color: #fff; font-size: 12px; }
.ph__remove { position: absolute; right: 8px; top: 8px; width: 26px; height: 26px; border-radius: 50%; background: rgba(0,0,0,.55); color: #fff; cursor: pointer; }

.ph__actions { display: flex; gap: 10px; justify-content: center; margin-top: 12px; }
.ph__btn { padding: 10px 16px; border-radius: 10px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); font-size: 14px; cursor: pointer; }
.ph__btn:disabled { opacity: .5; cursor: not-allowed; }
.ph__btn--main { background: var(--navy); border-color: var(--navy); color: #fff; }

.ph__camera { margin-top: 12px; padding: 12px; border-radius: 12px; background: var(--bg); border: 1px solid var(--line); }
.ph__camera video { width: 100%; border-radius: 10px; background: #000; }

.ph__face { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line); }
.ph__faceHead { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; }
.ph__facePrev { position: relative; }
.ph__facePrev img { width: 100%; max-height: 140px; object-fit: contain; border-radius: 10px; }
.ph__faceBtn { width: 100%; padding: 12px; border-radius: 10px; border: 1px dashed var(--line); background: var(--bg); color: var(--sub); cursor: pointer; }

.ph__style { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; }
.ph__style span { font-size: 14px; font-weight: 700; color: var(--sub); margin-right: 4px; }
.ph__style button { padding: 7px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg); color: var(--sub); font-size: 13px; cursor: pointer; }
.ph__style button.is-on { background: var(--navy); color: #fff; border-color: var(--navy); }

.ph__people { display: flex; flex-direction: column; gap: 8px; }
.ph__person { display: flex; gap: 12px; align-items: center; padding: 8px; border-radius: 12px; border: 1px solid var(--line); background: var(--bg); text-align: left; cursor: pointer; }
.ph__person.is-on { border-color: var(--gold); box-shadow: 0 0 0 2px var(--gold); }
.ph__person img {
  width: 56px;
  height: 56px;
  border-radius: 10px;
  /* 竖版的写实 3D 图若用 cover 会连头一起裁掉，改成完整缩放显示 */
  object-fit: contain;
  background: var(--bg);
}
.ph__person div { min-width: 0; }
.ph__person strong { display: block; color: var(--ink); }
.ph__person span { display: block; font-size: 12px; color: var(--sub); }
.ph__person small { display: block; font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.ph__sub { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin: 18px 0 8px; font-size: 14px; font-weight: 700; color: var(--sub); }
.ph__scenes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.ph__scene { position: relative; border-radius: 10px; overflow: hidden; border: 2px solid transparent; cursor: pointer; }
.ph__scene.is-on { border-color: var(--gold); }
.ph__scene img { width: 100%; height: 74px; object-fit: cover; display: block; }
.ph__scene span { position: absolute; inset: auto 0 0 0; padding: 12px 8px 6px; background: linear-gradient(transparent, rgba(0,0,0,.7)); color: #fff; }
.ph__scene strong { display: block; font-size: 13px; }
.ph__scene small { display: block; font-size: 10px; opacity: .8; }

.ph__poses { display: flex; flex-wrap: wrap; gap: 8px; }
.ph__poses button { padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--bg); color: var(--sub); cursor: pointer; }
.ph__poses button.is-on { background: var(--navy); color: #fff; border-color: var(--navy); }
.ph__etiquette {
  margin-top: 8px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}

.ph__gen { width: 100%; margin-top: 20px; padding: 13px; border-radius: 12px; background: linear-gradient(135deg, var(--navy), var(--navy-deep)); color: #fff; font-size: 16px; font-weight: 700; cursor: pointer; }
.ph__gen:disabled { opacity: .5; cursor: not-allowed; }
.ph__req { margin-top: 10px; text-align: center; color: var(--muted); font-size: 12.5px; }
.ph__status { margin-top: 10px; text-align: center; color: var(--gold-deep); font-size: 13px; }

.ph__resultPanel { display: flex; flex-direction: column; }
.ph__result { flex: 1; display: grid; place-items: center; min-height: 320px; border-radius: 12px; border: 1px dashed var(--line); background: rgba(44,62,80,.05); overflow: hidden; }
.ph__result img { max-width: 100%; max-height: 560px; object-fit: contain; }
.ph__resultEmpty { color: var(--muted); font-size: 14px; }
.ph__progress { display: flex; flex-direction: column; align-items: center; gap: 12px; width: 100%; padding: 28px 16px; }
/* 固定两行高度，文案长短变化时进度条不会上下跳动 */
.ph__progressLabel {
  display: flex;
  align-items: center;
  min-height: 2.6em;
  text-align: center;
  color: var(--sub);
  font-size: 14px;
}
.ph__bar {
  position: relative;
  width: min(340px, 100%);
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(44, 62, 80, 0.12), rgba(44, 62, 80, 0.07));
  box-shadow: inset 0 1px 2px rgba(20, 30, 40, 0.14);
  overflow: hidden;
}
.ph__barFill {
  position: relative;
  height: 100%;
  min-width: 6px;
  border-radius: 999px;
  background-image:
    repeating-linear-gradient(
      115deg,
      rgba(255, 255, 255, 0.26) 0 6px,
      rgba(255, 255, 255, 0) 6px 14px
    ),
    linear-gradient(90deg, #c69a4b, #edb74f 52%, #f6d998);
  background-size: 20px 100%, 100% 100%;
  background-position: 0 0, 0 0;
  animation: ph-stripes 1.1s linear infinite, ph-glow 2.4s ease-in-out infinite;
}
/* 前沿高光，让进度条像在"实时推进" */
.ph__barEdge {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 26px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.9));
  filter: blur(0.5px);
}
@keyframes ph-stripes {
  to {
    background-position: 20px 0, 0 0;
  }
}
@keyframes ph-glow {
  0%,
  100% {
    box-shadow: 0 0 8px rgba(237, 183, 79, 0.34);
  }
  50% {
    box-shadow: 0 0 16px rgba(237, 183, 79, 0.68);
  }
}
.ph__pct {
  font-size: 34px;
  font-weight: 800;
  color: var(--gold-deep);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  line-height: 1;
}
.ph__pct i {
  font-size: 16px;
  font-style: normal;
  font-weight: 700;
  margin-left: 2px;
  opacity: 0.72;
}
.ph__progressHint { color: var(--muted); font-size: 12px; }
.ph__resultActions { display: flex; gap: 10px; margin-top: 12px; }
.ph__resultActions .ph__btn { flex: 1; }

.ph__modal { position: fixed; inset: 0; display: grid; place-items: center; background: rgba(0,0,0,.4); z-index: 100; }
.ph__modalBox { width: min(420px, 86vw); padding: 24px; border-radius: 16px; background: #fff; text-align: center; }
.ph__modalBox h2 { font-size: 20px; color: var(--ink); }
.ph__modalBox p { margin: 10px 0 18px; color: var(--sub); }
.ph__modalActions { display: flex; gap: 10px; justify-content: center; }

/* 生成成功后的全屏预览：铺满屏幕展示合影，点一下即关闭 */
.ph__preview {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 3vh 3vw;
  background: rgba(6, 10, 14, 0.92);
  backdrop-filter: blur(4px);
  cursor: zoom-out;
  animation: phPreviewIn 0.18s ease;
}
.ph__preview img {
  max-width: 94vw;
  max-height: 82vh;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55);
}
.ph__previewHint {
  margin: 0;
  color: rgba(255, 255, 255, 0.74);
  font-size: 13px;
  letter-spacing: 0.04em;
}
@keyframes phPreviewIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@media (max-width: 980px) {
  .ph__grid { grid-template-columns: 1fr; }
}
</style>
