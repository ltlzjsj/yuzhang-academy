<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import HeroCarousel, { type HeroSlide } from '@/components/ui/HeroCarousel.vue'
import AgentChat from '@/components/agent/AgentChat.vue'
import { listKBs, type KnowledgeBase } from '@/api/kb'
import { listFigures, type HistoricalFigure } from '@/api/figures'
import { listActivities, type Activity } from '@/api/activities'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const kbs = ref<KnowledgeBase[]>([])
const figures = ref<HistoricalFigure[]>([])
const activities = ref<Activity[]>([])
const guideOpen = ref(false)
const guideMounted = ref(false)
const agentRef = ref<InstanceType<typeof AgentChat> | null>(null)
const kbIds = computed(() => kbs.value.map((k) => k.id))

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}
// 大图走缩略图端点，避免首页拉取数千像素原图。
function thumb(url: string | null, w = 320, h = 320): string | null {
  if (!url || !url.includes('/assets/academy/')) return url
  return url.replace('/assets/academy/', '/assets/thumb/academy/') + `?w=${w}&h=${h}`
}
const PHOTOS = '组织拍摄了江西遗存书院/江西四大书院'
const PAINT = '组织画家绘制了十大书院事件图'

const slides: HeroSlide[] = [
  {
    image: assetUrl(`${PHOTOS}/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG`),
    eyebrow: '豫章故郡 · 江右理学之源',
    title: '千年书院\n弦歌不辍',
    subtitle: '承宋明讲学之统，育江右人文之盛。今以数智之姿，让典籍可问、先贤可对、史事可询。',
    primary: { label: '走进书院概况', to: '/overview' },
    ghost: { label: '与先生对谈', to: '/figures' },
  },
  {
    image: assetUrl(`${PHOTOS}/鹅湖书院/鹅湖书院全景图.jpg`),
    eyebrow: '鹅湖之会 · 朱陆论道',
    title: '讲会论道\n兼容并蓄',
    subtitle: '尊德性与道问学交相为用，开放问难、躬行实践——书院之风，于今犹存。',
    primary: { label: '向书院请教', to: '/qa' },
    ghost: { label: '答题自测', to: '/training' },
  },
  {
    image: assetUrl(`${PHOTOS}/白鹭洲书院/白鹭洲书院风月楼.JPG`),
    eyebrow: '文章节义 · 白鹭遗风',
    title: '数智书院\n古韵新生',
    subtitle: '智能问答、历史名人互动、AI 出题批改——以现代科技承续千年讲学，让文化走近当下。',
    primary: { label: '历史名人互动', to: '/figures' },
    ghost: { label: '了解活动资讯', to: '/activities' },
  },
]

const stats = [
  { num: '70+', label: '江右书院', sub: '遍布赣鄱大地' },
  { num: '千年', label: '弦歌文脉', sub: '宋明迄今不绝' },
  { num: '6', label: '历代名儒', sub: '可隔空对谈' },
  { num: '10', label: '书院史事', sub: '画卷述千年' },
]

interface Feat { icon: string; title: string; desc: string; to: string }
const features: Feat[] = [
  { icon: '📖', title: '问书院', desc: '典籍人物即问即答，回答尽附出处，像有一位先生在旁随时解惑。', to: '/qa' },
  { icon: '🎓', title: '历史名人互动', desc: '与朱熹、陆九渊、王阳明诸先生隔空对谈，沉浸聆听书院讲学。', to: '/figures' },
  { icon: '📝', title: '答题自测', desc: '由书院资料自动出卷，作答后即得评分与点评，温故而知新。', to: '/training' },
  { icon: '🏛️', title: '书院概况', desc: '一览豫章书院的沿革、讲学传统与江右理学的源流脉络。', to: '/overview' },
]

