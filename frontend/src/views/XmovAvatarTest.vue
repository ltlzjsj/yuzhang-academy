<script setup lang="ts">
import { onBeforeUnmount, onMounted, onUnmounted, ref } from 'vue'

const SDK_URL = 'https://media.xingyun3d.com/xingyun3d/general/litesdk/xmovAvatar@latest.js'
const GATEWAY = 'https://nebula-agent.xingyun3d.com/user/v1/ttsa/session'

const appId = (import.meta.env.VITE_XMOV_APP_ID as string) || ''
const appSecret = (import.meta.env.VITE_XMOV_APP_SECRET as string) || ''

const loading = ref(true)
const progress = ref(0)
const status = ref('准备中…')
const error = ref('')
const text = ref('你好，我是豫章书院数字讲解员。')

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
      // 忽略销毁异常
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
    error.value = '缺少 VITE_XMOV_APP_ID / VITE_XMOV_APP_SECRET，请在 frontend/.env.local 里配置。'
    loading.value = false
    return
  }
  try {
    await loadScript()
    if (destroyed) return
    const w = window as any
    avatar = new w.XmovAvatar({
      containerId: '#xmov-avatar-container',
      appId,
      appSecret,
      gatewayServer: GATEWAY,
      onMessage: (msg: any) => {
        console.log('[xmov] message:', msg)
        if (msg?.code) error.value = `SDK 错误 ${msg.code}：${msg.message || ''}`
      },
      onStatusChange: (s: any) => {
        console.log('[xmov] status:', s)
        status.value = typeof s === 'string' ? s : JSON.stringify(s)
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
      onDownloadProgress: (p: number) => {
        progress.value = Math.round(p)
        status.value = `资源加载中 ${Math.round(p)}%`
        if (p >= 100) {
          loading.value = false
          status.value = '就绪'
        }
      },
    })
    if (destroyed) {
      destroy()
      return
    }
    loading.value = false
  } catch (e: any) {
    if (!destroyed) error.value = e?.message || '初始化失败'
    loading.value = false
  }
}

function speak() {
  if (!avatar || !text.value.trim()) return
  avatar.speak(text.value.trim(), true, true)
}

function idle() {
  avatar?.interactiveidle?.()
}

onMounted(init)
onBeforeUnmount(destroy)
onUnmounted(destroy)

if ((import.meta as any).hot) {
  ;(import.meta as any).hot.dispose(() => {
    destroy()
  })
}
</script>

<template>
  <div class="xmov">
    <h1 class="xmov__title">魔珐星云数字人测试</h1>

    <div class="xmov__stage">
      <div id="xmov-avatar-container" class="xmov__cv" />
      <div v-if="loading || error || (status && status !== '就绪')" class="xmov__overlay">
        <p v-if="loading">数字人加载中… {{ progress }}%</p>
        <p v-else-if="status && status !== '就绪'">{{ status }}</p>
        <p v-if="error" class="xmov__err">{{ error }}</p>
      </div>
    </div>

    <div class="xmov__ctrl">
      <input v-model="text" class="xmov__input" placeholder="输入要说的话" />
      <button class="xmov__btn xmov__btn--primary" :disabled="loading || !!error" @click="speak">说话</button>
      <button class="xmov__btn" :disabled="loading || !!error" @click="idle">待机</button>
    </div>
  </div>
</template>

<style scoped>
.xmov {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding: 28px 16px;
  min-height: 100vh;
  box-sizing: border-box;
}
.xmov__title {
  font-size: 20px;
  font-weight: 700;
}
.xmov__stage {
  position: relative;
  width: min(360px, 80vw);
  aspect-ratio: 9 / 16;
  border-radius: 16px;
  overflow: hidden;
  background: #0f1116;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
}
.xmov__cv {
  width: 100%;
  height: 100%;
}
.xmov__overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 6px;
  text-align: center;
  padding: 20px;
  color: rgba(255, 255, 255, 0.9);
  background: rgba(15, 17, 22, 0.72);
}
.xmov__err {
  color: #ff8f8f;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-all;
}
.xmov__ctrl {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  width: min(420px, 92vw);
}
.xmov__input {
  flex: 1 1 220px;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #d9d3c8;
  border-radius: 10px;
  font-size: 14px;
}
.xmov__btn {
  padding: 10px 18px;
  border: 1px solid #d9d3c8;
  border-radius: 10px;
  background: #fff;
  color: #333;
  font-size: 14px;
  cursor: pointer;
}
.xmov__btn--primary {
  background: #356f68;
  border-color: #356f68;
  color: #fff;
}
.xmov__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
