<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { listActivities } from '@/api/activities'

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}
function thumb(url: string | null | undefined, w = 480, h = 300): string {
  if (!url || !url.includes('/assets/academy/')) return url || ''
  return url.replace('/assets/academy/', '/assets/thumb/academy/') + `?w=${w}&h=${h}`
}
const PHOTOS = '组织拍摄了江西遗存书院/江西四大书院'
const PAINT = '组织画家绘制了十大书院事件图'
const heroImg = assetUrl(`${PHOTOS}/鹅湖书院/鹅湖书院全景图.jpg`)

type Status = 'open' | 'ongoing' | 'closed'
interface Activity {
  id: number
  cat: string
  title: string
  summary: string
  body: string
  date: string
  period: string
  place: string
  audience: string
  status: Status
  highlights: string[]
  image: string
}

const STATUS_LABEL: Record<Status, string> = { open: '报名中', ongoing: '进行中', closed: '已结束' }

const categories = ['全部', '讲会论道', '研学体验', '文化交流', '书院公告']
const activeCat = ref('全部')

// 后端有数据则用后端；否则回退到内置示例，保证页面始终有内容可展示。
const FALLBACK: Activity[] = [
  {
    id: 1,
    cat: '书院公告',
    title: '豫章书院数智化项目正式启动',
    summary: '引入知识检索、AI 导览与数字档案系统，开放在线「问书院」。',
    body: '豫章书院数智化项目正式上线，依托知识库检索、智能问答与历史名人互动等技术，将馆藏典籍、碑刻题咏与书院史事系统数字化，向公众开放「问书院」在线服务。项目以「让典籍可问、史事可询、先贤可对」为目标，推动文化体验与教育服务深度融合。',
    date: '2026-04-01',
    period: '长期开放',
    place: '线上 · 豫章书院数智平台',
    audience: '面向社会公众',
    status: 'ongoing',
    highlights: ['在线问书院，回答尽附出处', 'AI 数字导览先生随时答疑', '历史名人隔空对谈'],
    image: assetUrl(`${PAINT}/省会豫章书院的设立.jpg`),
  },
  {
    id: 2,
    cat: '讲会论道',
    title: '传统文化讲座系列 · 江右理学专题',
    summary: '邀学者分享儒学经典、书院礼仪与江右文化传承。',
    body: '本季讲座聚焦江右理学源流，邀请高校学者与书院研究者，围绕白鹿洞之规、象山心学、阳明良知等主题展开，兼及古籍解读、书院礼仪与当代创新。每场设主讲、对谈与现场问难环节，重现书院「会讲」之风。',
    date: '2026-03-28',
    period: '每周六 14:30',
    place: '豫章书院 · 明伦堂',
    audience: '高校师生 / 文化爱好者',
    status: 'open',
    highlights: ['名家主讲 + 现场会讲问难', '每场赠书院文化读本', '可线上同步直播回看'],
    image: assetUrl(`${PAINT}/朱熹亲订《白鹿洞书院揭示》.jpg`),
  },
  {
    id: 3,
    cat: '研学体验',
    title: '春季研学营 · 走读江右四大书院',
    summary: '书院探访、古籍阅读、礼仪体验与主题讨论。',
    body: '春季研学营带领营员实地走读白鹿洞、白鹭洲、鹅湖、豫章等江右名院，安排古籍诵读、拓片体验、束脩开笔礼与分组主题研讨，由书院导师与数字导览先生协同带教，让青少年在行走中感知千年讲学传统。',
    date: '2026-03-25',
    period: '4 月 · 两日一晚',
    place: '南昌 / 庐山 / 吉安 / 铅山',
    audience: '中小学及社会公众',
    status: 'open',
    highlights: ['四大书院实地走读', '开笔礼 · 拓片 · 古籍诵读', '结业颁发研学证书'],
    image: assetUrl(`${PHOTOS}/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG`),
  },
  {
    id: 4,
    cat: '书院公告',
    title: '书院入选省级文化遗产保护单位',
    summary: '成为江右文化与儒学传承的重要标志。',
    body: '豫章书院正式入选省级文化遗产保护单位，其建筑遗存、碑刻匾额与讲学传统获得系统性保护。书院将以此为契机，深化数字化保护与教育创新实践，让文化遗产在当代焕发新生。',
    date: '2026-03-20',
    period: '已公布',
    place: '江西 · 南昌',
    audience: '—',
    status: 'closed',
    highlights: ['建筑遗存系统性修缮', '碑刻题咏数字建档', '挂牌省级保护单位'],
    image: assetUrl(`${PHOTOS}/白鹭洲书院/白鹭洲书院云章阁.JPG`),
  },
  {
    id: 5,
    cat: '文化交流',
    title: '鹅湖之会 · 朱陆论道复现雅集',
    summary: '重现「尊德性」与「道问学」的千古论辩。',
    body: '于鹅湖书院旧址举办文化雅集，以情景再现与学术对谈相结合的方式，重现朱熹、陆九渊「鹅湖之会」的为学异同。雅集设古琴、茶礼与诗文唱和，邀两岸学人共论尊德性与道问学之会通。',
    date: '2026-03-12',
    period: '半日',
    place: '铅山 · 鹅湖书院',
    audience: '学界 / 文化机构',
    status: 'closed',
    highlights: ['情景再现朱陆论道', '古琴 · 茶礼 · 诗文唱和', '两岸学人会讲'],
    image: assetUrl(`${PAINT}/“尊德性”与“道问学”的鹅湖之会.jpg`),
  },
  {
    id: 6,
    cat: '文化交流',
    title: '白鹭洲「文章节义」主题展',
    summary: '以江万里与文天祥为线，讲述书院气节教育。',
    body: '展览以白鹭洲书院「文章节义」之教为主线，串联江万里创院、培育文天祥等忠义之士的史事，结合书院画作、文献与多媒体装置，呈现江右士人「读书明理、砥砺名节」的精神谱系。',
    date: '2026-02-28',
    period: '展期一个月',
    place: '吉安 · 白鹭洲书院',
    audience: '面向社会公众',
    status: 'closed',
    highlights: ['十大书院事件画作展出', '文天祥与白鹭洲专题', '沉浸式多媒体导览'],
    image: assetUrl(`${PAINT}/白鹭洲书院的“文章节义”.jpg`),
  },
]

