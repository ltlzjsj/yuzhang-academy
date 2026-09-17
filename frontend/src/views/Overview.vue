<script setup lang="ts">
import { RouterLink } from 'vue-router'
import JiangxiAcademyMap from '@/components/JiangxiAcademyMap.vue'

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}
// 中小图走缩略图端点，避免拉取数千像素原图。
function thumbUrl(src: string, w = 640, h = 480) {
  return '/api/v1/assets/thumb/academy/' + src.split('/').map(encodeURIComponent).join('/') + `?w=${w}&h=${h}`
}
const PHOTOS = '组织拍摄了江西遗存书院/江西四大书院'
const heroImg = assetUrl(`${PHOTOS}/白鹭洲书院/白鹭洲书院云章阁.JPG`)

const stats = [
  { num: '70+', label: '江右书院' },
  { num: '千年', label: '讲学文脉' },
  { num: '5', label: '江右名院' },
  { num: '6', label: '历代名儒' },
]

// 历史沿革（书院制度演进脉络，按朝代分段；具体史事见「活动资讯 · 十大史事」）
const eras = [
  { era: '唐', dot: '唐', title: '私学发轫', body: '江右聚徒讲学之风始兴，藏书延师、择地结庐，书院雏形渐成。' },
  { era: '两宋', dot: '宋', title: '讲学鼎盛', body: '白鹿洞订学规、鹅湖开会讲、象山立心学，江右理学蔚为大观，书院遍布州县。' },
  { era: '明清', dot: '明', title: '列入文教', body: '豫章书院设于省会南昌，渐入官学体系，成科举文教重镇，士子云集、讲诵不绝。' },
  { era: '近代', dot: '近', title: '转型赓续', body: '废科举、兴新学，书院多有改制，而崇文重教之文脉以新的形态延续不息。' },
  { era: '当代', dot: '今', title: '数智新生', body: '引入知识检索、智能问答、AI 出题与名人互动，让千年讲学传统走进当下。' },
]

// 办学传统
const traditions = [
  { icon: '📜', title: '讲会论道', body: '以讲学为本，重在明理修身、经世致用。立学规、开讲会，养成开放问难、躬行实践的为学之风。' },
  { icon: '🧠', title: '江右理学', body: '白鹿洞之规、象山之心学、阳明之良知，皆于赣鄱大地生发流布，泽被东南、影响数百年。' },
  { icon: '🏯', title: '楼阁碑亭', body: '风月楼、云章阁、正学门、古牌坊……碑刻匾额、楹联题咏俯拾即是，建筑与文化交相辉映。' },
  { icon: '🤝', title: '文章节义', body: '白鹭洲倡“文章节义”之教，培育文天祥等忠义之士，读书明理、砥砺名节之精神薪火相传。' },
]

// 江右其余四大名院
const academies = [
  { name: '白鹿洞书院', sub: '庐山 · 海内第一书院', img: thumbUrl(`${PHOTOS}/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG`) },
  { name: '白鹭洲书院', sub: '吉安 · 文章节义之邦', img: thumbUrl(`${PHOTOS}/白鹭洲书院/白鹭洲书院风月楼.JPG`) },
  { name: '鹅湖书院', sub: '铅山 · 朱陆论道之地', img: thumbUrl(`${PHOTOS}/鹅湖书院/鹅湖书院全景图.jpg`) },
  { name: '象山书院', sub: '贵溪 · 心学发祥之所', img: thumbUrl(`${PHOTOS}/象山书院/象山书院遗址全景.JPG`) },
]
</script>