const STATUS_LABEL: Record<string, string> = { open: '报名中', ongoing: '进行中', closed: '已结束' }
const newsFallback: Activity[] = [
  { id: -1, category: '书院公告', title: '豫章书院数智化项目正式启动', summary: '引入知识检索、AI 导览与数字档案系统，开放在线问书院。', body: '', event_date: '2026-04-01', period: '长期开放', place: '线上', audience: '', status: 'ongoing', highlights: [], image: '', image_url: null, is_published: true, sort_order: 0, created_at: '', updated_at: '' },
  { id: -2, category: '讲会论道', title: '传统文化讲座系列 · 江右理学专题', summary: '邀学者分享儒学经典、书院礼仪与江右文化传承。', body: '', event_date: '2026-03-28', period: '每周六', place: '明伦堂', audience: '', status: 'open', highlights: [], image: '', image_url: null, is_published: true, sort_order: 0, created_at: '', updated_at: '' },
  { id: -3, category: '研学体验', title: '春季研学营 · 走读江右四大书院', summary: '书院探访、古籍阅读、礼仪体验与主题讨论。', body: '', event_date: '2026-03-25', period: '4 月', place: '南昌等地', audience: '', status: 'open', highlights: [], image: '', image_url: null, is_published: true, sort_order: 0, created_at: '', updated_at: '' },
]
const news = computed(() => (activities.value.length ? activities.value : newsFallback).slice(0, 3))

const guidePrompt = `你是"豫章书院数字导览先生"，一位亲切的书院讲学先生。任务是帮助访客了解豫章书院与江西书院文化、研学路线、数字资源与本网站使用方法。
要求：
1. 语言亲切典雅，适合学生、教师与游客。
2. 优先结合知识库内容回答；不确定时说明"资料中未明确记载"。
3. 可推荐用户前往：问书院、历史名人互动、答题培训或书院概况页面。
4. 不要编造开放时间、票价、电话等实时信息，也不要暴露你是 AI 模型。`
// 透明底立绘（PNG，保留 alpha，不走会转 JPEG 的缩略图端点）。
// ?v= 用于在替换图片后绕过资源接口的一周强缓存；换图后把版本号 +1 即可。
const ASSET_V = '?v=9'
const guideCutout = assetUrl('历史名人立绘/guide.png') + ASSET_V
const guideFace = assetUrl('历史名人立绘/guide_face.png') + ASSET_V

function openGuide() {
  if (!auth.token) {
    router.push({ path: '/login', query: { redirect: '/' } })
    return
  }
  guideMounted.value = true
  guideOpen.value = true
}
function newChat() {
  agentRef.value?.reset()
}

onMounted(async () => {
  try {
    figures.value = await listFigures()
  } catch {
    figures.value = []
  }
  try {
    activities.value = await listActivities()
  } catch {
    activities.value = []
  }
  if (!auth.token) return
  try {
    kbs.value = await listKBs()
  } catch {
    kbs.value = []
  }
})
</script>

