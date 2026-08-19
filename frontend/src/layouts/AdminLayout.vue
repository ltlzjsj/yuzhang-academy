<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const collapsed = ref(false)

const nav = [
  { to: '/admin/kb', label: '知识库管理', icon: '🗂️' },
  { to: '/admin/bank', label: '题库管理', icon: '📝' },
  { to: '/admin/activities', label: '活动管理', icon: '📜' },
  { to: '/admin/chat', label: '智能问答（完整）', icon: '💬' },
  { to: '/admin/settings', label: '系统设置', icon: '⚙️' },
]

onMounted(async () => {
  if (auth.token && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      /* guard handles redirect */
    }
  }
})

function logout() {
  auth.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="admin" :class="{ 'admin--collapsed': collapsed }">
    <aside class="side">
      <div class="side__brand">
        <span class="side__seal">书</span>
        <span v-if="!collapsed" class="side__name">
          <strong>豫章书院</strong>
          <small>管理后台</small>
        </span>
      </div>

      <nav class="side__nav">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="side__link"
          active-class="is-active"
        >
          <span class="side__icon">{{ item.icon }}</span>
          <span v-if="!collapsed">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="side__foot">
        <RouterLink to="/" class="side__back">
          <span class="side__icon">↩</span>
          <span v-if="!collapsed">返回官网</span>
        </RouterLink>
        <button class="side__collapse" @click="collapsed = !collapsed">
          {{ collapsed ? '»' : '« 收起' }}
        </button>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <h1>管理后台</h1>
        <div class="topbar__user">
          <span class="topbar__avatar">{{ (auth.user?.username ?? '?').slice(0, 1).toUpperCase() }}</span>
          <span class="topbar__name">{{ auth.user?.username }}</span>
          <button class="topbar__logout" @click="logout">退出</button>
        </div>
      </header>
      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin {
  display: grid;
  grid-template-columns: 232px 1fr;
  height: 100%;
  background: var(--bg);
}
.admin--collapsed { grid-template-columns: 68px 1fr; }

.side {
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, var(--navy) 0%, var(--navy-deep) 100%);
  color: #fff;
  overflow: hidden;
}
.side__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.side__seal {
  display: grid;
  place-items: center;
  height: 36px;
  width: 36px;
  flex: none;
  border-radius: 10px;
  background: linear-gradient(145deg, var(--gold), var(--gold-deep));
  color: var(--navy-deep);
  font-family: var(--font-serif);
  font-weight: 900;
  font-size: 19px;
}
.side__name strong { display: block; font-family: var(--font-serif); font-size: 17px; }
.side__name small { display: block; color: rgba(255, 255, 255, 0.55); font-size: 11px; margin-top: 2px; }

.side__nav { flex: 1; padding: 14px 12px; display: flex; flex-direction: column; gap: 4px; }
.side__link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 12px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.82);
  font-size: 14.5px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.18s var(--ease), color 0.18s var(--ease);
}
.side__link:hover { background: rgba(255, 255, 255, 0.08); color: #fff; }
.side__link.is-active { background: var(--gold); color: var(--navy-deep); }
.side__icon { width: 22px; text-align: center; flex: none; }

.side__foot { padding: 12px; border-top: 1px solid rgba(255, 255, 255, 0.1); display: flex; flex-direction: column; gap: 6px; }
.side__back {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.78);
  font-size: 14px;
  text-decoration: none;
}
.side__back:hover { background: rgba(255, 255, 255, 0.08); color: #fff; }
.side__collapse {
  padding: 8px;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12.5px;
  text-align: center;
}
.side__collapse:hover { background: rgba(255, 255, 255, 0.08); color: #fff; }

.main { display: flex; flex-direction: column; min-width: 0; height: 100%; }
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 60px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid var(--line);
}
.topbar h1 { font-family: var(--font-serif); font-size: 20px; font-weight: 800; color: var(--ink); }
.topbar__user { display: flex; align-items: center; gap: 10px; }
.topbar__avatar {
  display: grid;
  place-items: center;
  height: 34px;
  width: 34px;
  border-radius: 50%;
  background: var(--navy);
  color: #fff;
  font-weight: 800;
  font-size: 14px;
}
.topbar__name { font-size: 14px; color: var(--sub); }
.topbar__logout {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--line);
  font-size: 13px;
  color: var(--sub);
  transition: all 0.18s var(--ease);
}
.topbar__logout:hover { border-color: var(--red); color: var(--red); }
.content { flex: 1; min-height: 0; overflow: auto; background: var(--bg); }

@media (max-width: 760px) {
  .admin, .admin--collapsed { grid-template-columns: 60px 1fr; }
  .side__name, .side__link span:last-child:not(.side__icon), .side__back span:last-child:not(.side__icon) { display: none; }
  .topbar__name { display: none; }
}
</style>
