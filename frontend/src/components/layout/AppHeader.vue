<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const mobileOpen = ref(false)
const keyword = ref('')
const searchOpen = ref(false)
const userMenuOpen = ref(false)
const activeIdx = ref(0)
let blurTimer: number | undefined

// 公开官网导航：内容页/锚点 + 公开 AI 功能
const navItems: { label: string; to: string }[] = [
  { label: '首页', to: '/' },
  { label: '书院概况', to: '/overview' },
  { label: '书院实况', to: '/tour' },
  { label: '合影留念', to: '/photo' },
  { label: '历史名人', to: '/figures' },
  { label: '问书院', to: '/qa' },
  { label: '答题培训', to: '/training' },
  { label: '活动资讯', to: '/activities' },
  { label: '关于我们', to: '/about' },
]

type Hit = { type: 'page' | 'figure' | 'academy' | 'ask'; label: string; hint: string; to?: string; q?: string }
const ICON: Record<Hit['type'], string> = { page: '📄', figure: '🎓', academy: '🏛️', ask: '🔎' }

// 站内检索索引（静态，覆盖功能页 / 历代名人 / 四大书院）
const INDEX: Hit[] = [
  { type: 'page', label: '问书院', hint: '智能问答', to: '/qa' },
  { type: 'page', label: '历史名人', hint: '与先贤对谈', to: '/figures' },
  { type: 'page', label: '答题培训', hint: 'AI 出题自测', to: '/training' },
  { type: 'page', label: '书院概况', hint: '沿革与传统', to: '/overview' },
  { type: 'page', label: '活动资讯', hint: '讲会·研学·史事', to: '/activities' },
  { type: 'page', label: '关于我们', hint: '平台与联系', to: '/about' },
  { type: 'figure', label: '朱熹', hint: '白鹿洞 · 理学集大成', to: '/figures' },
  { type: 'figure', label: '陆九渊', hint: '象山 · 心学开山', to: '/figures' },
  { type: 'figure', label: '王阳明', hint: '致良知 · 知行合一', to: '/figures' },
  { type: 'figure', label: '江万里', hint: '白鹭洲 · 文章节义', to: '/figures' },
  { type: 'figure', label: '吕祖谦', hint: '鹅湖之会主盟', to: '/figures' },
  { type: 'academy', label: '白鹿洞书院', hint: '海内第一书院', q: '白鹿洞书院' },
  { type: 'academy', label: '白鹭洲书院', hint: '吉安 · 文章节义', q: '白鹭洲书院' },
  { type: 'academy', label: '鹅湖书院', hint: '铅山 · 朱陆论道', q: '鹅湖书院' },
  { type: 'academy', label: '象山书院', hint: '贵溪 · 心学发祥', q: '象山书院' },
]

const results = computed<Hit[]>(() => {
  const kw = keyword.value.trim()
  if (!kw) return INDEX.filter((i) => i.type === 'page')
  const matched = INDEX.filter((i) => i.label.includes(kw) || i.hint.includes(kw))
  return [{ type: 'ask', label: `在「问书院」中提问：${kw}`, hint: '智能问答', q: kw }, ...matched]
})

function openSearch() {
  searchOpen.value = true
  activeIdx.value = 0
}
function closeSearchSoon() {
  blurTimer = window.setTimeout(() => (searchOpen.value = false), 120)
}
function askRoute(q: string) {
  return { path: '/qa', query: { q, ask: Date.now().toString() } }
}
function go(hit: Hit) {
  if (blurTimer) clearTimeout(blurTimer)
  searchOpen.value = false
  mobileOpen.value = false
  keyword.value = ''
  if (hit.to) router.push(hit.to)
  else router.push(askRoute(hit.q || keyword.value.trim()))
}
function onSubmit() {
  const hit = results.value[activeIdx.value]
  if (hit) return go(hit)
  const q = keyword.value.trim()
  router.push(q ? askRoute(q) : '/qa')
  keyword.value = ''
  searchOpen.value = false
  mobileOpen.value = false
}
function move(delta: number) {
  const n = results.value.length
  if (!n) return
  activeIdx.value = (activeIdx.value + delta + n) % n
}
function logout() {
  if (!window.confirm('确定要退出当前账号吗？')) return
  auth.logout()
  userMenuOpen.value = false
  router.replace('/login')
}
</script>

