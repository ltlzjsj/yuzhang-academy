<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
let cityClickAt = 0 // 记录城市点击时刻，防止随后的 map click 立刻把面板关掉

// 书院列表面板：点击城市时展开（停靠在地图内，不再用悬浮卡片承载点击，
// 悬浮只保留一句轻提示，鼠标移出城市即消失）
const panelCity = ref<string | null>(null)
const panelItems = computed(() => (panelCity.value ? CITY_ACADEMIES[panelCity.value] || [] : []))

function closePanel() {
  panelCity.value = null
}

function openAcademy(name: string) {
  const id = ACADEMY_ID[name]
  const city = panelCity.value
  closePanel()
  if (id) router.push(`/academies/${id}`)
  else router.push({ path: '/academies', query: city ? { city } : {} })
}

function onMapKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closePanel()
}
// 全屏展示：优先用浏览器全屏 API（同一个地图实例直接铺满，内容与缩放位置完全一致），
// 不支持的浏览器退化成 CSS 覆盖层。两种情况下都用 .jmap--full 控制尺寸
// ——浏览器的 :fullscreen 伪类在部分浏览器会被解析器丢掉，靠类名更稳。
const isFullscreen = ref(false)
const fullMode = ref(false)
let nativeFsActive = false // 是否真的进了浏览器原生全屏（用于区分「请求被拒」与「用户按 Esc 退出」）
// 进全屏前的视角：退出全屏时原样恢复，避免小地图停在全屏时的特写状态
let preFullView: { lat: number; lng: number; zoom: number } | null = null
// 进出全屏的过渡期：这段时间内不要跑"自动贴合"逻辑（容器尺寸还会变，
// 否则会把最小缩放抬高、把小地图顶到特写档位）
let fsTransitionUntil = 0

function rememberView() {
  if (!map) return
  const c = map.getCenter()
  preFullView = { lat: c.lat, lng: c.lng, zoom: map.getZoom() }
}

function restoreView() {
  const v = preFullView
  preFullView = null
  if (!map || !v) return
  // 退出全屏时容器尺寸会经历一段过渡，这里多次套用，确保最终停回原视角
  const apply = () => {
    map?.invalidateSize()
    map?.setView([v.lat, v.lng], v.zoom, { animate: false })
  }
  fsTransitionUntil = Date.now() + 800
  requestAnimationFrame(apply)
  window.setTimeout(apply, 160)
  window.setTimeout(apply, 420)
  window.setTimeout(() => {
    apply()
    fsTransitionUntil = 0
  }, 800)
}

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
    restoreView()
  }
  syncFullscreen()
}

