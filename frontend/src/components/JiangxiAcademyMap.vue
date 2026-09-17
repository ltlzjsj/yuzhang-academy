<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useRouter } from 'vue-router'
import { ACADEMIES } from '@/data/academies'

interface Academy {
  name: string
  desc: string
}

// 江西 11 个地级市代表性书院及简介。地图悬停时按城市名匹配。
const CITY_ACADEMIES: Record<string, Academy[]> = {
  南昌市: [
    { name: '豫章书院', desc: '省会南昌的江西四大书院之一，南宋始创、明清渐入官学体系，是江西书院文化的地标。' },
    { name: '东湖书院', desc: '南昌城内的历史名院，与豫章书院并称，历代讲学不辍。' },
    { name: '友教书院', desc: '南昌的讲学之所，书院名录中的江右名院。' },
  ],
  景德镇市: [
    { name: '长芗书院', desc: '位于浮梁（今景德镇），南宋庆元二年（1197）镇监李齐愈仿白鹿洞规制创建，有八百余年历史。' },
  ],
  萍乡市: [
    { name: '鳌洲书院', desc: '萍乡最著名的古代书院，明万历二十至二十三年（1592—1595）知县陆世勣始建，传承吴楚文化。' },
  ],
  九江市: [
    { name: '白鹿洞书院', desc: '庐山脚下的“海内第一书院”，朱熹重兴并亲订《白鹿洞书院揭示》，影响深远。' },
  ],
  新余市: [
    { name: '蒙山书院', desc: '新余蒙山一带的著名书院，与石门、正德等书院并称。' },
    { name: '瀛洲书院', desc: '新余现存较完整的古代书院，清咸丰元年（1851）创建于城南虎瞰山。' },
  ],
  鹰潭市: [
    { name: '象山书院', desc: '位于贵溪，陆九渊讲学、心学发祥之地，初名象山精舍。' },
  ],
  赣州市: [
    { name: '阳明书院', desc: '赣州，王阳明巡抚南赣时讲学兴学之地，阳明心学传播的重要一站。' },
    { name: '潋江书院', desc: '位于兴国，江西书院名录中的赣南名院，兼具近代红色文化印记。' },
  ],
  吉安市: [
    { name: '白鹭洲书院', desc: '白鹭洲上的庐陵名院，文天祥母校，“文章节义”之邦的象征。' },
    { name: '龙江书院', desc: '位于井冈山，毛泽东、朱德首次会见之地，兼具书院与红色革命遗址双重身份。' },
  ],
  宜春市: [
    { name: '华林书院', desc: '位于奉新，北宋胡仲尧兴办，藏书延师、广纳寒士，开江西民间书院兴学之风。' },
    { name: '昌黎书院', desc: '袁州（今宜春）为纪念韩愈而建的书院，是赣西文教的重要象征。' },
  ],
  抚州市: [
    { name: '兴鲁书院', desc: '临川（今抚州）的历史名院，与曾巩及临川文脉关系密切。' },
    { name: '盱江书院', desc: '位于南城，江西书院名录中的抚州名院。' },
  ],
  上饶市: [
    { name: '鹅湖书院', desc: '位于铅山，朱熹、陆九渊“鹅湖之会”论辩之地，宋明理学史的标志性现场。' },
    { name: '信江书院', desc: '上饶市区信江之畔的著名书院。' },
    { name: '叠山书院', desc: '位于弋阳，纪念南宋忠臣谢枋得（号叠山）。' },
  ],
}

// 各书院的配图（相对“书院文化图片”目录）。有实拍用实拍，没有的用书院事件画。
// 悬停时在简介左侧显示一张简图；找不到配图的书院回退成首字印章。
const ACADEMY_IMAGES: Record<string, string> = {
  豫章书院: '组织画家绘制了十大书院事件图/省会豫章书院的设立.jpg',
  白鹿洞书院: '组织拍摄了江西遗存书院/江西四大书院/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG',
  象山书院: '组织拍摄了江西遗存书院/江西四大书院/象山书院/象山书院遗址全景.JPG',
  鹅湖书院: '组织拍摄了江西遗存书院/江西四大书院/鹅湖书院/鹅湖书院全景图.jpg',
  白鹭洲书院: '组织拍摄了江西遗存书院/江西四大书院/白鹭洲书院/白鹭洲书院风月楼.JPG',
  阳明书院: '组织拍摄了江西遗存书院/赣州阳明书院.JPG',
  潋江书院: '组织拍摄了江西遗存书院/赣州兴国潋江书院.JPG',
  龙江书院: '组织拍摄了江西遗存书院/吉安井冈山龙江书院.jpg',
  华林书院: '组织画家绘制了十大书院事件图/胡仲尧兴华林书院.jpg',
}