const list = ref<Activity[]>(FALLBACK)

onMounted(async () => {
  try {
    const rows = await listActivities()
    if (rows.length) {
      list.value = rows.map((r) => ({
        id: r.id,
        cat: r.category,
        title: r.title,
        summary: r.summary,
        body: r.body,
        date: r.event_date,
        period: r.period,
        place: r.place,
        audience: r.audience,
        status: r.status,
        highlights: r.highlights || [],
        image: r.image_url || assetUrl(r.image || `${PAINT}/省会豫章书院的设立.jpg`),
      }))
    }
  } catch {
    /* 后端未就绪时静默使用内置示例 */
  }
})

const filtered = computed(() =>
  activeCat.value === '全部' ? list.value : list.value.filter((a) => a.cat === activeCat.value),
)

const detail = ref<Activity | null>(null)

interface Milestone {
  era: string
  title: string
  desc: string
  image: string
}
const milestones: Milestone[] = [
  { era: '唐', title: '东佳书堂的设立', desc: '江州陈氏义门聚族而居、设东佳书堂藏书延师，开私家聚徒讲学之先，为后世书院之雏形。', image: assetUrl(`${PAINT}/东佳书堂的设立.jpg`) },
  { era: '五代', title: '唐明宗敕额匡山书院', desc: '后唐明宗为匡山书院赐额，书院得官方褒扬，私学与官学渐相辉映，讲学之风益盛。', image: assetUrl(`${PAINT}/唐明宗敕额匡山书院.jpg`) },
  { era: '北宋', title: '胡仲尧兴华林书院', desc: '奉新华林胡氏倾家兴办华林书院，藏书延师、广纳寒士，开江西民间书院兴学之风。', image: assetUrl(`${PAINT}/胡仲尧兴华林书院.jpg`) },
  { era: '南宋', title: '朱熹亲订《白鹿洞书院揭示》', desc: '朱熹重修白鹿洞书院并亲订学规，确立书院讲学的宗旨与规范，影响后世数百年。', image: assetUrl(`${PAINT}/朱熹亲订《白鹿洞书院揭示》.jpg`) },
  { era: '南宋', title: '象山精舍与赣学的兴起', desc: '陆九渊结庐象山讲学，倡「心即理」「发明本心」，开陆王心学之先河，赣学由是兴起。', image: assetUrl(`${PAINT}/象山精舍与赣学的兴起.jpg`) },
  { era: '南宋', title: '尊德性与道问学的鹅湖之会', desc: '吕祖谦主盟，朱熹、陆九渊于鹅湖会讲，论辩为学异同，成中国思想史上的千古盛事。', image: assetUrl(`${PAINT}/“尊德性”与“道问学”的鹅湖之会.jpg`) },
  { era: '南宋', title: '白鹭洲书院的文章节义', desc: '江万里创建吉州白鹭洲书院，倡「文章节义」之教，培育文天祥等忠义之士，气节为后世所重。', image: assetUrl(`${PAINT}/白鹭洲书院的“文章节义”.jpg`) },
  { era: '明', title: '省会豫章书院的设立', desc: '豫章书院设于省会南昌，遂为江右理学与科举教育之重镇，士子负笈而来，讲诵之声不绝。', image: assetUrl(`${PAINT}/省会豫章书院的设立.jpg`) },
  { era: '清', title: '奎光书院与客家文化', desc: '奎光书院兴于客家聚居之地，崇文重教蔚然成风，书院文化与客家民系深相融合。', image: assetUrl(`${PAINT}/奎光书院与客家文化.jpg`) },
  { era: '近代', title: '潋江书院与红色故土', desc: '兴国潋江书院于近代成为革命教育的重要场所，千年文脉与红色故土在此交汇。', image: assetUrl(`${PAINT}/潋江书院与红色故土.jpg`) },
]
</script>