<template>
  <header class="hdr">
    <div class="hdr__inner shell">
      <RouterLink to="/" class="brand" @click="mobileOpen = false">
        <span class="brand__icon">书</span>
        <span class="brand__name h-serif">豫章书院</span>
      </RouterLink>

      <nav class="nav" :class="{ 'nav--open': mobileOpen }" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav__link"
          @click="mobileOpen = false"
        >{{ item.label }}</RouterLink>
      </nav>

      <div class="hdr__right">
        <div class="search" :class="{ 'search--open': searchOpen }">
          <form class="search__form" @submit.prevent="onSubmit">
            <input
              v-model="keyword"
              type="text"
              placeholder="搜索书院、人物、功能…"
              aria-label="搜索"
              autocomplete="off"
              @focus="openSearch"
              @blur="closeSearchSoon"
              @keydown.down.prevent="move(1)"
              @keydown.up.prevent="move(-1)"
              @keydown.esc="searchOpen = false"
            />
            <button type="submit">搜索</button>
          </form>

          <div v-if="searchOpen && results.length" class="sug">
            <p class="sug__hdr">{{ keyword.trim() ? '搜索结果' : '快捷入口' }}</p>
            <button
              v-for="(r, i) in results"
              :key="r.type + r.label"
              class="sug__item"
              :class="{ 'is-active': i === activeIdx }"
              @mousedown.prevent="go(r)"
              @mouseenter="activeIdx = i"
            >
              <span class="sug__ic">{{ ICON[r.type] }}</span>
              <span class="sug__main">
                <span class="sug__label">{{ r.label }}</span>
                <span class="sug__hint">{{ r.hint }}</span>
              </span>
            </button>
          </div>
        </div>

        <RouterLink v-if="auth.isAdmin" to="/admin" class="admin-entry">管理后台</RouterLink>
        <template v-if="auth.token">
          <div class="user" @focusout="userMenuOpen = false">
            <button
              class="user__btn"
              :title="auth.user?.username ?? '用户'"
              aria-haspopup="menu"
              :aria-expanded="userMenuOpen"
              @click="userMenuOpen = !userMenuOpen"
            >
              <span class="user__avatar">{{ (auth.user?.username ?? '?').slice(0, 1).toUpperCase() }}</span>
            </button>
            <div v-if="userMenuOpen" class="user__menu" role="menu">
              <p class="user__name">{{ auth.user?.username ?? '用户' }}</p>
              <button class="user__logout" role="menuitem" @mousedown.prevent="logout">退出登录</button>
            </div>
          </div>
        </template>
        <RouterLink v-else to="/login" class="login">登录</RouterLink>

        <button class="burger" :class="{ 'is-open': mobileOpen }" aria-label="菜单" @click="mobileOpen = !mobileOpen">
          <span /><span /><span />
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.hdr {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--navy);
  box-shadow: var(--shadow-nav);
}
.hdr__inner {
  display: flex;
  align-items: center;
  gap: 18px;
  min-height: var(--header-h);
  max-width: 1400px;
}
.brand { display: flex; align-items: center; gap: 10px; flex: none; text-decoration: none; }
.brand__icon {
  display: grid;
  place-items: center;
  height: 38px;
  width: 38px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  color: #fff;
  font-weight: 700;
  font-size: 18px;
}
.brand__name {
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.04em;
  transition: color 0.25s var(--ease), transform 0.25s var(--ease);
}
.brand:hover .brand__name { color: var(--gold); transform: scale(1.04); }

.nav {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 2px;
}
.nav__link {
  padding: 8px 14px;
  border-radius: 5px;
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  white-space: nowrap;
  text-decoration: none;
  transition: background 0.25s var(--ease), color 0.25s var(--ease);
}
.nav__link:hover { background: var(--navy-soft); color: var(--gold-soft); }
.nav__link.router-link-exact-active { color: var(--gold); }

.hdr__right { display: flex; align-items: center; gap: 12px; flex: none; }

