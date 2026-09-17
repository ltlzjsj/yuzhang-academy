<script setup lang="ts">
const timeline = [
  { year: '北宋', title: '周敦颐开理学之端', desc: '濂学兴于江右，为宋明理学导夫先路。' },
  { year: '南宋 · 淳熙二年（1175）', title: '鹅湖之会', desc: '吕祖谦邀朱熹、陆九渊会讲，论“尊德性”与“道问学”。' },
  { year: '南宋', title: '朱熹重兴白鹿洞书院', desc: '亲订《白鹿洞书院揭示》，确立为学之序与修身之要。' },
  { year: '南宋', title: '陆九渊象山讲学', desc: '倡“心即理”“发明本心”，心学自成体系。' },
  { year: '南宋', title: '白鹭洲书院兴学', desc: '庐陵“文章节义”之教兴，文天祥曾就读于此。' },
  { year: '明', title: '王阳明倡知行合一', desc: '承接陆九渊心学，以“致良知”成一代之教。' },
]
</script>

<template>
  <div class="rel">
    <section class="shell rel__head">
      <p class="eyebrow">理学图谱</p>
      <h1 class="h-serif">江右理学 · 人物与脉络</h1>
      <p class="rel__lead">从朱陆论辩到阳明心学，看江西书院与理学的传承脉络。</p>
    </section>

    <section class="shell rel__panel">
      <h2 class="rel__h">人物关系图</h2>
      <div class="rel__graph">
        <svg viewBox="0 0 760 440" role="img" aria-label="江右理学人物关系图">
          <g stroke="#c9b48a" stroke-width="1.6" fill="none">
            <line x1="400" y1="66" x2="210" y2="128" />
            <line x1="400" y1="66" x2="590" y2="128" />
            <line x1="210" y1="128" x2="590" y2="128" />
            <line x1="400" y1="66" x2="400" y2="190" />
            <line x1="400" y1="190" x2="210" y2="128" />
            <line x1="400" y1="190" x2="590" y2="128" />
            <line x1="210" y1="128" x2="196" y2="302" />
            <line x1="590" y1="128" x2="620" y2="200" />
            <line x1="590" y1="128" x2="590" y2="330" />
          </g>

          <!-- 人物节点 -->
          <g font-size="16" text-anchor="middle">
            <circle cx="210" cy="118" r="34" fill="#2c3e50" />
            <text x="210" y="124" fill="#fff">朱熹</text>
            <text x="210" y="170" fill="#6b6b6b" font-size="13">理学集大成</text>

            <circle cx="590" cy="118" r="34" fill="#356f68" />
            <text x="590" y="124" fill="#fff">陆九渊</text>
            <text x="590" y="170" fill="#6b6b6b" font-size="13">心学开山</text>

            <circle cx="400" cy="56" r="30" fill="#8c6a3e" />
            <text x="400" y="62" fill="#fff" font-size="14">吕祖谦</text>
            <text x="400" y="12" fill="#6b6b6b" font-size="13">鹅湖主盟</text>

            <circle cx="590" cy="360" r="34" fill="#6d5b86" />
            <text x="590" y="366" fill="#fff">王阳明</text>
            <text x="590" y="412" fill="#6b6b6b" font-size="13">致良知</text>
          </g>

          <!-- 事件节点 -->
          <g font-size="14" text-anchor="middle">
            <rect x="330" y="180" width="140" height="42" rx="10" fill="#e7b84f" />
            <text x="400" y="205" fill="#2c3e50" font-weight="700">鹅湖之会</text>

            <rect x="120" y="292" width="160" height="42" rx="10" fill="#f1e7cf" />
            <text x="200" y="318" fill="#2c3e50">白鹿洞书院</text>

            <rect x="620" y="200" width="150" height="42" rx="10" fill="#f1e7cf" />
            <text x="695" y="226" fill="#2c3e50">象山书院</text>
          </g>

          <g font-size="12" fill="#8a5a2b">
            <text x="405" y="46">东南三贤</text>
            <text x="305" y="150">论辩</text>
            <text x="405" y="165">主盟</text>
            <text x="168" y="235">订学规</text>
            <text x="620" y="190">讲学</text>
            <text x="605" y="245">心学传承</text>
          </g>
        </svg>
      </div>
    </section>

    <section class="shell rel__panel">
      <h2 class="rel__h">理学时间轴</h2>
      <ol class="rel__timeline">
        <li v-for="t in timeline" :key="t.title" class="rel__item">
          <span class="rel__dot" />
          <div>
            <span class="rel__year">{{ t.year }}</span>
            <h3 class="h-serif">{{ t.title }}</h3>
            <p>{{ t.desc }}</p>
          </div>
        </li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.rel { min-height: 100vh; background: var(--bg); padding-bottom: 64px; }
.rel__head { padding: 48px 0 24px; text-align: center; }
.eyebrow { color: var(--gold-deep); font-size: 13px; font-weight: 700; letter-spacing: .08em; }
.rel__head h1 { margin: 8px 0 0; font-size: clamp(26px, 3.4vw, 40px); font-weight: 800; color: var(--ink); }
.rel__lead { margin: 12px auto 0; color: var(--sub); font-size: 14.5px; }
.rel__panel { margin-bottom: 24px; padding: 24px; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); }
.rel__h { font-size: 20px; font-weight: 800; color: var(--ink); }
.rel__graph { margin-top: 16px; }
.rel__graph svg { width: 100%; height: auto; display: block; }
.rel__timeline { list-style: none; padding: 0; margin: 18px 0 0; }
.rel__item { position: relative; display: flex; gap: 16px; padding: 0 0 24px 10px; }
.rel__item::before { content: ''; position: absolute; left: 7px; top: 16px; bottom: 0; width: 2px; background: var(--line); }
.rel__item:last-child::before { display: none; }
.rel__dot { flex: none; width: 12px; height: 12px; margin-top: 4px; border-radius: 50%; background: var(--gold); }
.rel__year { color: var(--gold-deep); font-size: 13px; font-weight: 700; }
.rel__item h3 { margin: 4px 0; font-size: 18px; font-weight: 800; color: var(--ink); }
.rel__item p { color: var(--sub); font-size: 14px; line-height: 1.7; }
</style>