<template>
  <div class="home">
    <HeroCarousel :slides="slides" />

    <!-- 书院简介 + 数据 -->
    <section class="intro">
      <div class="shell intro__inner">
        <div class="intro__text">
          <p class="eyebrow">豫章故郡 · 江右理学之源</p>
          <h2 class="h-serif">一座书院，半部江右人文史</h2>
          <p>
            豫章书院坐落于江西南昌，承宋明讲学之统、育江右人文之盛。自南宋讲学之风渐盛，
            历元明清三朝屡有修葺，名儒迭主讲席，士子负笈而来，遂为江右理学与科举教育之重镇。
          </p>
          <p>
            今日豫章书院引入知识检索、智能问答、AI 出题批改与历史名人互动等数智手段，
            让典籍可问、史事可询、先贤可对——以现代科技承续千年讲学，使文化遗产走近当下。
          </p>
          <div class="intro__btns">
            <RouterLink class="btn-navy" to="/overview">了解书院概况</RouterLink>
            <RouterLink class="btn-outline" to="/about">关于我们</RouterLink>
          </div>
        </div>
        <div class="stats">
          <div v-for="s in stats" :key="s.label" class="stat">
            <strong class="h-serif">{{ s.num }}</strong>
            <span class="stat__lbl">{{ s.label }}</span>
            <small>{{ s.sub }}</small>
          </div>
        </div>
      </div>
    </section>

    <!-- 数智书院体验 -->
    <section id="features" class="sec sec--alt">
      <div class="shell">
        <h2 class="sec__title h-serif">数智书院体验</h2>
        <p class="sec__lead">让千年书院，成为可问、可学、可对话的当下</p>
        <div class="feats">
          <RouterLink v-for="f in features" :key="f.title" class="feat" :to="f.to">
            <span class="feat__icon">{{ f.icon }}</span>
            <h3 class="h-serif">{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
            <span class="feat__more">前往 →</span>
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- 历代名儒 -->
    <section v-if="figures.length" class="sec">
      <div class="shell">
        <h2 class="sec__title h-serif">历代名儒</h2>
        <p class="sec__lead">先览先生立绘与生平，再请其讲学论道</p>
        <div class="figs">
          <RouterLink v-for="f in figures.slice(0, 6)" :key="f.id" class="fig" to="/figures">
            <span class="fig__img" :style="{ '--ac': f.accent }">
              <img v-if="f.image_url" :src="thumb(f.image_url, 260, 320)!" :alt="f.name" loading="lazy" />
              <span v-else class="fig__seal h-serif">{{ f.name.slice(0, 1) }}</span>
            </span>
            <span class="fig__name h-serif">{{ f.name }}</span>
            <span class="fig__sub">{{ f.dynasty }} · {{ f.academy }}</span>
          </RouterLink>
        </div>
        <div class="sec__foot">
          <RouterLink class="btn-outline" to="/figures">认识全部先生 →</RouterLink>
        </div>
      </div>
    </section>

    <!-- 数智导览 / 数字人 -->
    <section class="digital">
      <div class="shell digital__inner">
        <div class="digital__figure">
          <span class="digital__halo" />
          <img :src="guideCutout" alt="数字书院先生" />
          <span class="digital__badge">数字书院先生</span>
        </div>
        <div class="digital__text">
          <p class="eyebrow">数智导览 · 在线讲学</p>
          <h2 class="h-serif">请位书院先生，为你讲学引路</h2>
          <p class="digital__desc">
            他熟知豫章书院的沿革典故，也通晓本站的每一处功能。想了解某座书院、规划一次研学，
            或不知从何入手，问他便是。
          </p>
          <div class="digital__actions">
            <button class="btn-gold" @click="openGuide">与书院先生对话</button>
            <RouterLink class="btn-ghost-light" to="/figures">认识历代名儒</RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- 书院动态 -->
    <section id="news" class="sec sec--alt">
      <div class="shell">
        <h2 class="sec__title h-serif">书院动态</h2>
        <p class="sec__lead">讲会 · 研学 · 文化资讯</p>
        <div class="news">
          <RouterLink v-for="n in news" :key="n.id" to="/activities" class="news__item">
            <span class="news__tag" :class="`is-${n.status}`">{{ STATUS_LABEL[n.status] || n.category }}</span>
            <h3>{{ n.title }}</h3>
            <p>{{ n.summary }}</p>
            <small>{{ n.event_date }}</small>
          </RouterLink>
        </div>
        <div class="sec__foot">
          <RouterLink class="btn-outline" to="/activities">查看全部活动资讯 →</RouterLink>
        </div>
      </div>
    </section>

    <!-- 浮动入口：导览先生立绘 -->
    <button class="fab" :class="{ 'is-hidden': guideOpen }" aria-label="数字导览先生" @click="openGuide">
      <span class="fab__ring" />
      <span class="fab__glow" />
      <img class="fab__fig" :src="guideCutout" alt="数字导览先生" />
      <span class="fab__shadow" />
      <span class="fab__tip">问问导览先生</span>
    </button>

    <!-- 导览弹窗：常挂载 + v-show，关闭后会话仍保留 -->
    <Teleport to="body">
      <div v-if="guideMounted" v-show="guideOpen" class="modal" @click.self="guideOpen = false">
        <div class="modal__panel">
          <div class="modal__bar">
            <button class="modal__act" @click="newChat">新对话</button>
            <button class="modal__close" @click="guideOpen = false">✕</button>
          </div>
          <AgentChat
            ref="agentRef"
            title="豫章书院 · 数字导览先生"
            subtitle="问问书院文化、研学路线，或网站怎么用。"
            :avatar="guideFace"
            accent="#2c3e50"
            :system-prompt="guidePrompt"
            :kb-ids="kbIds"
            :suggestions="['适合中学生的研学路线？', '白鹿洞书院有什么看点？', '这个网站能帮我做什么？']"
            placeholder="问问导览先生…"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.home { background: var(--bg); }
.sec { padding: 72px 0; }
.sec--alt { background: #fff; }
.sec__title { text-align: center; font-size: clamp(26px, 3.4vw, 34px); font-weight: 800; color: var(--ink); }
.sec__title::after {
  content: '';
  display: block;
  width: 56px;
  height: 3px;
  margin: 14px auto 0;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--gold), var(--gold-deep));
}
.sec__lead { margin: 14px 0 36px; text-align: center; color: var(--muted); font-size: 15px; }
.sec__foot { margin-top: 36px; text-align: center; }