<template>
  <div class="ov">
    <!-- Hero -->
    <section class="ov__hero" :style="{ backgroundImage: `url('${heroImg}')` }">
      <div class="ov__shade" />
      <div class="shell ov__heroIn">
        <p class="eyebrow">书院概况</p>
        <h1 class="h-serif">豫章故郡 · 江右理学之源</h1>
        <p class="ov__lead">
          坐落于江西南昌的豫章书院，承宋明讲学之统，育江右人文之盛。在这里，千年文脉以数智之姿，重新走向今天。
        </p>
      </div>
    </section>

    <!-- 数据 -->
    <section class="shell">
      <div class="stats">
        <div v-for="s in stats" :key="s.label" class="stat">
          <strong class="h-serif">{{ s.num }}</strong>
          <span>{{ s.label }}</span>
        </div>
      </div>
    </section>

    <!-- 简介 -->
    <section class="shell ov__about">
      <p class="eyebrow">书院简介</p>
      <h2 class="h-serif">一座书院，半部江右人文史</h2>
      <div class="ov__cols">
        <p>
          豫章书院肇启于宋，几经兴废而文脉不绝。自南宋讲学之风渐盛，历元明清三朝屡有修葺，
          名儒迭主讲席，士子负笈而来，遂为江右理学与科举教育之重镇。书院以讲学为本，
          立学规、开讲会，尊德性与道问学交相为用，养成开放问难、躬行实践的为学之风。
        </p>
        <p>
          “江右理学之源”，非虚誉也。白鹿洞之规、象山之心学、阳明之良知，皆于赣鄱大地生发流布。
          今日豫章书院引入知识检索、智能问答、AI 出题批改与历史名人互动等数智手段，
          让典籍可问、史事可询、先贤可对，以现代科技承续千年讲学。
        </p>
      </div>
    </section>

    <!-- 历史沿革（朝代脉络） -->
    <section class="shell sec chron">
      <h2 class="sec__title h-serif">历史沿革</h2>
      <p class="sec__lead">千年文脉，弦歌不辍 · 书院制度演进脉络</p>
      <ol class="steps">
        <li v-for="(e, i) in eras" :key="e.era" class="step">
          <div class="step__top">
            <span class="step__dot h-serif">{{ e.dot }}</span>
            <span v-if="i < eras.length - 1" class="step__line" />
          </div>
          <div class="step__body">
            <span class="step__era">{{ e.era }}</span>
            <h3 class="h-serif">{{ e.title }}</h3>
            <p>{{ e.body }}</p>
          </div>
        </li>
      </ol>
      <p class="chron__hint">
        想看「东佳书堂」「鹅湖之会」等具体史事？前往
        <RouterLink to="/activities">活动资讯 · 江西书院十大史事 →</RouterLink>
      </p>
    </section>

    <!-- 办学传统 -->
    <section class="shell sec">
      <h2 class="sec__title h-serif">办学传统</h2>
      <p class="sec__lead">讲学之道 · 书院之精神</p>
      <div class="trad">
        <article v-for="t in traditions" :key="t.title" class="trad__item">
          <span class="trad__icon">{{ t.icon }}</span>
          <h3 class="h-serif">{{ t.title }}</h3>
          <p>{{ t.body }}</p>
        </article>
      </div>
    </section>

    <!-- 江右其余四大名院 -->
    <section class="sec sec--alt">
      <div class="shell">
        <h2 class="sec__title h-serif">江右其余四大名院</h2>
        <p class="sec__lead">遗存犹在，弦歌可闻</p>
        <div class="acad">
          <article v-for="a in academies" :key="a.name" class="acard">
            <div class="acard__media"><img :src="a.img" :alt="a.name" loading="lazy" /></div>
            <div class="acard__cap">
              <h3 class="h-serif">{{ a.name }}</h3>
              <span>{{ a.sub }}</span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- 分布图 -->
    <section class="shell sec">
      <h2 class="sec__title h-serif">江西书院遗存分布</h2>
      <p class="sec__lead">书院遍布赣鄱，文教蔚然成风</p>
      <div class="mapwrap">
        <JiangxiAcademyMap />
      </div>
    </section>

    <!-- 更多探索 -->
    <section class="shell sec">
      <h2 class="sec__title h-serif">更多探索</h2>
      <p class="sec__lead">从百科、图谱到闯关，继续走进书院文化</p>
      <div class="explore">
        <RouterLink class="explore__card" to="/academies">
          <strong class="h-serif">书院百科</strong>
          <span>一院一史 · 沿革与诗文</span>
        </RouterLink>
        <RouterLink class="explore__card" to="/relations">
          <strong class="h-serif">理学图谱</strong>
          <span>人物关系 · 时间轴</span>
        </RouterLink>
        <RouterLink class="explore__card" to="/quiz">
          <strong class="h-serif">闯关答题</strong>
          <span>书院知识挑战赛</span>
        </RouterLink>
      </div>
    </section>

    <!-- CTA -->
    <section class="shell">
      <div class="ov__cta">
        <h3 class="h-serif">想更深入地了解豫章书院？</h3>
        <p>与书院先生隔空请教，或向「问书院」发问，让典籍与史事即问即答。</p>
        <div class="ov__btns">
          <RouterLink class="btn-solid" to="/figures">历史名人互动</RouterLink>
          <RouterLink class="btn-outline" to="/qa">向书院请教</RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ov { background: var(--bg); }
