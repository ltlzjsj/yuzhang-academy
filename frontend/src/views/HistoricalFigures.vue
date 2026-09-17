<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SectionHeading from '@/components/ui/SectionHeading.vue'
import { listFigures, type HistoricalFigure } from '@/api/figures'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const figures = ref<HistoricalFigure[]>([])
const activeId = ref<string>('')
const loading = ref(true)
const error = ref('')

const active = computed(() => figures.value.find((f) => f.id === activeId.value) ?? null)
const ASSET_V = 'v=13'

function thumb(url: string | null, w = 320, h = 400): string | null {
  if (!url || !url.includes('/assets/academy/')) return url
  return url.replace('/assets/academy/', '/assets/thumb/academy/') + `?w=${w}&h=${h}`
}

function withAssetVersion(url: string | null): string | null {
  if (!url || !url.includes('/assets/academy/')) return url
  return `${url}${url.includes('?') ? '&' : '?'}${ASSET_V}`
}

function isPortrait(url: string | null): boolean {
  return !!url && url.includes('/assets/academy/') && url.split('?')[0].toLowerCase().endsWith('.png')
}

function figureImage(url: string | null, w = 320, h = 400): string | null {
  if (!url) return null
  if (isPortrait(url)) return withAssetVersion(url)
  return withAssetVersion(thumb(url, w, h))
}

