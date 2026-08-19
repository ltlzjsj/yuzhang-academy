<script setup lang="ts">
import { RouterLink } from 'vue-router'

withDefaults(
  defineProps<{
    to: string
    tag?: string
    title: string
    desc?: string
    icon?: string
    variant?: 'light' | 'dark'
  }>(),
  { variant: 'light' },
)
</script>

<template>
  <RouterLink :to="to" class="fc" :class="`fc--${variant}`">
    <span v-if="icon" class="fc__icon">{{ icon }}</span>
    <span v-if="tag" class="fc__tag">{{ tag }}</span>
    <h3 class="fc__title h-serif">{{ title }}</h3>
    <p v-if="desc" class="fc__desc">{{ desc }}</p>
    <span class="fc__more">进入 <i>→</i></span>
  </RouterLink>
</template>

<style scoped>
.fc {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 200px;
  padding: 26px 24px;
  border-radius: var(--radius-card);
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
  text-decoration: none;
  overflow: hidden;
  transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease), border-color 0.25s var(--ease);
}
.fc::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  height: 3px;
  width: 100%;
  background: linear-gradient(90deg, var(--gold), var(--gold-deep));
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s var(--ease);
}
.fc:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-lift);
  border-color: transparent;
}
.fc:hover::before { transform: scaleX(1); }
.fc__icon {
  display: grid;
  place-items: center;
  height: 50px;
  width: 50px;
  margin-bottom: 16px;
  border-radius: 13px;
  background: rgba(237, 183, 79, 0.16);
  font-size: 26px;
}
.fc__tag {
  align-self: flex-start;
  margin-bottom: 10px;
  color: var(--gold-deep);
  font-size: 11.5px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.fc__title {
  margin: 0;
  color: var(--ink);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.3;
}
.fc__desc {
  margin: 12px 0 0;
  color: var(--sub);
  font-size: 14px;
  line-height: 1.8;
}
.fc__more {
  margin-top: auto;
  padding-top: 18px;
  color: var(--navy);
  font-size: 13.5px;
  font-weight: 700;
}
.fc__more i { font-style: normal; transition: transform 0.2s var(--ease); display: inline-block; }
.fc:hover .fc__more i { transform: translateX(4px); }

/* 深色变体（藏青） */
.fc--dark {
  background: linear-gradient(155deg, var(--navy) 0%, var(--navy-deep) 100%);
  border-color: transparent;
}
.fc--dark .fc__icon { background: rgba(237, 183, 79, 0.2); }
.fc--dark .fc__title { color: #fff; }
.fc--dark .fc__desc { color: rgba(255, 255, 255, 0.72); }
.fc--dark .fc__more { color: var(--gold); }
</style>
