<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { ACADEMIES } from '@/data/academies'

const route = useRoute()
const city = computed(() => (typeof route.query.city === 'string' ? route.query.city : ''))
const list = computed(() =>
  city.value ? ACADEMIES.filter((a) => a.city === city.value) : ACADEMIES,
)
</script>

<template>
  <div class="al">
    <section class="shell al__head">
      <p class="eyebrow">书院百科</p>
      <h1 class="h-serif">江右书院 · 一院一史</h1>
      <p class="al__lead">
        {{ city ? `当前查看：${city}的书院` : '走进江西历代书院，了解沿革、名儒与诗文。' }}
      </p>
      <RouterLink v-if="city" class="al__all" to="/academies">查看全部书院</RouterLink>
    </section>

    <section class="shell al__grid">
      <RouterLink
        v-for="a in list"
        :key="a.id"
        class="al__card"
        :to="`/academies/${a.id}`"
      >
        <div class="al__media">
          <img v-if="a.image" :src="a.image" :alt="a.name" loading="lazy" />
          <span v-else class="al__seal h-serif">{{ a.name.slice(0, 1) }}</span>
        </div>
        <div class="al__body">
          <span class="al__city">{{ a.city }} · {{ a.era }}</span>
          <h2 class="h-serif">{{ a.name }}</h2>
          <p>{{ a.summary }}</p>
        </div>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped>
.al { min-height: 100vh; background: var(--bg); padding-bottom: 64px; }
.al__head { padding: 48px 0 24px; text-align: center; }
.eyebrow { color: var(--gold-deep); font-size: 13px; font-weight: 700; letter-spacing: 0.08em; }
.al__head h1 { margin: 8px 0 0; font-size: clamp(26px, 3.4vw, 40px); font-weight: 800; color: var(--ink); }
.al__lead { margin: 12px auto 0; color: var(--sub); font-size: 14.5px; }
.al__all { display: inline-block; margin-top: 10px; color: var(--navy); font-weight: 700; }
.al__grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.al__card { display: flex; flex-direction: column; overflow: hidden; border-radius: 16px; background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow-soft); text-decoration: none; transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease); }
.al__card:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.al__media { aspect-ratio: 4 / 3; display: grid; place-items: center; background: linear-gradient(155deg, rgba(44, 62, 80, 0.06), #fff); overflow: hidden; }
.al__media img { width: 100%; height: 100%; object-fit: cover; }
.al__seal { font-size: 64px; font-weight: 800; color: var(--navy); opacity: 0.35; }
.al__body { padding: 16px 18px 20px; }
.al__city { font-size: 12px; font-weight: 700; color: var(--gold-deep); }
.al__body h2 { margin: 4px 0 8px; font-size: 20px; font-weight: 800; color: var(--ink); }
.al__body p { color: var(--sub); font-size: 13.5px; line-height: 1.7; }
@media (max-width: 980px) { .al__grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .al__grid { grid-template-columns: 1fr; } }
</style>