function select(id: string) {
  activeId.value = id
  // 平滑滚动到详情区
  requestAnimationFrame(() => {
    document.getElementById('figure-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function startChat(id: string) {
  // 进入独立对话页（左立绘 + 右对话）；未登录由路由守卫跳登录。
  if (!auth.token) {
    router.push({ path: '/login', query: { redirect: `/figures/${id}` } })
    return
  }
  router.push(`/figures/${id}`)
}

onMounted(async () => {
  try {
    figures.value = await listFigures()
    activeId.value = figures.value[0]?.id ?? ''
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="fig">
    <div class="fig__hero">
      <div class="shell">
        <SectionHeading
          eyebrow="历史名人互动"
          title="与书院先生隔空对谈"
          subtitle="先览先生立绘与生平，再请其讲学论道——以第一人称的口吻，回答你关于书院与治学的提问。"
        />
      </div>
    </div>

    <div class="shell fig__body">
      <p v-if="loading" class="fig__hint">正在恭请诸位先生…</p>
      <p v-else-if="error" class="fig__hint fig__hint--err">{{ error }}</p>

      <template v-else>
        <!-- 立绘画廊 -->
        <div class="gallery">
          <button
            v-for="f in figures"
            :key="f.id"
            class="gcard"
            :class="{ 'is-active': f.id === activeId }"
            :style="{ '--ac': f.accent }"
            @click="select(f.id)"
          >
            <span class="gcard__img">
              <img v-if="f.image_url" :src="figureImage(f.image_url, 220, 220)!" :alt="f.name" loading="lazy" />
              <span v-else class="gcard__seal h-serif">{{ f.name.slice(0, 1) }}</span>
            </span>
            <span class="gcard__name h-serif">{{ f.name }}</span>
            <span class="gcard__sub">{{ f.dynasty }} · {{ f.academy }}</span>
          </button>
          <div class="gcard gcard--more" aria-label="更多历史名人陆续开放">
            <span class="gcard__moreIcon h-serif">+</span>
            <span class="gcard__name h-serif">更多名人</span>
            <span class="gcard__sub">陆续开放中</span>
          </div>
        </div>

        <!-- 详情：立绘 + 介绍 → 点击进入独立对话页 -->
        <section v-if="active" id="figure-detail" class="detail" :style="{ '--ac': active.accent }">
          <div class="profile">
            <div class="profile__portrait">
              <img v-if="active.image_url" :src="figureImage(active.image_url, 480, 600)!" :alt="active.name" />
              <span v-else class="h-serif">{{ active.name.slice(0, 1) }}</span>
            </div>
            <div class="profile__info">
              <p class="profile__dyn">{{ active.dynasty }} · {{ active.academy }}</p>
              <h2 class="h-serif">{{ active.name }}</h2>
              <p class="profile__title">{{ active.title }}</p>
              <blockquote v-if="active.quote" class="profile__quote">「{{ active.quote }}」</blockquote>
              <p class="profile__bio">{{ active.bio }}</p>
              <div class="profile__chips">
                <span class="profile__chipsLbl">可问：</span>
                <span v-for="q in active.suggestions" :key="q" class="profile__chip">{{ q }}</span>
              </div>
              <button class="btn-solid profile__start" @click="startChat(active.id)">请先生讲学 · 开始对话</button>
              <p v-if="!auth.token" class="profile__login">对话需先登录</p>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.fig { background: var(--bg); }
.fig__hero {
  padding: 48px 0 8px;
  background: radial-gradient(circle at 90% 10%, rgba(237, 183, 79, 0.1), transparent 45%), var(--bg);
}
.fig__body { padding: 28px 0 72px; }
.fig__hint { padding: 60px 0; text-align: center; color: var(--muted); }
.fig__hint--err { color: var(--red); }

/* 画廊 */
.gallery {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}
.gcard {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 10px 16px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
  transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease), border-color 0.2s var(--ease);
}
.gcard:hover { transform: translateY(-5px); box-shadow: var(--shadow-lift); }
.gcard.is-active { border-color: var(--ac); box-shadow: 0 0 0 2px var(--ac), var(--shadow-soft); }
.gcard--more {
  justify-content: center;
  min-height: 164px;
  border-style: dashed;
  border-color: color-mix(in srgb, var(--gold) 50%, var(--line));
  background:
    radial-gradient(circle at 50% 24%, rgba(237, 183, 79, 0.12), transparent 44%),
    color-mix(in srgb, var(--panel) 88%, var(--bg));
  color: var(--muted);
  cursor: default;
  box-shadow: none;
}
.gcard--more:hover { transform: none; box-shadow: none; }
.gcard__moreIcon {
  display: grid;
  place-items: center;
  height: 58px;
  width: 58px;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--gold) 54%, var(--line));
  background: rgba(255, 255, 255, 0.56);
  color: var(--gold);
  font-size: 34px;
  font-weight: 500;
}
.gcard--more .gcard__name { color: var(--ink); }
.gcard__img {
  height: 96px;
  width: 96px;
  border-radius: 14px;
  overflow: visible;
  display: grid;
  place-items: end center;
  background:
    radial-gradient(ellipse at center bottom, rgba(20, 30, 40, 0.22), transparent 54%),
    color-mix(in srgb, var(--ac) 14%, white);
}
.gcard__img img {
  max-height: 118px;
  max-width: 112px;
  object-fit: contain;
  transform: translateY(-10px);
  filter:
    drop-shadow(1px 0 0 rgba(255, 255, 255, 0.92))
    drop-shadow(-1px 0 0 rgba(255, 255, 255, 0.92))
    drop-shadow(0 1px 0 rgba(255, 255, 255, 0.88))
    drop-shadow(0 -1px 0 rgba(255, 255, 255, 0.88))
    drop-shadow(0 12px 10px rgba(20, 30, 40, 0.22));
}
.gcard__seal { font-size: 40px; font-weight: 800; color: var(--ac); }
.gcard__name { margin-top: 18px; font-size: 17px; font-weight: 800; color: var(--ink); }
.gcard__sub { margin-top: 3px; font-size: 11.5px; color: var(--muted); text-align: center; }

/* 详情 */
.detail { margin-top: 28px; }
.profile {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 36px;
  padding: 32px;
  border-radius: 20px;
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-soft);
}
.profile__portrait {
  border-radius: 16px;
  overflow: visible;
  aspect-ratio: 4 / 5;
  display: grid;
  place-items: end center;
  background: linear-gradient(155deg, color-mix(in srgb, var(--ac) 22%, white), #fff);
  border: 3px solid color-mix(in srgb, var(--ac) 40%, white);
  font-size: 96px;
  font-weight: 800;
  color: var(--ac);
}
.profile__portrait img {
  max-height: 108%;
  max-width: 112%;
  object-fit: contain;
  filter:
    drop-shadow(1.5px 0 0 rgba(255, 255, 255, 0.95))
    drop-shadow(-1.5px 0 0 rgba(255, 255, 255, 0.95))
    drop-shadow(0 1.5px 0 rgba(255, 255, 255, 0.92))
    drop-shadow(0 -1.5px 0 rgba(255, 255, 255, 0.92))
    drop-shadow(0 22px 20px rgba(20, 30, 40, 0.28));
}
.profile__dyn { color: var(--ac); font-size: 14px; font-weight: 700; letter-spacing: 0.06em; }
.profile__info h2 { margin: 6px 0; font-size: 38px; font-weight: 800; color: var(--ink); }
.profile__title { color: var(--sub); font-size: 16px; }
.profile__quote {
  margin: 18px 0;
  padding: 12px 18px;
  border-left: 3px solid var(--ac);
  background: color-mix(in srgb, var(--ac) 6%, var(--bg));
  border-radius: 0 10px 10px 0;
  font-family: var(--font-serif);
  font-size: 18px;
  color: var(--ink);
}
.profile__bio { color: var(--sub); font-size: 15.5px; line-height: 1.95; }
.profile__chips { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 18px 0 22px; }
.profile__chipsLbl { color: var(--muted); font-size: 13px; }
.profile__chip {
  padding: 6px 13px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--ac) 10%, var(--bg));
  color: var(--ac);
  font-size: 13px;
}
.profile__start { font-size: 16px; padding: 13px 30px; }
.profile__login { margin-top: 10px; color: var(--muted); font-size: 12.5px; }

@media (max-width: 1080px) { .gallery { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 820px) {
  .profile { grid-template-columns: 1fr; gap: 22px; }
  .profile__portrait { max-width: 260px; margin: 0 auto; }
}
@media (max-width: 520px) { .gallery { grid-template-columns: repeat(2, 1fr); } }
</style>