.sec { padding: 64px 0; }
.sec--alt { background: #fff; }
.sec__title { text-align: center; font-size: clamp(24px, 3vw, 32px); font-weight: 800; color: var(--ink); }
.sec__title::after { content: ''; display: block; width: 56px; height: 3px; margin: 14px auto 0; border-radius: 3px; background: linear-gradient(90deg, var(--gold), var(--gold-deep)); }
.sec__lead { margin: 14px 0 36px; text-align: center; color: var(--muted); font-size: 15px; }

/* Hero */
.ov__hero { position: relative; background-size: cover; background-position: center; background-color: var(--navy-deep); }
.ov__shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15, 23, 33, 0.55), rgba(15, 23, 33, 0.82)); }
.ov__heroIn { position: relative; z-index: 1; padding: 90px 0 70px; color: #fff; }
.ov__heroIn .eyebrow { color: var(--gold); }
.ov__heroIn h1 { margin: 14px 0 0; font-size: clamp(30px, 4.4vw, 50px); font-weight: 800; }
.ov__lead { margin: 20px 0 0; max-width: 640px; color: rgba(255, 255, 255, 0.82); font-size: 16px; line-height: 1.9; }

/* 数据 */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin-top: -38px; position: relative; z-index: 2; }
.stat {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 22px 12px; border-radius: 14px; text-align: center;
  background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-lift);
}
.stat strong { font-size: clamp(26px, 3.4vw, 36px); font-weight: 900; color: var(--navy); }
.stat span { font-size: 14px; font-weight: 700; color: var(--sub); }

/* 简介 */
.ov__about { padding: 60px 0 8px; text-align: center; }
.ov__about h2 { margin: 10px 0 26px; font-size: clamp(22px, 2.8vw, 30px); font-weight: 800; color: var(--ink); }
.ov__cols { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; text-align: left; }
.ov__cols p { color: var(--sub); font-size: 15.5px; line-height: 2; }

/* 历史沿革（朝代脉络 stepper，浅色横向，区别于活动页十大史事） */
.chron { padding-bottom: 56px; }
.steps { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; list-style: none; padding: 0; }
.step { display: flex; flex-direction: column; }
.step__top { position: relative; display: flex; align-items: center; height: 56px; }
.step__dot {
  position: relative; z-index: 1; flex: none;
  display: grid; place-items: center; height: 52px; width: 52px; border-radius: 50%;
  background: linear-gradient(145deg, var(--navy), var(--navy-deep)); color: var(--gold);
  font-size: 22px; font-weight: 800; box-shadow: var(--shadow-soft);
}
.step:nth-child(even) .step__dot { background: linear-gradient(145deg, var(--gold), var(--gold-deep)); color: var(--navy-deep); }
.step__line { position: absolute; left: 52px; right: 0; top: 50%; height: 3px; background: linear-gradient(90deg, var(--gold), var(--line)); }
.step__body { padding: 18px 18px 0 2px; }
.step__era { font-size: 13px; font-weight: 800; letter-spacing: 0.08em; color: var(--gold-deep); }
.step__body h3 { margin: 4px 0 0; font-size: 19px; font-weight: 800; color: var(--ink); }
.step__body p { margin-top: 8px; font-size: 14px; line-height: 1.8; color: var(--sub); padding-right: 14px; }
.chron__hint { margin-top: 36px; text-align: center; color: var(--muted); font-size: 14px; }
.chron__hint a { color: var(--navy); font-weight: 700; }
.chron__hint a:hover { color: var(--red); }

