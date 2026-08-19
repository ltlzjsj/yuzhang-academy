<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const email = ref('')
const loading = ref(false)
const error = ref('')

const brandImg =
  '/api/v1/assets/academy/' +
  '组织拍摄了江西遗存书院/江西四大书院/白鹿洞书院/白鹿洞书院正学之门前古牌坊.JPG'
    .split('/')
    .map(encodeURIComponent)
    .join('/')

function readableError(e: any, fallback = '请求失败') {
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    return first?.msg || first?.message || fallback
  }
  return e?.message || fallback
}

function validateForm() {
  const name = username.value.trim()
  const pwd = password.value
  if (!name) return '请输入用户名'
  if (!pwd) return '请输入密码'
  if (mode.value === 'register') {
    if (name.length < 3) return '用户名至少需要 3 个字符'
    if (name.length > 64) return '用户名不能超过 64 个字符'
    if (pwd.length < 6) return '密码至少需要 6 个字符'
    if (pwd.length > 128) return '密码不能超过 128 个字符'
  }
  return ''
}

async function submit() {
  error.value = ''
  const msg = validateForm()
  if (msg) {
    error.value = msg
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value.trim(), password.value)
    } else {
      await auth.register(username.value.trim(), password.value, email.value.trim() || undefined)
    }
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (e: any) {
    error.value = readableError(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login">
    <!-- 品牌侧 -->
    <div class="brand" :style="{ backgroundImage: `url('${brandImg}')` }">
      <div class="brand__shade" />
      <div class="brand__content">
        <div class="brand__logo">
          <span class="brand__seal">书</span>
          <span class="brand__name h-serif">豫章书院</span>
        </div>
        <h2 class="brand__slogan h-serif">千年书院<br />数智新生</h2>
        <p class="brand__desc">
          融合知识检索、图文问答、AI 出题批改与历史名人互动，<br />让豫章书院文化成为可问、可学、可对话的数字课堂。
        </p>
        <div class="brand__tags">
          <span>智能问答</span><span>AI 培训</span><span>名人互动</span><span>知识库</span>
        </div>
      </div>
    </div>

    <!-- 表单侧 -->
    <div class="panel">
      <div class="form">
        <h1 class="form__title h-serif">{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</h1>
        <p class="form__sub">{{ mode === 'login' ? '登录以继续你的书院之旅' : '注册一个新账号，立即开始' }}</p>

        <div class="switch">
          <button :class="{ 'is-on': mode === 'login' }" @click="mode = 'login'">登录</button>
          <button :class="{ 'is-on': mode === 'register' }" @click="mode = 'register'">注册</button>
        </div>

        <form @submit.prevent="submit">
          <label class="form__lbl">用户名</label>
          <input v-model="username" class="field" autocomplete="username" placeholder="请输入用户名" required />

          <template v-if="mode === 'register'">
            <label class="form__lbl">邮箱（可选）</label>
            <input v-model="email" type="email" class="field" autocomplete="email" placeholder="name@example.com" />
          </template>

          <label class="form__lbl">密码</label>
          <input
            v-model="password"
            type="password"
            class="field"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            placeholder="请输入密码"
            required
          />

          <p v-if="error" class="form__err">{{ error }}</p>

          <button class="btn-navy form__submit" :disabled="loading">
            {{ loading ? '请稍候…' : mode === 'login' ? '登录' : '注册并登录' }}
          </button>
        </form>

        <p class="form__foot">
          {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
          <button class="form__link" @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '去注册' : '去登录' }}
          </button>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  height: 100%;
  background: var(--bg);
}
.brand {
  position: relative;
  background-size: cover;
  background-position: center;
  background-color: var(--navy-deep);
  overflow: hidden;
}
.brand__shade {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(160deg, rgba(20, 30, 40, 0.82), rgba(20, 30, 40, 0.6)),
    radial-gradient(circle at 20% 20%, rgba(237, 183, 79, 0.22), transparent 45%);
}
.brand__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
  padding: clamp(40px, 6vw, 88px);
  color: #fff;
}
.brand__logo { display: flex; align-items: center; gap: 12px; }
.brand__seal {
  display: grid;
  place-items: center;
  height: 44px;
  width: 44px;
  border-radius: 12px;
  background: linear-gradient(145deg, var(--gold), var(--gold-deep));
  color: var(--navy-deep);
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 900;
}
.brand__name { font-size: 22px; font-weight: 800; letter-spacing: 0.04em; }
.brand__slogan { margin: 40px 0 0; font-size: clamp(36px, 5vw, 58px); font-weight: 900; line-height: 1.15; }
.brand__desc { margin: 24px 0 0; color: rgba(255, 255, 255, 0.78); font-size: 15px; line-height: 1.9; }
.brand__tags { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 30px; }
.brand__tags span {
  padding: 6px 15px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
}

.panel { display: grid; place-items: center; padding: 32px; }
.form { width: min(400px, 100%); }
.form__title { font-size: 32px; font-weight: 800; color: var(--ink); }
.form__sub { margin-top: 8px; color: var(--sub); font-size: 14.5px; }
.switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin: 26px 0 22px;
  padding: 4px;
  border-radius: 12px;
  background: rgba(44, 62, 80, 0.07);
}
.switch button {
  padding: 9px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 700;
  color: var(--sub);
  transition: all 0.18s var(--ease);
}
.switch button.is-on { background: #fff; color: var(--navy); box-shadow: var(--shadow-soft); }
.form__lbl { display: block; margin: 14px 0 7px; font-size: 13px; font-weight: 600; color: var(--sub); }
.form__err { margin-top: 12px; color: var(--red); font-size: 13.5px; }
.form__submit { width: 100%; margin-top: 22px; padding-top: 12px; padding-bottom: 12px; }
.form__foot { margin-top: 20px; text-align: center; color: var(--muted); font-size: 14px; }
.form__link { color: var(--navy); font-weight: 700; }
.form__link:hover { color: var(--blue); }

@media (max-width: 860px) {
  .login { grid-template-columns: 1fr; }
  .brand { display: none; }
}
</style>