/* 搜索（combobox） */
.search { position: relative; width: 250px; }
.search__form {
  display: flex;
  align-items: center;
  padding: 3px 4px 3px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.22);
  transition: background 0.2s var(--ease), border-color 0.2s var(--ease);
}
.search--open .search__form { background: rgba(255, 255, 255, 0.24); border-color: var(--gold); }
.search__form input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #fff;
  font-size: 13.5px;
  padding: 6px 8px;
}
.search__form input::placeholder { color: rgba(255, 255, 255, 0.7); }
.search__form button {
  flex: none;
  height: 30px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.26);
  color: #fff;
  font-size: 13px;
  transition: background 0.2s var(--ease);
}
.search__form button:hover { background: var(--gold); color: var(--navy-deep); }

.sug {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: min(360px, 80vw);
  padding: 8px;
  border-radius: 14px;
  background: #fff;
  box-shadow: var(--shadow-lift);
  border: 1px solid var(--line);
  max-height: 60vh;
  overflow: auto;
}
.sug__hdr { padding: 6px 10px; font-size: 11.5px; font-weight: 700; letter-spacing: 0.08em; color: var(--muted); }
.sug__item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 9px 10px;
  border-radius: 10px;
  text-align: left;
  transition: background 0.14s var(--ease);
}
.sug__item.is-active { background: var(--bg); }
.sug__ic {
  flex: none;
  display: grid; place-items: center;
  height: 32px; width: 32px;
  border-radius: 8px;
  background: rgba(44, 62, 80, 0.07);
  font-size: 16px;
}
.sug__main { display: flex; flex-direction: column; min-width: 0; }
.sug__label { font-size: 14px; font-weight: 600; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sug__hint { font-size: 12px; color: var(--muted); }

.login {
  padding: 7px 20px;
  border-radius: 20px;
  border: 1px solid #fff;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 14px;
  text-decoration: none;
  transition: all 0.25s var(--ease);
}
.login:hover { background: var(--gold); border-color: var(--gold); color: var(--navy-deep); }
.admin-entry {
  padding: 7px 14px;
  border-radius: 20px;
  background: rgba(237, 183, 79, 0.18);
  border: 1px solid rgba(237, 183, 79, 0.5);
  color: var(--gold-soft);
  font-size: 13.5px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: all 0.2s var(--ease);
}
.admin-entry:hover { background: var(--gold); color: var(--navy-deep); }
.user { position: relative; }
.user__btn { display: block; padding: 0; border-radius: 50%; }
.user__avatar {
  display: grid;
  place-items: center;
  height: 38px;
  width: 38px;
  border-radius: 50%;
  background: var(--gold);
  color: var(--navy-deep);
  font-weight: 800;
}
.user__menu {
  position: absolute;
  top: calc(100% + 9px);
  right: 0;
  width: 148px;
  padding: 8px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-lift);
}
.user__name {
  padding: 6px 8px 8px;
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
  border-bottom: 1px solid var(--line);
}
.user__logout {
  width: 100%;
  margin-top: 6px;
  padding: 8px;
  border-radius: 8px;
  color: var(--red);
  font-size: 13px;
  text-align: left;
}
.user__logout:hover { background: rgba(231, 76, 60, 0.08); }
.burger { display: none; flex-direction: column; gap: 4px; padding: 8px; }
.burger span { display: block; width: 22px; height: 2px; border-radius: 2px; background: #fff; transition: transform 0.25s var(--ease), opacity 0.2s var(--ease); }
.burger.is-open span:nth-child(1) { transform: translateY(6px) rotate(45deg); }
.burger.is-open span:nth-child(2) { opacity: 0; }
.burger.is-open span:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }

@media (max-width: 1140px) {
  .search { width: 190px; }
  .nav__link { padding: 8px 10px; font-size: 15px; }
}
@media (max-width: 980px) {
  .burger { display: flex; }
  .search { display: none; }
  .nav {
    position: absolute;
    top: var(--header-h);
    left: 0; right: 0;
    flex-direction: column;
    align-items: stretch;
    gap: 0;
    padding: 8px 16px 16px;
    background: var(--navy-deep);
    box-shadow: var(--shadow-nav);
    transform: translateY(-12px);
    opacity: 0;
    pointer-events: none;
    transition: transform 0.25s var(--ease), opacity 0.2s var(--ease);
  }
  .nav--open { transform: translateY(0); opacity: 1; pointer-events: auto; }
  .nav__link { padding: 12px 14px; }
}
</style>
