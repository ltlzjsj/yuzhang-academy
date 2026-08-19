<script setup lang="ts">
import { RouterLink } from 'vue-router'

function assetUrl(src: string) {
  return '/api/v1/assets/academy/' + src.split('/').map(encodeURIComponent).join('/')
}
const PHOTOS = '组织拍摄了江西遗存书院/江西四大书院'
const heroImg = assetUrl(`${PHOTOS}/鹅湖书院/鹅湖书院古牌坊.JPG`)

const capabilities = [
  { icon: '📖', title: '问书院', desc: '基于书院典籍知识库的智能问答，回答尽附出处，可溯可证。' },
  { icon: '🎓', title: '历史名人互动', desc: '与朱熹、陆九渊、王阳明等先生隔空对谈，以第一人称讲学论道。' },
  { icon: '📝', title: '答题与培训', desc: '由书院资料自动出卷，客观题即时判分、主观题 AI 批阅并给出建议。' },
  { icon: '🧭', title: '数智导览', desc: '数字书院先生为访客讲解书院文化、研学路线与网站使用方法。' },
  { icon: '🗂️', title: '知识库与档案', desc: '将馆藏典籍、碑刻题咏与书院史事系统数字化，长久保存、便捷检索。' },
  { icon: '🏛️', title: '文化展示', desc: '书院概况、十大史事画卷与四大书院掠影，立体呈现江右人文。' },
]

const contacts = [
  { icon: '📍', label: '地址', value: '江西省南昌市 · 豫章书院' },
  { icon: '📞', label: '电话', value: '0791-1234 5678' },
  { icon: '✉️', label: '邮箱', value: 'info@yuzhang-shuyuan.cn' },
  { icon: '🕘', label: '开放', value: '周二至周日 9:00–17:00' },
]

const cooperations = ['学术合作与课题共建', '研学课程与基地共建', '文化交流与展览策划', '数字化保护与技术合作']
</script>

<template>
  <div class="ab">
    <!-- Hero -->
    <section class="ab__hero" :style="{ backgroundImage: `url('${heroImg}')` }">
      <div class="ab__shade" />
      <div class="shell ab__heroIn">
        <p class="eyebrow">关于我们</p>
        <h1 class="h-serif">承千年讲学，启数智新生</h1>
        <p class="ab__lead">
          豫章书院数智平台，以现代科技承续江右书院的讲学传统，让文化遗产真正走近大众、走进当下。
        </p>
      </div>
    </section>

    <!-- 关于书院 -->
    <section class="shell ab__intro">
      <div class="ab__introText">
        <p class="eyebrow">关于豫章书院</p>
        <h2 class="h-serif">江右理学之源，千年文教重镇</h2>
        <p>
          豫章书院坐落于江西南昌，承宋明讲学之统、育江右人文之盛。自南宋讲学之风渐盛，历元明清三朝屡有修葺，
          名儒迭主讲席，士子负笈而来，遂为江右理学与科举教育之重镇。白鹿洞之规、象山之心学、阳明之良知，
          皆于赣鄱大地生发流布，泽被东南、影响后世数百年。
        </p>
        <p>
          本平台依托知识检索、智能问答、AI 出题批改与历史名人互动等数智手段，将书院典籍、史事与文物系统数字化，
          打造一座“可问、可学、可对话”的数字书院，让千年讲学传统在新时代延续生长。
        </p>
        <RouterLink class="btn-navy" to="/overview">查看书院概况</RouterLink>
      </div>
      <div class="ab__quote">
        <blockquote class="h-serif">问渠那得清如许，<br />为有源头活水来。</blockquote>
        <span>—— 朱熹</span>
      </div>
    </section>

    <!-- 平台能做什么 -->
    <section class="sec sec--alt">
      <div class="shell">
        <h2 class="sec__title h-serif">数智平台能做什么</h2>
        <p class="sec__lead">六大数智能力，承续书院讲学之道</p>
        <div class="caps">
          <article v-for="c in capabilities" :key="c.title" class="cap">
            <span class="cap__icon">{{ c.icon }}</span>
            <div>
              <h3 class="h-serif">{{ c.title }}</h3>
              <p>{{ c.desc }}</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- 合作 + 联系 -->
    <section class="shell sec">
      <div class="ab__grid">
        <div class="ab__coop">
          <p class="eyebrow">合作咨询</p>
          <h2 class="h-serif">期待与你共建书院文化</h2>
          <p class="ab__coopLead">我们欢迎各界在以下方向与豫章书院展开合作，共同推动江右文化的传承与创新。</p>
          <ul class="coop">
            <li v-for="c in cooperations" :key="c">{{ c }}</li>
          </ul>
        </div>
        <div class="ab__contact">
          <div v-for="c in contacts" :key="c.label" class="contact">
            <span class="contact__icon">{{ c.icon }}</span>
            <div>
              <span class="contact__lbl">{{ c.label }}</span>
              <strong>{{ c.value }}</strong>
            </div>
          </div>
          <div class="qr">
            <div class="qr__box">QR</div>
            <span>扫码关注书院公众号</span>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="shell">
      <div class="ab__cta">
        <h3 class="h-serif">即刻走进数智豫章书院</h3>
        <p>向「问书院」发问，或与历代名儒隔空对谈，开启你的书院之旅。</p>
        <div class="ab__btns">
          <RouterLink class="btn-gold" to="/qa">向书院请教</RouterLink>
          <RouterLink class="btn-ghost-light" to="/figures">历史名人互动</RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.ab { background: var(--bg); }
