import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { public: true } },

  // ---- 公开官网（豫章书院门户）----
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    children: [
      // 内容页公开；AI 功能页需登录
      { path: '', name: 'home', component: () => import('@/views/Home.vue'), meta: { shell: 'portal', public: true } },
      { path: 'overview', name: 'overview', component: () => import('@/views/Overview.vue'), meta: { shell: 'portal', public: true } },
      { path: 'figures', name: 'figures', component: () => import('@/views/HistoricalFigures.vue'), meta: { shell: 'portal', public: true } },
      // 人物对话页保留站点顶栏（如需恢复全屏沉浸式，在 meta 里加回 immersive: true）
      { path: 'figures/:id', name: 'figure-chat', component: () => import('@/views/FigureChat.vue'), meta: { shell: 'app', requiresAuth: true } },
      { path: 'activities', name: 'activities', component: () => import('@/views/Activities.vue'), meta: { shell: 'portal', public: true } },
      { path: 'about', name: 'about', component: () => import('@/views/About.vue'), meta: { shell: 'portal', public: true } },
      { path: 'tour', name: 'tour', component: () => import('@/views/Tour.vue'), meta: { shell: 'portal', public: true } },
      { path: 'xmov-test', name: 'xmov-test', component: () => import('@/views/XmovAvatarTest.vue'), meta: { shell: 'portal', public: true } },
      { path: 'zhuxi-ue5-test', name: 'zhuxi-ue5-test', component: () => import('@/views/ZhuxiUe5Test.vue'), meta: { shell: 'portal', public: true } },
      { path: 'photo', name: 'photo', component: () => import('@/views/Photo.vue'), meta: { shell: 'portal', public: true } },
      { path: 'academies', name: 'academies', component: () => import('@/views/AcademyList.vue'), meta: { shell: 'portal', public: true } },
      { path: 'academies/:id', name: 'academy-detail', component: () => import('@/views/AcademyDetail.vue'), meta: { shell: 'portal', public: true } },
      { path: 'relations', name: 'relations', component: () => import('@/views/Relations.vue'), meta: { shell: 'portal', public: true } },
      { path: 'quiz', name: 'quiz', component: () => import('@/views/Quiz.vue'), meta: { shell: 'portal', public: true } },
      { path: 'qa', name: 'qa', component: () => import('@/views/QA.vue'), meta: { shell: 'portal', requiresAuth: true } },
      { path: 'training', name: 'training', component: () => import('@/views/Training.vue'), meta: { shell: 'portal', requiresAuth: true } },
    ],
  },

  // ---- 管理后台（role=admin）----
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { admin: true },
    children: [
      { path: '', redirect: '/admin/kb' },
      { path: 'kb', name: 'admin-kb', component: () => import('@/views/KnowledgeBases.vue') },
      { path: 'kb/:id', name: 'admin-kb-detail', component: () => import('@/views/KBDetail.vue'), props: true },
      { path: 'bank', name: 'admin-bank', component: () => import('@/views/admin/QuestionBank.vue') },
      { path: 'activities', name: 'admin-activities', component: () => import('@/views/admin/Activities.vue') },
      { path: 'chat', name: 'admin-chat', component: () => import('@/views/Chat.vue') },
      { path: 'settings', name: 'admin-settings', component: () => import('@/views/Settings.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, _from, saved) {
    if (to.hash) return { el: to.hash, top: 80, behavior: 'smooth' }
    if (saved) return saved
    return { top: 0 }
  },
})

function needsAuth(to: any): boolean {
  return to.matched.some((r: any) => r.meta?.requiresAuth || r.meta?.admin)
}
function needsAdmin(to: any): boolean {
  return to.matched.some((r: any) => r.meta?.admin)
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (needsAuth(to) && !auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (needsAdmin(to)) {
    if (!auth.user && auth.token) {
      try {
        await auth.fetchMe()
      } catch {
        auth.logout()
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }
    if (!auth.isAdmin) return { name: 'home' }
  }
  if (to.name === 'login' && auth.token) return { name: 'home' }
})

export default router
