<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

export interface HeroSlide {
  image: string
  eyebrow?: string
  title: string
  subtitle?: string
  primary?: { label: string; to: string }
  ghost?: { label: string; to: string }
}

const props = withDefaults(defineProps<{ slides: HeroSlide[]; interval?: number }>(), {
  interval: 6000,
})

const active = ref(0)
let timer: number | undefined

function go(i: number) {
  active.value = (i + props.slides.length) % props.slides.length
  restart()
}
function next() { go(active.value + 1) }
function prev() { go(active.value - 1) }

function pause() {
  if (timer) { window.clearInterval(timer); timer = undefined }
}
function restart() {
  pause()
  if (props.slides.length > 1) {
    timer = window.setInterval(() => { active.value = (active.value + 1) % props.slides.length }, props.interval)
  }
}

onMounted(restart)
onBeforeUnmount(pause)
</script>

<template>
  <section class="banner" @mouseenter="pause" @mouseleave="restart">
    <!-- 背景层 -->
    <div
      v-for="(s, i) in slides"
      :key="'bg' + i"
      class="banner__bg"
      :class="{ 'is-active': i === active }"
      :style="{ backgroundImage: `url('${s.image}')` }"
    />
    <div class="banner__shade" />

    <!-- 内容层：左文右图 -->
    <div class="banner__inner shell">
      <transition name="swap" mode="out-in">
        <div :key="active" class="slide">
          <div class="slide__text">
            <p v-if="slides[active].eyebrow" class="slide__eyebrow">{{ slides[active].eyebrow }}</p>
            <h1 class="slide__title h-serif">{{ slides[active].title }}</h1>
            <p v-if="slides[active].subtitle" class="slide__sub">{{ slides[active].subtitle }}</p>
            <div class="slide__actions">
              <RouterLink v-if="slides[active].primary" class="btn-solid slide__cta" :to="slides[active].primary!.to">
                {{ slides[active].primary!.label }}
              </RouterLink>
              <RouterLink v-if="slides[active].ghost" class="btn-ghost-light" :to="slides[active].ghost!.to">
                {{ slides[active].ghost!.label }}
              </RouterLink>
            </div>
          </div>
          <div class="slide__image">
            <img :src="slides[active].image" :alt="slides[active].title" />
          </div>
        </div>
      </transition>
    </div>

    <div v-if="slides.length > 1" class="banner__dots">
      <button
        v-for="(s, i) in slides"
        :key="'d' + i"
        class="banner__dot"
        :class="{ 'is-active': i === active }"
        :aria-label="`第 ${i + 1} 张`"
        @click="go(i)"
      />
    </div>
    <button v-if="slides.length > 1" class="banner__arrow banner__arrow--l" aria-label="上一张" @click="prev">‹</button>
    <button v-if="slides.length > 1" class="banner__arrow banner__arrow--r" aria-label="下一张" @click="next">›</button>
  </section>
</template>

<style scoped>
.banner {
  position: relative;
  height: 70vh;
  min-height: 560px;
  overflow: hidden;
  background: var(--navy-deep);
}
.banner__bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0;
  transform: scale(1.06);
  transition: opacity 1s var(--ease), transform 7s linear;
}
.banner__bg.is-active { opacity: 1; transform: scale(1); }
.banner__shade {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(15, 23, 33, 0.78), rgba(15, 23, 33, 0.5));
}
.banner__inner {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  height: 100%;
}
.slide {
  display: flex;
  align-items: center;
  gap: 48px;
  width: 100%;
}
.slide__text { width: 52%; }
.slide__eyebrow {
  margin-bottom: 14px;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.16em;
  opacity: 0.85;
}
.slide__title {
  margin: 0;
  color: var(--gold);
  font-size: clamp(36px, 5vw, 64px);
  font-weight: 800;
  line-height: 1.08;
  text-shadow: 2px 4px 16px rgba(0, 0, 0, 0.7);
  white-space: pre-line;
}
.slide__sub {
  margin: 22px 0 0;
  max-width: 520px;
  color: #d8dde2;
  font-size: clamp(15px, 1.6vw, 21px);
  line-height: 1.8;
}
.slide__actions { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 32px; }
.slide__cta { padding: 14px 34px; font-size: 17px; box-shadow: 0 14px 30px rgba(231, 76, 60, 0.32); }
.slide__image { width: 48%; display: flex; justify-content: center; }
.slide__image img {
  width: 100%;
  max-width: 500px;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: 24px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
  border: 3px solid rgba(255, 255, 255, 0.12);
}

.banner__dots {
  position: absolute;
  bottom: 24px;
  left: 0; right: 0;
  z-index: 3;
  display: flex;
  justify-content: center;
  gap: 10px;
}
.banner__dot {
  height: 9px; width: 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.45);
  transition: width 0.3s var(--ease), background 0.3s var(--ease);
}
.banner__dot.is-active { width: 28px; background: var(--gold); }
.banner__arrow {
  position: absolute;
  top: 50%;
  z-index: 3;
  display: grid;
  place-items: center;
  height: 46px; width: 46px;
  transform: translateY(-50%);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 26px;
  backdrop-filter: blur(4px);
  transition: background 0.2s var(--ease);
}
.banner__arrow:hover { background: rgba(237, 183, 79, 0.85); color: var(--navy-deep); }
.banner__arrow--l { left: 18px; }
.banner__arrow--r { right: 18px; }

.swap-enter-active, .swap-leave-active { transition: opacity 0.5s var(--ease), transform 0.5s var(--ease); }
.swap-enter-from { opacity: 0; transform: translateY(16px); }
.swap-leave-to { opacity: 0; transform: translateY(-12px); }

@media (max-width: 1080px) {
  .slide { flex-direction: column; align-items: flex-start; gap: 24px; }
  .slide__text, .slide__image { width: 100%; }
  .slide__image { display: none; }
}
@media (max-width: 720px) {
  .banner__arrow { display: none; }
}
</style>
