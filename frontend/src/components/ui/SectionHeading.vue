<script setup lang="ts">
withDefaults(
  defineProps<{ eyebrow?: string; title: string; subtitle?: string; align?: 'left' | 'center' }>(),
  { align: 'left' },
)
</script>

<template>
  <div class="sh" :class="`sh--${align}`">
    <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
    <h2 class="sh__title h-serif">{{ title }}</h2>
    <p v-if="subtitle" class="sh__sub">{{ subtitle }}</p>
  </div>
</template>

<style scoped>
.sh--center { text-align: center; }
.sh--center .sh__sub { margin-left: auto; margin-right: auto; }
.sh__title {
  margin: 12px 0 0;
  color: var(--ink);
  font-size: clamp(26px, 3.2vw, 38px);
  font-weight: 800;
  line-height: 1.25;
}
.sh__title::after {
  content: '';
  display: block;
  width: 52px;
  height: 3px;
  margin-top: 14px;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--gold), var(--gold-deep));
}
.sh--center .sh__title::after { margin-left: auto; margin-right: auto; }
.sh__sub {
  margin: 16px 0 0;
  max-width: 640px;
  color: var(--sub);
  font-size: 15.5px;
  line-height: 1.85;
}
</style>