<template>
  <div class="act">
    <!-- Hero -->
    <section class="act__hero" :style="{ backgroundImage: `url('${heroImg}')` }">
      <div class="act__shade" />
      <div class="shell act__heroIn">
        <p class="eyebrow">活动资讯</p>
        <h1 class="h-serif">讲会 · 研学 · 文化雅集</h1>
        <p class="act__lead">
          书院之风，于今犹存。讲会论道、研学走读、文化交流接续举办，让千年讲学传统在当下持续生长。
        </p>
      </div>
    </section>

    <!-- 近期活动 -->
    <section class="shell act__body">
      <div class="act__head">
        <div>
          <p class="eyebrow">近期活动</p>
          <h2 class="h-serif">书院动态一览</h2>
        </div>
        <div class="tabs">
          <button
            v-for="c in categories"
            :key="c"
            class="tab"
            :class="{ 'tab--on': activeCat === c }"
            @click="activeCat = c"
          >{{ c }}</button>
        </div>
      </div>

      <div class="grid">
        <article v-for="a in filtered" :key="a.id" class="card" @click="detail = a">
          <div class="card__media">
            <img :src="thumb(a.image, 480, 300)" :alt="a.title" loading="lazy" />
            <span class="card__cat">{{ a.cat }}</span>
            <span class="card__status" :class="`is-${a.status}`">{{ STATUS_LABEL[a.status] }}</span>
          </div>
          <div class="card__body">
            <h3 class="h-serif">{{ a.title }}</h3>
            <p>{{ a.summary }}</p>
            <div class="card__meta">
              <span>🗓 {{ a.period }}</span>
              <span>📍 {{ a.place }}</span>
            </div>
            <span class="card__more">查看详情 →</span>
          </div>
        </article>
      </div>

      <p v-if="!filtered.length" class="empty">该分类暂无活动，敬请期待。</p>
    </section>

    <!-- 书院大事记 -->
    <section class="chron">
      <div class="shell">
        <p class="eyebrow eyebrow--gold">书院大事记</p>
        <h2 class="chron__title h-serif">江西书院十大史事</h2>
        <p class="chron__lead">由画家绘制的十帧书院事件图，串起自唐迄今千年讲学的高光时刻。</p>
        <div class="timeline">
          <article v-for="(m, i) in milestones" :key="m.title" class="ms" :class="{ 'ms--rev': i % 2 === 1 }">
            <div class="ms__media">
              <img :src="thumb(m.image, 640, 480)" :alt="m.title" loading="lazy" />
            </div>
            <div class="ms__text">
              <span class="ms__era h-serif">{{ m.era }}</span>
              <h3 class="h-serif">{{ m.title }}</h3>
              <p>{{ m.desc }}</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="shell">
      <div class="act__cta">
        <h3 class="h-serif">想参与书院活动，或深入了解书院史事？</h3>
        <p>向「问书院」发问，或与历代名儒隔空对谈，让典籍与史事即问即答。</p>
        <div class="act__btns">
          <RouterLink class="btn-solid" to="/qa">向书院请教</RouterLink>
          <RouterLink class="btn-outline" to="/figures">历史名人互动</RouterLink>
        </div>
      </div>
    </section>

    <!-- 详情弹窗 -->
    <Teleport to="body">
      <div v-if="detail" class="dlg" @click.self="detail = null">
        <div class="dlg__panel">
          <button class="dlg__close" @click="detail = null">✕</button>
          <div class="dlg__media">
            <img :src="detail.image" :alt="detail.title" />
            <span class="card__status" :class="`is-${detail.status}`">{{ STATUS_LABEL[detail.status] }}</span>
          </div>
          <div class="dlg__body">
            <span class="dlg__cat">{{ detail.cat }}</span>
            <h3 class="h-serif">{{ detail.title }}</h3>
            <dl class="dlg__info">
              <div><dt>时间</dt><dd>{{ detail.period }}</dd></div>
              <div><dt>地点</dt><dd>{{ detail.place }}</dd></div>
              <div><dt>对象</dt><dd>{{ detail.audience }}</dd></div>
              <div><dt>发布</dt><dd>{{ detail.date }}</dd></div>
            </dl>
            <p class="dlg__desc">{{ detail.body }}</p>
            <ul class="dlg__hl">
              <li v-for="h in detail.highlights" :key="h">{{ h }}</li>
            </ul>
            <div class="dlg__foot">
              <RouterLink class="btn-gold" to="/qa" @click="detail = null">向书院咨询</RouterLink>
              <button class="btn-outline" @click="detail = null">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.act { background: var(--bg); }