/* 办学传统 */
.trad { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.trad__item { padding: 28px 22px; border-radius: 14px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease); }
.trad__item:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.trad__icon { display: grid; place-items: center; height: 60px; width: 60px; margin-bottom: 14px; border-radius: 14px; background: radial-gradient(circle at 30% 30%, rgba(237, 183, 79, 0.26), rgba(44, 62, 80, 0.08)); font-size: 28px; }
.trad__item h3 { font-size: 19px; font-weight: 800; color: var(--ink); }
.trad__item p { margin-top: 10px; font-size: 14px; line-height: 1.8; color: var(--sub); }

/* 四大书院 */
.acad { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.acard { border-radius: 16px; overflow: hidden; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease); }
.acard:hover { transform: translateY(-6px); box-shadow: var(--shadow-lift); }
.acard__media { aspect-ratio: 4 / 3; overflow: hidden; background: var(--navy-deep); }
.acard__media img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s var(--ease); }
.acard:hover .acard__media img { transform: scale(1.06); }
.acard__cap { padding: 16px 18px; }
.acard__cap h3 { font-size: 18px; font-weight: 800; color: var(--ink); }
.acard__cap span { font-size: 13px; color: var(--muted); }

/* 分布图 */
.mapwrap { isolation: isolate; border-radius: 16px; overflow: hidden; border: 1px solid var(--line); box-shadow: var(--shadow-soft); background: #fff; }

/* 更多探索 */
.explore { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.explore__card { display: flex; flex-direction: column; gap: 6px; padding: 26px 22px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); text-decoration: none; transition: transform .25s var(--ease), box-shadow .25s var(--ease); }
.explore__card:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.explore__card strong { font-size: 22px; font-weight: 800; color: var(--ink); }
.explore__card span { font-size: 13.5px; color: var(--sub); }
@media (max-width: 760px) {
  .explore { grid-template-columns: 1fr; }
}

/* CTA */
.ov__cta {
  margin: 24px 0 72px; padding: 40px; border-radius: 20px; text-align: center;
  background: radial-gradient(circle at 20% 20%, rgba(237, 183, 79, 0.14), transparent 45%), linear-gradient(155deg, var(--navy), var(--navy-deep));
  color: #fff;
}
.ov__cta h3 { font-size: 24px; font-weight: 800; }
.ov__cta p { margin: 12px 0 22px; color: rgba(255, 255, 255, 0.78); }
.ov__btns { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; }

@media (max-width: 1080px) {
  .trad, .acad { grid-template-columns: repeat(2, 1fr); }
  .steps { grid-template-columns: 1fr 1fr 1fr; gap: 24px 0; }
  .step:nth-child(3n) .step__line { display: none; }
}
@media (max-width: 760px) {
  .stats { grid-template-columns: repeat(2, 1fr); margin-top: 24px; }
  .ov__cols { grid-template-columns: 1fr; gap: 16px; }
  /* 沿革脉络改为纵向：圆点在左，文字在右 */
  .steps { grid-template-columns: 1fr; gap: 0; }
  .step { flex-direction: row; gap: 16px; }
  .step__top { height: auto; flex-direction: column; align-self: stretch; width: 52px; }
  .step__line { left: 50%; right: auto; top: 52px; bottom: 0; width: 3px; height: auto; transform: translateX(-50%); background: linear-gradient(180deg, var(--gold), var(--line)); }
  .step__body { padding: 0 0 26px; }
}
@media (max-width: 520px) {
  .trad, .acad { grid-template-columns: 1fr; }
}
</style>