.sec { padding: 64px 0; }
.sec--alt { background: #fff; }
.sec__title { text-align: center; font-size: clamp(24px, 3vw, 32px); font-weight: 800; color: var(--ink); }
.sec__title::after { content: ''; display: block; width: 56px; height: 3px; margin: 14px auto 0; border-radius: 3px; background: linear-gradient(90deg, var(--gold), var(--gold-deep)); }
.sec__lead { margin: 14px 0 36px; text-align: center; color: var(--muted); font-size: 15px; }

/* Hero */
.ab__hero { position: relative; background-size: cover; background-position: center; background-color: var(--navy-deep); }
.ab__shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15, 23, 33, 0.5), rgba(15, 23, 33, 0.82)); }
.ab__heroIn { position: relative; z-index: 1; padding: 86px 0 64px; color: #fff; }
.ab__heroIn .eyebrow { color: var(--gold); }
.ab__heroIn h1 { margin: 14px 0 0; font-size: clamp(28px, 4.2vw, 46px); font-weight: 800; }
.ab__lead { margin: 18px 0 0; max-width: 600px; color: rgba(255, 255, 255, 0.82); font-size: 15.5px; line-height: 1.9; }

/* 关于书院 */
.ab__intro { display: grid; grid-template-columns: 1.4fr 0.9fr; gap: 48px; align-items: center; padding: 64px 0; }
.ab__introText h2 { margin: 10px 0 18px; font-size: clamp(22px, 2.8vw, 30px); font-weight: 800; color: var(--ink); }
.ab__introText p { margin-bottom: 14px; color: var(--sub); font-size: 15.5px; line-height: 1.95; }
.ab__introText .btn-navy { margin-top: 10px; }
.ab__quote {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
  padding: 48px 32px; border-radius: 20px; text-align: center;
  background: radial-gradient(circle at 30% 20%, rgba(237, 183, 79, 0.16), transparent 50%), linear-gradient(155deg, var(--navy), var(--navy-deep));
  color: #fff;
}
.ab__quote blockquote { font-size: clamp(22px, 3vw, 30px); font-weight: 700; line-height: 1.7; color: var(--gold-soft); }
.ab__quote span { color: rgba(255, 255, 255, 0.7); font-size: 14px; }

/* 能力 */
.caps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.cap { display: flex; gap: 16px; padding: 24px; border-radius: 14px; background: var(--bg); border: 1px solid var(--line); box-shadow: var(--shadow-soft); transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease); }
.cap:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.cap__icon { flex: none; display: grid; place-items: center; height: 52px; width: 52px; border-radius: 12px; background: radial-gradient(circle at 30% 30%, rgba(237, 183, 79, 0.26), rgba(44, 62, 80, 0.08)); font-size: 26px; }
.cap h3 { font-size: 17px; font-weight: 800; color: var(--ink); }
.cap p { margin-top: 6px; font-size: 13.5px; line-height: 1.75; color: var(--sub); }

/* 合作 + 联系 */
.ab__grid { display: grid; grid-template-columns: 1fr 0.9fr; gap: 40px; }
.ab__coop h2 { margin: 10px 0 14px; font-size: 26px; font-weight: 800; color: var(--ink); }
.ab__coopLead { color: var(--sub); font-size: 15px; line-height: 1.9; }
.coop { margin-top: 18px; display: flex; flex-direction: column; gap: 10px; list-style: none; }
.coop li { position: relative; padding: 12px 16px 12px 40px; border-radius: 12px; background: var(--panel); border: 1px solid var(--line); font-size: 14.5px; color: var(--ink); }
.coop li::before { content: '✦'; position: absolute; left: 16px; color: var(--gold-deep); }
.ab__contact { padding: 28px; border-radius: 18px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); display: flex; flex-direction: column; gap: 16px; }
.contact { display: flex; align-items: center; gap: 14px; }
.contact__icon { flex: none; display: grid; place-items: center; height: 42px; width: 42px; border-radius: 10px; background: rgba(44, 62, 80, 0.07); font-size: 20px; }
.contact__lbl { display: block; font-size: 12.5px; color: var(--muted); }
.contact strong { font-size: 15px; color: var(--ink); }
.qr { display: flex; align-items: center; gap: 14px; margin-top: 4px; padding-top: 16px; border-top: 1px solid var(--line); }
.qr__box { display: grid; place-items: center; height: 72px; width: 72px; border-radius: 10px; background: var(--navy); color: #fff; font-weight: 800; letter-spacing: 0.1em; }
.qr span { font-size: 13.5px; color: var(--sub); }

/* CTA */
.ab__cta {
  margin: 24px 0 72px; padding: 44px; border-radius: 20px; text-align: center;
  background: radial-gradient(circle at 80% 20%, rgba(237, 183, 79, 0.16), transparent 45%), linear-gradient(155deg, var(--navy-soft), var(--navy-deep));
  color: #fff;
}
.ab__cta h3 { font-size: 24px; font-weight: 800; }
.ab__cta p { margin: 12px 0 22px; color: rgba(255, 255, 255, 0.78); }
.ab__btns { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; }

@media (max-width: 980px) {
  .ab__intro { grid-template-columns: 1fr; gap: 32px; }
  .caps { grid-template-columns: repeat(2, 1fr); }
  .ab__grid { grid-template-columns: 1fr; gap: 28px; }
}
@media (max-width: 560px) {
  .caps { grid-template-columns: 1fr; }
}
</style>
