<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const loadedUrls = new Set<string>()

const props = defineProps<{
  src: string
  fallbackSrc?: string
  alt: string
  caption?: string
  page?: number | null
}>()

const root = ref<HTMLElement | null>(null)
const activeSrc = ref(props.src)
const shouldLoad = ref(loadedUrls.has(props.src))
const loaded = ref(loadedUrls.has(props.src))
let observer: IntersectionObserver | null = null

function startLoad() {
  shouldLoad.value = true
}

function resetForSource() {
  observer?.disconnect()
  observer = null
  activeSrc.value = props.src
  shouldLoad.value = loadedUrls.has(activeSrc.value)
  loaded.value = loadedUrls.has(activeSrc.value)
  if (shouldLoad.value) return
  if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
    startLoad()
    return
  }
  if (!root.value) return
  observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      startLoad()
      observer?.disconnect()
      observer = null
    },
    { rootMargin: '720px 0px' },
  )
  observer.observe(root.value)
}

function onLoad() {
  loaded.value = true
  loadedUrls.add(activeSrc.value)
}

function onError() {
  if (props.fallbackSrc && activeSrc.value !== props.fallbackSrc) {
    activeSrc.value = props.fallbackSrc
    loaded.value = loadedUrls.has(activeSrc.value)
    shouldLoad.value = true
    return
  }
  loaded.value = true
}

onMounted(resetForSource)
onBeforeUnmount(() => observer?.disconnect())
watch(() => props.src, resetForSource)
</script>

<template>
  <figure
    ref="root"
    class="group/img w-36 cursor-zoom-in overflow-hidden rounded-lg border border-claude-border bg-white"
  >
    <div class="relative h-24 w-full bg-claude-bg">
      <div
        v-if="!loaded"
        class="absolute inset-0 animate-pulse bg-gradient-to-br from-claude-border/40 to-white"
      />
      <img
        v-if="shouldLoad"
        :src="activeSrc"
        :alt="alt"
        loading="lazy"
        decoding="async"
        fetchpriority="low"
        class="h-24 w-full object-cover transition duration-200 group-hover/img:scale-105"
        :class="loaded ? 'opacity-100' : 'opacity-0'"
        @load="onLoad"
        @error="onError"
      />
    </div>
    <figcaption
      v-if="caption || page"
      class="truncate px-1.5 py-1 text-[10px] text-claude-muted"
      :title="caption || ''"
    >
      {{ caption || `p.${page}` }}
    </figcaption>
  </figure>
</template>