async function toggleFullscreen() {
  const root = rootEl.value
  if (!root) return
  if (fullMode.value && !document.fullscreenElement) {
    fullMode.value = false
    syncFullscreen()
    restoreView()
    return
  }
  if (document.fullscreenElement) {
    await document.exitFullscreen().catch(() => {})
    return
  }
  // 先加尺寸类，避免进入全屏的瞬间地图没铺满
  rememberView()
  // 过渡期内不跑"自动贴合"，全屏只换窗口大小，视角保持不变
  fsTransitionUntil = Date.now() + 900
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
    restoreView()
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

/** 悬浮提示：只报一句"哪个市、几所书院、点击查看"，鼠标移出即消失。 */
function tooltipHtml(name: string): string {
  const n = (CITY_ACADEMIES[name] || []).length
  const tail = n ? `${n} 所书院 · 点击查看` : '暂无书院资料'
  return `<div class="jmap__tip"><b>${name}</b><span>${tail}</span></div>`
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
    // 不显示右下角的署名条（Leaflet / Esri 版权信息）
    attributionControl: false,
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
        // 悬浮提示不承载点击，保持默认"移出即关闭"
        interactive: false,
        sticky: false,
      })
      // 点击城市：在地图内展开该市书院列表面板（不再用悬浮卡片承载点击）
      layer.on('click', (ev: L.LeafletMouseEvent) => {
        // 注意：这里必须把「Leaflet 事件」交给 DomEvent.stop —— 它会设置 originalEvent._stopped，
        // Leaflet 才不会再把这个点击冒泡成 map 的 click（否则面板刚开就被关掉）。
        L.DomEvent.stop(ev)
        cityClickAt = Date.now()
        panelCity.value = name
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
      openTip = tip
      requestAnimationFrame(() => clampTooltip(tip))
    }
  })
  map.on('tooltipclose', (e: any) => {
    if (e.tooltip === openTip) openTip = null
  })
  // 点地图空白处收起书院面板
  map.on('click', () => {
    if (Date.now() - cityClickAt < 60) return
    closePanel()
  })
  map.on('zoomend moveend', () => {
    if (openTip) requestAnimationFrame(() => clampTooltip(openTip))
  })

  ro = new ResizeObserver(() => {
    map?.invalidateSize()
    // 全屏期间与进出过渡期都不跑"自动贴合"：
    // 全屏只是把窗口变大（同一缩放看到更多范围），这样退出后小地图不会被顶成特写。
    if (fullMode.value || Date.now() < fsTransitionUntil) return
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
  window.addEventListener('keydown', onMapKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', onFullscreenChange as EventListener)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('keydown', onMapKeydown)
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

    <!-- 点击城市后展开的书院面板：停靠在地图内，不与鼠标状态纠缠 -->
    <aside v-if="panelCity" class="jmap__panel" aria-label="该市书院列表">
      <header class="jmap__panelHead">
        <span class="jmap__panelCity">{{ panelCity }}</span>
        <span class="jmap__panelCount">{{ panelItems.length }} 所书院</span>
        <button type="button" class="jmap__panelClose" aria-label="关闭" @click="closePanel">×</button>
      </header>
      <div class="jmap__panelBody">
        <button
          v-for="a in panelItems"
          :key="a.name"
          type="button"
          class="jmap__panelItem"
          :title="`查看《${a.name}》`"
          @click="openAcademy(a.name)"
        >
          <img
            v-if="ACADEMY_IMAGES[a.name]"
            class="jmap__panelThumb"
            :src="assetThumb(ACADEMY_IMAGES[a.name])"
            :alt="a.name"
            loading="lazy"
          />
          <span v-else class="jmap__panelSeal">{{ a.name.slice(0, 1) }}</span>
          <span class="jmap__panelText">
            <b>{{ a.name }}<i>{{ ACADEMY_ID[a.name] ? '查看 ›' : '该市 ›' }}</i></b>
            <em>{{ a.desc }}</em>
          </span>
        </button>
        <p v-if="!panelItems.length" class="jmap__panelEmpty">暂无书院资料</p>
      </div>
      <RouterLink class="jmap__panelMore" :to="{ path: '/academies', query: { city: panelCity } }">
        查看 {{ panelCity }} 全部书院 →
      </RouterLink>
    </aside>
    <p class="jmap__hint">点击城市查看该市书院 · 滚轮缩放、可拖拽</p>
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

/* 悬停轻提示：只报"哪个市 / 几所书院"，不承载点击，移出即消失 */
:deep(.leaflet-tooltip.jmap__tipbox) {
  box-sizing: border-box;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #d8c49b;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(31, 42, 54, 0.14);
  white-space: nowrap;
}
:deep(.leaflet-tooltip.jmap__tipbox::before) {
  display: none;
}
:deep(.jmap__tip) {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
:deep(.jmap__tip b) {
  color: #2c3e50;
  font-size: 12.5px;
}
:deep(.jmap__tip span) {
  color: #8a5a2b;
  font-size: 11.5px;
}

/* 点击城市后展开的书院面板：停靠在地图内，由用户显式关闭 */
.jmap__panel {
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 1200;
  width: min(336px, 48%);
  max-height: calc(100% - 28px);
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  border: 1px solid rgba(184, 138, 74, 0.45);
  background: rgba(255, 253, 248, 0.965);
  box-shadow: 0 12px 30px rgba(31, 42, 54, 0.22);
  overflow: hidden;
}
.jmap__panelHead {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(184, 138, 74, 0.22);
}
.jmap__panelCity {
  font-size: 15px;
  font-weight: 800;
  color: #2c3e50;
}
.jmap__panelCount {
  font-size: 12px;
  color: #8a5a2b;
}
.jmap__panelClose {
  margin-left: auto;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8a5a2b;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.jmap__panelClose:hover {
  background: rgba(184, 138, 74, 0.16);
}
.jmap__panelBody {
  overflow-y: auto;
}
.jmap__panelItem {
  display: flex;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-bottom: 1px solid #f1ece1;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease;
}
.jmap__panelItem:hover {
  background: #fbf5e8;
}
.jmap__panelThumb {
  width: 48px;
  height: 48px;
  flex: none;
  border-radius: 8px;
  object-fit: cover;
  background: #f2efe8;
}
.jmap__panelSeal {
  width: 48px;
  height: 48px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #f4efe4;
  color: #b08a52;
  font-size: 18px;
  font-weight: 700;
}
.jmap__panelText {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.jmap__panelText b {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: #2c3e50;
}
.jmap__panelText i {
  flex: none;
  font-style: normal;
  font-weight: 600;
  color: #b08a52;
}
.jmap__panelText em {
  font-style: normal;
  font-size: 11.5px;
  line-height: 1.5;
  color: #6b6b6b;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.jmap__panelEmpty {
  padding: 10px 12px;
  font-size: 12px;
  color: #6b6b6b;
}
.jmap__panelMore {
  display: block;
  padding: 9px 12px;
  font-size: 12.5px;
  color: #8a5a2b;
  text-decoration: none;
  border-top: 1px solid rgba(184, 138, 74, 0.22);
  background: rgba(248, 243, 232, 0.72);
}
.jmap__panelMore:hover {
  background: #f6eeda;
}

/* 常驻城市名标注 */
:deep(.leaflet-tooltip.jmap__label) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  white-space: nowrap;
}

/* 点击省份后浏览器会给 SVG 路径画一圈焦点框，去掉它 */
:deep(.leaflet-overlay-pane .leaflet-interactive:focus) {
  outline: none;
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