function assetThumb(src: string, w = 120, h = 120) {
  return '/api/v1/assets/thumb/academy/' + src.split('/').map(encodeURIComponent).join('/') + `?w=${w}&h=${h}`
}

const el = ref<HTMLDivElement | null>(null)
const rootEl = ref<HTMLDivElement | null>(null)
const router = useRouter()
let map: L.Map | null = null
let geoLayer: L.GeoJSON | null = null
let ro: ResizeObserver | null = null
let openTip: L.Tooltip | null = null
// 卡片（tooltip）改成可交互后，需要自己管理"什么时候关"：
// 移出省份不立刻关，给鼠标留 320ms 走到卡片上；鼠标进入卡片则取消关闭。
let tipCloseTimer: number | undefined
let tipHovered = false

function cancelTipClose() {
  if (tipCloseTimer !== undefined) {
    window.clearTimeout(tipCloseTimer)
    tipCloseTimer = undefined
  }
}

function closeTipNow() {
  cancelTipClose()
  tipHovered = false
  openTip?.close()
  openTip = null
}

function scheduleTipClose() {
  cancelTipClose()
  tipCloseTimer = window.setTimeout(() => {
    tipCloseTimer = undefined
    if (tipHovered) return
    openTip?.close()
    openTip = null
  }, 320)
}

function onTipClick(ev: MouseEvent) {
  const el = (ev.target as HTMLElement | null)?.closest('.jmap__card') as HTMLElement | null
  if (!el) return
  ev.stopPropagation()
  const acad = el.dataset.acad || ''
  const id = ACADEMY_ID[acad]
  closeTipNow()
  if (id) {
    router.push(`/academies/${id}`)
    return
  }
  const city = Object.keys(CITY_ACADEMIES).find((c) => (CITY_ACADEMIES[c] || []).some((a) => a.name === acad))
  router.push({ path: '/academies', query: city ? { city } : {} })
}

function bindTipEvents(tip: L.Tooltip) {
  const el = tip.getElement() as HTMLElement | undefined
  if (!el || el.dataset.bound === '1') return
  el.dataset.bound = '1'
  // 关键：让卡片自己吞掉鼠标事件。否则 mousedown 会冒泡到地图容器，
  // 被 Leaflet 的拖拽逻辑接管，卡片的点击就被当成"拖地图"而丢失。
  L.DomEvent.disableClickPropagation(el)
  L.DomEvent.disableScrollPropagation(el)
  el.addEventListener('mouseenter', () => {
    tipHovered = true
    cancelTipClose()
  })
  el.addEventListener('mouseleave', () => {
    tipHovered = false
    scheduleTipClose()
  })
  el.addEventListener('click', onTipClick)
}
// 全屏展示：优先用浏览器全屏 API（同一个地图实例直接铺满，内容与缩放位置完全一致），
// 不支持的浏览器退化成 CSS 覆盖层。两种情况下都用 .jmap--full 控制尺寸
// ——浏览器的 :fullscreen 伪类在部分浏览器会被解析器丢掉，靠类名更稳。
const isFullscreen = ref(false)
const fullMode = ref(false)
let nativeFsActive = false // 是否真的进了浏览器原生全屏（用于区分「请求被拒」与「用户按 Esc 退出」）

function syncFullscreen() {
  isFullscreen.value = fullMode.value
  // 容器尺寸变了：等浏览器完成布局再让 Leaflet 重算
  requestAnimationFrame(() => map?.invalidateSize())
  window.setTimeout(() => map?.invalidateSize(), 260)
}