/* 简介 + 数据 */
.intro { padding: 72px 0; }
.intro__inner { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 56px; align-items: center; }
.intro__text h2 { margin: 12px 0 18px; font-size: clamp(24px, 3vw, 32px); font-weight: 800; color: var(--ink); }
.intro__text p { margin-bottom: 14px; color: var(--sub); font-size: 15.5px; line-height: 1.95; }
.intro__btns { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 24px; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.stat {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 26px 16px; border-radius: 16px; text-align: center;
  background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft);
  transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
}
.stat:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.stat strong { font-size: clamp(30px, 4vw, 42px); font-weight: 900; color: var(--navy); line-height: 1; }
.stat__lbl { margin-top: 8px; font-size: 15px; font-weight: 800; color: var(--ink); }
.stat small { margin-top: 3px; font-size: 12px; color: var(--muted); }

/* 体验卡 */
.feats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.feat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 22px;
  border-radius: 14px;
  background: var(--bg);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
  text-decoration: none;
  transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
}
.feat:hover { transform: translateY(-6px); box-shadow: var(--shadow-lift); }
.feat__icon {
  display: grid;
  place-items: center;
  height: 76px;
  width: 76px;
  margin-bottom: 16px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, rgba(237, 183, 79, 0.28), rgba(44, 62, 80, 0.08));
  font-size: 34px;
}
.feat h3 { font-size: 20px; font-weight: 800; color: var(--ink); }
.feat p { margin: 10px 0 16px; font-size: 14px; line-height: 1.7; color: var(--sub); flex-grow: 1; }
.feat__more { color: var(--navy); font-size: 14px; font-weight: 700; }
.feat:hover .feat__more { color: var(--red); }

/* 历代名儒 */
.figs { display: grid; grid-template-columns: repeat(6, 1fr); gap: 18px; }
.fig {
  display: flex; flex-direction: column; align-items: center; text-decoration: none;
  padding: 16px 10px; border-radius: 16px; background: var(--panel);
  border: 1px solid var(--line); box-shadow: var(--shadow-soft);
  transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease);
}
.fig:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.fig__img {
  height: 110px; width: 110px; border-radius: 14px; overflow: hidden;
  display: grid; place-items: center;
  background: color-mix(in srgb, var(--ac, var(--navy)) 14%, white);
}
.fig__img img { height: 100%; width: 100%; object-fit: cover; }
.fig__seal { font-size: 44px; font-weight: 800; color: var(--ac, var(--navy)); }
.fig__name { margin-top: 10px; font-size: 17px; font-weight: 800; color: var(--ink); }
.fig__sub { margin-top: 3px; font-size: 11.5px; color: var(--muted); text-align: center; }