/* Hero */
.act__hero { position: relative; background-size: cover; background-position: center; background-color: var(--navy-deep); }
.act__shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15, 23, 33, 0.5), rgba(15, 23, 33, 0.82)); }
.act__heroIn { position: relative; z-index: 1; padding: 84px 0 64px; color: #fff; }
.act__heroIn .eyebrow { color: var(--gold); }
.act__heroIn h1 { margin: 14px 0 0; font-size: clamp(28px, 4.2vw, 46px); font-weight: 800; }
.act__lead { margin: 18px 0 0; max-width: 620px; color: rgba(255, 255, 255, 0.82); font-size: 15.5px; line-height: 1.9; }

/* 列表区 */
.act__body { padding: 56px 0 24px; }
.act__head { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; justify-content: space-between; margin-bottom: 28px; }
.act__head h2 { margin-top: 6px; font-size: clamp(22px, 2.8vw, 30px); font-weight: 800; color: var(--ink); }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.tab {
  padding: 7px 16px; border-radius: 999px; font-size: 14px; font-weight: 600;
  background: var(--panel); border: 1px solid var(--line); color: var(--sub);
  transition: all 0.2s var(--ease);
}
.tab:hover { border-color: var(--navy); color: var(--navy); }
.tab--on { background: var(--navy); border-color: var(--navy); color: #fff; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px; }
.card {
  display: flex; flex-direction: column; overflow: hidden; cursor: pointer;
  border-radius: 16px; background: var(--panel); border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
  transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
}
.card:hover { transform: translateY(-6px); box-shadow: var(--shadow-lift); }
.card__media { position: relative; aspect-ratio: 16 / 10; overflow: hidden; background: var(--navy-deep); }
.card__media img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s var(--ease); }
.card:hover .card__media img { transform: scale(1.06); }
.card__cat {
  position: absolute; top: 12px; left: 12px;
  padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 700;
  background: rgba(44, 62, 80, 0.88); color: var(--gold-soft); backdrop-filter: blur(4px);
}
.card__status {
  position: absolute; top: 12px; right: 12px;
  padding: 4px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; color: #fff;
}
.card__status.is-open { background: var(--red); }
.card__status.is-ongoing { background: #2f8f5b; }
.card__status.is-closed { background: rgba(20, 30, 40, 0.55); }
.card__body { display: flex; flex-direction: column; flex: 1; padding: 20px; }
.card__body h3 { font-size: 18.5px; font-weight: 800; line-height: 1.4; color: var(--ink); }
.card__body > p { margin: 10px 0 14px; font-size: 14px; line-height: 1.7; color: var(--sub); flex: 1; }
.card__meta { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; font-size: 13px; color: var(--muted); }
.card__more { color: var(--navy); font-size: 14px; font-weight: 700; }
.card:hover .card__more { color: var(--red); }
.empty { padding: 40px 0; text-align: center; color: var(--muted); }

/* 大事记 */
.chron {
  margin-top: 40px;
  padding: 64px 0 72px;
  background:
    radial-gradient(circle at 12% 18%, rgba(237, 183, 79, 0.1), transparent 42%),
    linear-gradient(160deg, var(--navy) 0%, var(--navy-deep) 100%);
  color: #fff;
}
.eyebrow--gold { color: var(--gold); text-align: center; display: block; }
.chron__title { text-align: center; margin-top: 10px; font-size: clamp(24px, 3.2vw, 34px); font-weight: 800; }
.chron__lead { margin: 14px auto 40px; max-width: 560px; text-align: center; color: rgba(255, 255, 255, 0.74); font-size: 15px; }
.timeline { position: relative; display: flex; flex-direction: column; gap: 30px; }
.timeline::before {
  content: ''; position: absolute; top: 0; bottom: 0; left: 50%; width: 2px;
  background: linear-gradient(180deg, transparent, rgba(237, 183, 79, 0.5), transparent);
  transform: translateX(-50%);
}
.ms { position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: 32px; align-items: center; }
.ms--rev .ms__media { order: 2; }
.ms__media { border-radius: 14px; overflow: hidden; border: 2px solid rgba(237, 183, 79, 0.4); box-shadow: 0 18px 40px rgba(0, 0, 0, 0.4); }
.ms__media img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; transition: transform 0.5s var(--ease); }
.ms__media:hover img { transform: scale(1.05); }
.ms__text { padding: 0 6px; }
.ms--rev .ms__text { text-align: right; }
.ms__era {
  display: inline-block; padding: 3px 14px; border-radius: 999px;
  background: linear-gradient(135deg, var(--gold), var(--gold-deep)); color: var(--navy-deep);
  font-weight: 800; font-size: 14px;
}
.ms__text h3 { margin: 14px 0 0; font-size: 21px; font-weight: 800; color: #fff; }
.ms__text p { margin-top: 10px; color: rgba(255, 255, 255, 0.76); font-size: 14.5px; line-height: 1.85; }

/* CTA */
.act__cta {
  margin: 56px 0 72px; padding: 40px; border-radius: 20px; text-align: center;
  background:
    radial-gradient(circle at 80% 20%, rgba(237, 183, 79, 0.14), transparent 45%),
    linear-gradient(155deg, var(--navy-soft), var(--navy-deep));
  color: #fff;
}
.act__cta h3 { font-size: 23px; font-weight: 800; }
.act__cta p { margin: 12px 0 22px; color: rgba(255, 255, 255, 0.78); }
.act__btns { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; }

/* 详情弹窗 */
.dlg { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 24px; background: rgba(15, 23, 33, 0.62); backdrop-filter: blur(3px); }
.dlg__panel { position: relative; width: min(560px, 100%); max-height: 90vh; overflow: auto; border-radius: 18px; background: var(--panel); box-shadow: var(--shadow-lift); }
.dlg__close { position: absolute; top: 14px; right: 14px; z-index: 2; display: grid; place-items: center; height: 34px; width: 34px; border-radius: 50%; background: rgba(255, 255, 255, 0.92); color: var(--navy); box-shadow: var(--shadow-soft); }
.dlg__media { position: relative; aspect-ratio: 16 / 9; overflow: hidden; background: var(--navy-deep); }
.dlg__media img { width: 100%; height: 100%; object-fit: cover; }
.dlg__media .card__status { top: auto; bottom: 14px; right: 14px; }
.dlg__body { padding: 24px; }
.dlg__cat { display: inline-block; padding: 4px 12px; border-radius: 999px; background: rgba(44, 62, 80, 0.08); color: var(--navy); font-size: 12.5px; font-weight: 700; }
.dlg__body h3 { margin: 12px 0 0; font-size: 24px; font-weight: 800; color: var(--ink); }
.dlg__info { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 20px; margin: 18px 0; padding: 16px; border-radius: 12px; background: var(--bg); }
.dlg__info div { display: flex; gap: 10px; font-size: 14px; }
.dlg__info dt { flex: none; color: var(--muted); }
.dlg__info dd { color: var(--ink); font-weight: 600; }
.dlg__desc { color: var(--sub); font-size: 15px; line-height: 1.9; }
.dlg__hl { margin: 16px 0 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
.dlg__hl li { position: relative; padding-left: 22px; font-size: 14.5px; color: var(--sub); }
.dlg__hl li::before { content: '✦'; position: absolute; left: 0; color: var(--gold-deep); }
.dlg__foot { display: flex; gap: 12px; margin-top: 22px; }

@media (max-width: 760px) {
  .ms { grid-template-columns: 1fr; gap: 16px; }
  .ms--rev .ms__media { order: 0; }
  .ms--rev .ms__text { text-align: left; }
  .timeline::before { display: none; }
  .dlg__info { grid-template-columns: 1fr; }
}
</style>