function onFullscreenChange() {
  if (document.fullscreenElement) {
    nativeFsActive = true
    fullMode.value = true
  } else if (nativeFsActive) {
    // 只有「本来就在原生全屏、现在退出了」才关闭；请求被浏览器拒绝时不动兜底状态
    nativeFsActive = false
    fullMode.value = false
  }
  syncFullscreen()
}

async function toggleFullscreen() {
  const root = rootEl.value
  if (!root) return
  if (fullMode.value && !document.fullscreenElement) {
    fullMode.value = false
    syncFullscreen()
    return
  }
  if (document.fullscreenElement) {
    await document.exitFullscreen().catch(() => {})
    return
  }
  // 先加尺寸类，避免进入全屏的瞬间地图没铺满
  fullMode.value = true
  syncFullscreen()
  const req: ((o?: any) => Promise<void>) | undefined =
    root.requestFullscreen?.bind(root) || (root as any).webkitRequestFullscreen?.bind(root)
  if (req) {
    try {
      await req({ navigationUI: 'hide' })
      nativeFsActive = true
      return
    } catch {
      /* 浏览器拒绝（例如不是用户手势触发）：落到 CSS 覆盖层 */
      nativeFsActive = false
    }
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && fullMode.value && !document.fullscreenElement) {
    fullMode.value = false
    syncFullscreen()
  }
}

