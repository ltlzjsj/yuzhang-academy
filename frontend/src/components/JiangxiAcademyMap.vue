<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useRouter } from 'vue-router'

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
const router = useRouter()
let map: L.Map | null = null
let geoLayer: L.GeoJSON | null = null
let ro: ResizeObserver | null = null
let openTip: L.Tooltip | null = null

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

function tooltipHtml(name: string): string {
  const items = CITY_ACADEMIES[name] || []
  const rows = items.length
    ? items
        .map((a) => {
          const img = ACADEMY_IMAGES[a.name]
          const thumb = img
            ? `<img src="${assetThumb(img)}" alt="${a.name}" style="width:46px;height:46px;border-radius:6px;object-fit:cover;flex:none;background:#f2efe8;" />`
            : `<span style="width:46px;height:46px;border-radius:6px;flex:none;display:flex;align-items:center;justify-content:center;background:#f4efe4;color:#b08a52;font-size:18px;font-weight:700;">${a.name.slice(0, 1)}</span>`
          return `
            <div style="display:flex;gap:8px;align-items:flex-start;padding:6px 10px;border-top:1px solid #efe9dc;">
              ${thumb}
              <div style="min-width:0;">
                <div style="color:#2c3e50;font-weight:700;font-size:12px;line-height:1.4;">${a.name}</div>
                <div style="margin-top:2px;color:#6b6b6b;font-size:11px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">${a.desc}</div>
              </div>
            </div>`
        })
        .join('')
    : `<div style="padding:8px 10px;color:#6b6b6b;font-size:11px;">暂无书院资料</div>`

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
      })
      layer.on('click', () => {
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
      openTip = tip
      requestAnimationFrame(() => clampTooltip(tip))
    }
  })
  map.on('tooltipclose', (e: any) => {
    if (e.tooltip === openTip) openTip = null
  })
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
onBeforeUnmount(() => {
  ro?.disconnect()
  map?.remove()
  map = null
})
</script>

<template>
  <div class="jmap">
    <div ref="el" class="jmap__chart" />
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
