<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const isApp = computed(() => route.meta.shell === 'app')
// 沉浸式页面（meta.immersive）隐藏站点顶栏，把高度全部让给内容。
// 目前没有路由启用它，保留为可选开关：想全屏时在路由 meta 里加 immersive: true。
const isImmersive = computed(() => !!route.meta.immersive)

onMounted(async () => {
  if (auth.token && !auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      router.replace('/login')
    }
  }
})
</script>

<template>
  <div
    class="shell-root"
    :class="[isApp ? 'shell-root--app' : 'shell-root--portal', { 'shell-root--immersive': isImmersive }]"
  >
    <AppHeader v-if="!isImmersive" />
    <main class="shell-main">
      <RouterView v-slot="{ Component }">
        <component :is="Component" />
      </RouterView>
    </main>
    <AppFooter v-if="!isApp" />
  </div>
</template>

<style scoped>
.shell-root {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--bg);
}
/* 应用页：固定视口高度，内容区自行滚动，无页脚 */
.shell-root--app {
  height: 100%;
  min-height: 0;
}
.shell-root--app .shell-main {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
/* 门户页：整页随内容流动并显示页脚 */
.shell-root--portal .shell-main {
  flex: 1;
}
</style>