function clampTooltip(tip: L.Tooltip | null) {
  if (!tip || !map) return
  const container = tip.getElement() as HTMLElement | undefined
  const mapEl = map.getContainer()
  if (!container || !mapEl) return
  const mr = mapEl.getBoundingClientRect()
  const tr = container.getBoundingClientRect()
  const pad = 10
  let dx = 0
  let dy = 0
  if (tr.left < mr.left + pad) dx = mr.left + pad - tr.left
  else if (tr.right > mr.right - pad) dx = mr.right - pad - tr.right
  if (tr.top < mr.top + pad) dy = mr.top + pad - tr.top
  else if (tr.bottom > mr.bottom - pad) dy = mr.bottom - pad - tr.bottom
  if (!dx && !dy) return
  const m = /translate3d\(\s*(-?\d+(?:\.\d+)?)px\s*,\s*(-?\d+(?:\.\d+)?)px\s*/.exec(
    container.style.transform || '',
  )
  if (!m) return
  container.style.transform = `translate3d(${parseFloat(m[1]) + dx}px, ${parseFloat(m[2]) + dy}px, 0)`
}

// 书院名 → 详情页 id（有详情页的优先跳详情，没有的跳到该市书院列表）
const ACADEMY_ID: Record<string, string> = Object.fromEntries(ACADEMIES.map((a) => [a.name, a.id]))

function tooltipHtml(name: string): string {
  const items = CITY_ACADEMIES[name] || []
  const rows = items.length
    ? items
        .map((a) => {
          const img = ACADEMY_IMAGES[a.name]
          const thumb = img
            ? `<img src="${assetThumb(img)}" alt="${a.name}" style="width:46px;height:46px;border-radius:6px;object-fit:cover;flex:none;background:#f2efe8;" />`
            : `<span style="width:46px;height:46px;border-radius:6px;flex:none;display:flex;align-items:center;justify-content:center;background:#f4efe4;color:#b08a52;font-size:18px;font-weight:700;">${a.name.slice(0, 1)}</span>`
          // 每条书院都是可点击条目：点击跳到该书院详情（没有详情页的跳到该市列表）
          const detail = ACADEMY_ID[a.name] ? `查看 ›` : `看该市 ›`
          return `
            <div class="jmap__card" data-acad="${a.name}" title="查看《${a.name}》">
              ${thumb}
              <div style="min-width:0;">
                <div style="color:#2c3e50;font-weight:700;font-size:12px;line-height:1.4;">${a.name}<span style="float:right;color:#b08a52;font-weight:600;">${detail}</span></div>
                <div style="margin-top:2px;color:#6b6b6b;font-size:11px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">${a.desc}</div>
              </div>
            </div>`
        })
        .join('')
    : `<div class="jmap__empty">暂无书院资料</div>`

  return `
    <div style="white-space:normal;">
      <div style="padding:8px 10px;color:#8a5a2b;font-weight:700;font-size:13px;">${name}</div>
      ${rows}
    </div>`
}

async function init() {
  if (!el.value) return
  const resp = await fetch('/maps/jiangxi.json')
  if (!resp.ok) return
  const geo: any = await resp.json()

  map = L.map(el.value, {
    center: [27.6, 115.9],
    zoom: 7,
    minZoom: 4,
    zoomControl: false,
    scrollWheelZoom: true,
  })

  const attribution =
    '&copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
  const satellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution, minZoom: 4, maxZoom: 18, noWrap: true },
  )
  satellite.addTo(map)

  geoLayer = L.geoJSON(geo, {
    style: () => ({
      color: '#b98a4a',
      weight: 1.5,
      fillColor: '#e7b84f',
      fillOpacity: 0.22,
    }),
    onEachFeature: (feature: any, layer: any) => {
      const name = feature.properties?.name as string
      layer.on('mouseover', () => {
        layer.setStyle({ fillColor: '#d99a2b', fillOpacity: 0.48, weight: 2.5 })
        layer.bringToFront()
      })
      layer.on('mouseout', () => geoLayer?.resetStyle(layer))
      layer.bindTooltip(tooltipHtml(name), {
        className: 'jmap__tipbox',
        direction: 'top',
        opacity: 1,
        // 关键：卡片必须可交互，否则鼠标一移进卡片就"离开"了本省多边形，
        // 既会立刻关闭卡片，又会把点击穿透给卡片下方的邻省（点豫章书院跳成九江）。
        interactive: true,
        sticky: false,
      })
      // 覆盖 Leaflet 默认的"移出图形立即关闭"，改为延时关闭（见 scheduleTipClose）
      layer.off('mouseout', (layer as any).closeTooltip, layer)
      layer.on('mouseout', scheduleTipClose)
      layer.on('mouseover', cancelTipClose)
      layer.on('click', () => {
        closeTipNow()
        router.push({ path: '/academies', query: { city: name } })
      })
    },
  }).addTo(map)

  // 缩放下限锁死在江西范围：最远只能缩到刚好看全江西，且不能拖出省界
  const jxBounds = geoLayer.getBounds()
  const applyJiangxiLimits = () => {
    if (!map || !geoLayer) return
    const bounds = geoLayer.getBounds()
    const fitZoom = map.getBoundsZoom(bounds, false, L.point(24, 24))
    map.setMinZoom(fitZoom)
    map.setMaxBounds(bounds.pad(0.08))
    return fitZoom
  }
  const fitZoom = applyJiangxiLimits() ?? map.getZoom()
  map.setView(jxBounds.getCenter(), fitZoom)

  for (const f of geo.features) {
    const name = f.properties?.name as string
    const c = f.properties?.centroid || f.properties?.center
    if (!name || !c) continue
    L.tooltip({ permanent: true, direction: 'center', className: 'jmap__label', interactive: false })
      .setLatLng([c[1], c[0]])
      .setContent(`<span>${name}</span>`)
      .addTo(map)
  }

  map.on('tooltipopen', (e: any) => {
    const tip = e.tooltip as L.Tooltip
    if (tip.options.className === 'jmap__tipbox') {
      cancelTipClose()
      tipHovered = false
      openTip = tip
      bindTipEvents(tip)
      requestAnimationFrame(() => clampTooltip(tip))
    }
  })
  map.on('tooltipclose', (e: any) => {
    if (e.tooltip === openTip) openTip = null
  })
  // 缩放时收起卡片（卡片锚定在省份上，平移时会跟着走，不必关闭）
  map.on('zoomstart', () => closeTipNow())
  // 点空白处收起卡片
  map.on('click', () => closeTipNow())
  map.on('zoomend moveend', () => {
    if (openTip) requestAnimationFrame(() => clampTooltip(openTip))
  })

  ro = new ResizeObserver(() => {
    map?.invalidateSize()
    const z = applyJiangxiLimits()
    if (z !== undefined && map && map.getZoom() < z) map.setZoom(z)
  })
  ro.observe(el.value)
  setTimeout(() => map?.invalidateSize(), 0)
}

