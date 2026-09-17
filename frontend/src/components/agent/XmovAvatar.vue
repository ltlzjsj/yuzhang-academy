<script setup lang="ts">
import { onBeforeUnmount, onMounted, onUnmounted, ref } from 'vue'

const SDK_URL = 'https://media.xingyun3d.com/xingyun3d/general/litesdk/xmovAvatar@latest.js'
const GATEWAY = 'https://nebula-agent.xingyun3d.com/user/v1/ttsa/session'

const appId = (import.meta.env.VITE_XMOV_APP_ID as string) || ''
const appSecret = (import.meta.env.VITE_XMOV_APP_SECRET as string) || ''

const containerId = `xmov-figure-${Math.random().toString(36).slice(2, 9)}`
const loading = ref(true)
const error = ref('')

let avatar: any = null
let destroyed = false

function destroy() {
  if (destroyed) return
  destroyed = true
  const a = avatar
  avatar = null
  if (a) {
    try {
      a.destroy?.('page_unload')
    } catch {
      // 忽略销毁过程中的异常
    }
  }
}

async function loadScript(): Promise<void> {
  const w = window as any
  if (w.XmovAvatar) return
  await new Promise<void>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SDK_URL
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('魔珐 SDK 加载失败'))
    document.head.appendChild(s)
  })
}

async function init() {
  if (destroyed) return
  if (!appId || !appSecret) {
    error.value = '缺少魔珐星云密钥（VITE_XMOV_APP_ID / VITE_XMOV_APP_SECRET）'
    loading.value = false
    return
  }
  try {
    await loadScript()
    if (destroyed) return
    const w = window as any
    avatar = new w.XmovAvatar({
      containerId: `#${containerId}`,
      appId,
      appSecret,
      gatewayServer: GATEWAY,
      onMessage: (msg: any) => {
        if (msg?.code) error.value = `SDK 错误 ${msg.code}：${msg.message || ''}`
      },
      // 拦截字幕事件，不显示字幕
      proxyWidget: {
        subtitle_on: () => {},
        subtitle_off: () => {},
      },
    })
    if (destroyed) {
      try {
        avatar.destroy?.('page_unload')
      } catch {
        // 忽略
      }
      avatar = null
      return
    }
    await avatar.init({
      onDownloadProgress: (_p: number) => {
        // 进度回调，用于后续展示加载状态
      },
    })
    if (destroyed) {
      destroy()
      return
    }
    loading.value = false
  } catch (e: any) {
    if (!destroyed) error.value = e?.message || '魔珐数字人初始化失败'
    loading.value = false
  }
}

function speak(text: string) {
  if (!avatar || !text?.trim()) return
  avatar.speak(text.trim(), true, true)
}

function idle() {
  avatar?.interactiveidle?.()
}

defineExpose({ speak, idle, loading, error })

onMounted(init)
onBeforeUnmount(destroy)
onUnmounted(destroy)

// 开发模式热更新时也释放连接，避免 HMR 导致并发数泄漏
if ((import.meta as any).hot) {
  ;(import.meta as any).hot.dispose(() => {
    destroy()
  })
}
</script>

<template>
  <div class="xa">
    <div :id="containerId" class="xa__cv" />
    <div v-if="loading || error" class="xa__hint">{{ error || '数字人加载中…' }}</div>
  </div>
</template>

<style scoped>
.xa {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  border-radius: 16px;
  overflow: hidden;
  background: transparent;
  transform: translateX(11%) scale(1.25);
  transform-origin: bottom center;
}
.xa__cv {
  width: 100%;
  height: 100%;
}
/* 让魔珐 SDK 创建的 canvas 也保持透明背景，只显示数字人本身 */
.xa :deep(canvas),
.xa :deep(video) {
  background: transparent !important;
}
.xa__hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  text-align: center;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}
</style>