/* 数字人 */
.digital {
  padding: 0;
  background:
    radial-gradient(circle at 15% 30%, rgba(237, 183, 79, 0.12), transparent 40%),
    linear-gradient(160deg, var(--navy) 0%, var(--navy-deep) 100%);
  color: #fff;
}
.digital__inner {
  display: grid;
  grid-template-columns: 0.85fr 1.15fr;
  gap: 48px;
  align-items: center;
  padding: 64px 0;
}
.digital__figure { position: relative; justify-self: center; width: min(340px, 80vw); }
.digital__figure img {
  position: relative;
  z-index: 1;
  width: 100%;
  filter: drop-shadow(0 20px 32px rgba(0, 0, 0, 0.5));
  animation: float 5s ease-in-out infinite;
}
.digital__halo {
  position: absolute;
  inset: -22px;
  border-radius: 28px;
  background: radial-gradient(circle, rgba(237, 183, 79, 0.35), transparent 68%);
  filter: blur(8px);
  animation: pulse 4s ease-in-out infinite;
}
.digital__badge {
  position: absolute;
  z-index: 2;
  left: 50%;
  bottom: -14px;
  transform: translateX(-50%);
  padding: 7px 18px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--gold), var(--gold-deep));
  color: var(--navy-deep);
  font-family: var(--font-serif);
  font-weight: 800;
  font-size: 14px;
  white-space: nowrap;
  box-shadow: 0 8px 20px rgba(237, 183, 79, 0.4);
}
.digital__text h2 { margin: 12px 0 0; font-size: clamp(26px, 3.4vw, 36px); font-weight: 800; }
.digital__desc { margin: 18px 0 0; max-width: 540px; color: rgba(255, 255, 255, 0.78); font-size: 15.5px; line-height: 1.9; }
.digital__actions { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 28px; }
.digital .eyebrow { color: var(--gold); }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
@keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }

/* 动态 */
.news { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; }
.news__item {
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-radius: 12px;
  background: var(--bg);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
  text-decoration: none;
  transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease);
}
.news__item:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.news__tag {
  align-self: flex-start;
  margin-bottom: 12px;
  padding: 3px 12px;
  border-radius: 999px;
  background: rgba(44, 62, 80, 0.08);
  color: var(--navy);
  font-size: 12px;
  font-weight: 700;
}
.news__tag.is-open { background: rgba(231, 76, 60, 0.12); color: var(--red-deep); }
.news__tag.is-ongoing { background: rgba(47, 143, 91, 0.14); color: #2f8f5b; }
.news__tag.is-closed { background: rgba(20, 30, 40, 0.08); color: var(--muted); }
.news__item h3 { font-size: 18px; font-weight: 700; line-height: 1.4; color: var(--ink); }
.news__item p { margin: 10px 0 14px; font-size: 14px; line-height: 1.7; color: var(--sub); flex-grow: 1; }
.news__item small { color: var(--muted); font-size: 13px; }

/* FAB + Modal */
.fab {
  position: fixed;
  right: 24px; bottom: 18px;
  z-index: 40;
  display: grid; place-items: center;
  padding: 0; background: none; border: 0; cursor: pointer;
  transition: transform 0.25s var(--ease), opacity 0.25s var(--ease);
}
.fab:hover { transform: translateY(-6px) scale(1.05); }
.fab.is-hidden { opacity: 0; pointer-events: none; }
/* 立绘背后的柔光光晕：保证深色区域上也清晰可见 */
.fab__glow {
  position: absolute;
  bottom: 14px;
  height: 168px; width: 168px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.85), rgba(255, 248, 230, 0.45) 48%, transparent 72%);
  filter: blur(3px);
}
/* 金色脉冲圈，提示可点击 */
.fab__ring {
  position: absolute;
  bottom: 18px;
  height: 156px; width: 156px;
  border-radius: 50%;
  border: 2px solid var(--gold);
  opacity: 0.5;
  animation: fabRing 2.6s ease-out infinite;
}
/* 脚下的底座接地阴影，让先生"站"在页面上 */
.fab__shadow {
  position: absolute;
  bottom: 8px; left: 50%;
  transform: translateX(-50%);
  width: 92px; height: 16px;
  border-radius: 50%;
  background: radial-gradient(ellipse, rgba(20, 30, 40, 0.4), transparent 70%);
  filter: blur(2.5px);
}
.fab__fig {
  position: relative;
  height: 188px; width: auto;
  display: block;
  /* 叠加细描边（沿透明边缘的浅色描边）+ 立体投影 */
  filter:
    drop-shadow(1px 0 0 rgba(255, 255, 255, 0.95))
    drop-shadow(-1px 0 0 rgba(255, 255, 255, 0.95))
    drop-shadow(0 1px 0 rgba(255, 255, 255, 0.9))
    drop-shadow(0 -1px 0 rgba(255, 255, 255, 0.9))
    drop-shadow(0 16px 12px rgba(20, 30, 40, 0.3));
}
.fab__tip {
  position: absolute;
  right: 100%; bottom: 64px; margin-right: 2px;
  white-space: nowrap;
  padding: 6px 13px;
  border-radius: 999px;
  background: var(--navy);
  color: #fff;
  font-size: 12.5px; font-weight: 700;
  box-shadow: var(--shadow-soft);
  opacity: 0; transform: translateX(8px);
  transition: opacity 0.2s var(--ease), transform 0.2s var(--ease);
  pointer-events: none;
}
.fab:hover .fab__tip { opacity: 1; transform: translateX(0); }
@keyframes fabRing { 0% { transform: scale(0.7); opacity: 0.55; } 100% { transform: scale(1.18); opacity: 0; } }
.modal {
  position: fixed; inset: 0;
  z-index: 60;
  display: grid; place-items: end;
  padding: 24px;
  background: rgba(15, 23, 33, 0.5);
  backdrop-filter: blur(2px);
}
.modal__panel { position: relative; width: min(440px, calc(100vw - 32px)); height: min(640px, calc(100vh - 48px)); display: flex; flex-direction: column; }
.modal__bar { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 8px; }
.modal__act {
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--navy);
  font-size: 13px;
  font-weight: 700;
  box-shadow: var(--shadow-soft);
}
.modal__panel :deep(.ac) { flex: 1; min-height: 0; }
.modal__close {
  display: grid; place-items: center;
  height: 32px; width: 32px;
  border-radius: 50%;
  background: #fff; color: var(--navy);
  font-size: 14px;
  box-shadow: var(--shadow-soft);
}

@media (max-width: 1080px) {
  .feats { grid-template-columns: repeat(2, 1fr); }
  .figs { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 980px) {
  .intro__inner { grid-template-columns: 1fr; gap: 36px; }
  .digital__inner { grid-template-columns: 1fr; gap: 40px; text-align: center; }
  .digital__desc { margin-left: auto; margin-right: auto; }
  .digital__actions { justify-content: center; }
}
@media (max-width: 560px) {
  .feats { grid-template-columns: 1fr; }
  .figs { grid-template-columns: repeat(2, 1fr); }
  .stats { grid-template-columns: 1fr 1fr; }
  .fab__tip { display: none; }
  .fab__fig { height: 138px; }
  .fab__glow, .fab__ring { height: 124px; width: 124px; }
  .fab__shadow { width: 68px; }
  .modal { place-items: stretch; padding: 0; }
  .modal__panel { width: 100%; height: 100%; }
}
</style>