onMounted(init)
onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange as EventListener)
  window.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange as EventListener)
  window.removeEventListener('keydown', onKeydown)
  ro?.disconnect()
  map?.remove()
  map = null
})
</script>

<template>
  <div ref="rootEl" class="jmap" :class="{ 'jmap--full': fullMode }">
    <div ref="el" class="jmap__chart" />
    <button
      type="button"
      class="jmap__fs"
      :title="isFullscreen ? '退出全屏（Esc）' : '全屏查看书院分布图'"
      :aria-label="isFullscreen ? '退出全屏' : '全屏查看地图'"
      @click.stop="toggleFullscreen"
      @mousedown.stop
      @dblclick.stop
    >
      <svg v-if="!isFullscreen" viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
        <path
          fill="currentColor"
          d="M4 9V4h5v2H6v3H4zm11-5h5v5h-2V6h-3V4zM4 15h2v3h3v2H4v-5zm14 0h2v5h-5v-2h3v-3z"
        />
      </svg>
      <span v-else class="jmap__fsX" aria-hidden="true">✕</span>
      <span>{{ isFullscreen ? '退出全屏' : '全屏' }}</span>
    </button>
    <p class="jmap__hint">将鼠标移到城市上查看书院介绍 · 滚轮缩放、可拖拽</p>
  </div>
</template>

<style scoped>
.jmap {
  position: relative;
  width: 100%;
}
.jmap__chart {
  width: 100%;
  height: 560px;
  background: #e7ecdf;
}
.jmap__hint {
  margin: 10px 0 0;
  text-align: center;
  color: var(--muted);
  font-size: 12.5px;
}

/* 右上角「全屏」按钮（浮在地图之上，避开 Leaflet 控件层） */
.jmap__fs {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1200;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid rgba(184, 138, 74, 0.55);
  background: rgba(255, 255, 255, 0.93);
  color: #8a5a2b;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 3px 10px rgba(31, 42, 54, 0.18);
  backdrop-filter: blur(6px);
  transition: background 0.15s ease, transform 0.15s ease;
}
.jmap__fs:hover {
  background: #fff;
  transform: translateY(-1px);
}
.jmap__fs:active {
  transform: translateY(0);
}
.jmap__fsX {
  font-size: 13px;
  line-height: 1;
}

/* 全屏展示（浏览器全屏与 CSS 兜底共用这套类名）：
   同一个地图实例直接铺满整屏，中心点与缩放保持不变 */
.jmap--full {
  position: fixed;
  inset: 0;
  z-index: 3000;
  width: 100vw;
  height: 100vh;
  padding: 0;
  background: #0d1117;
}
.jmap--full .jmap__chart {
  height: 100%;
}
.jmap--full .jmap__hint {
  display: none;
}
.jmap--full .jmap__fs {
  top: 18px;
  right: 20px;
}

/* 悬停富文本：允许换行 */
:deep(.leaflet-tooltip.jmap__tipbox) {
  width: 300px;
  box-sizing: border-box;
  padding: 0;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid #d8c49b;
  border-radius: 10px;
  box-shadow: 0 6px 18px rgba(31, 42, 54, 0.16);
  white-space: normal;
}
:deep(.leaflet-tooltip.jmap__tipbox::before) {
  display: none;
}

/* 卡片里的每条书院：可点击，带悬停反馈 */
:deep(.jmap__tipbox .jmap__card) {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 7px 10px;
  border-top: 1px solid #efe9dc;
  cursor: pointer;
  transition: background 0.14s ease;
}
:deep(.jmap__tipbox .jmap__card:hover) {
  background: #fbf5e8;
}
:deep(.jmap__tipbox .jmap__card:last-child) {
  border-radius: 0 0 10px 10px;
}
:deep(.jmap__tipbox .jmap__empty) {
  padding: 8px 10px;
  color: #6b6b6b;
  font-size: 11px;
}

/* 常驻城市名标注 */
:deep(.leaflet-tooltip.jmap__label) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  white-space: nowrap;
}
:deep(.leaflet-tooltip.jmap__label::before) {
  display: none;
}
:deep(.jmap__label span) {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.86);
  color: #2c3e50;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

@media (max-width: 760px) {
  .jmap__chart {
    height: 420px;
  }
}
</style>
