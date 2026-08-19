import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { http } from '@/api/http'

export interface UserInfo {
  id: number
  username: string
  email: string | null
  role: string
  is_admin?: boolean
}

const TOKEN_KEY = 'georag_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserInfo | null>(null)
  const isAuthed = computed(() => !!token.value)
  const isAdmin = computed(() => !!user.value?.is_admin)

  function setToken(t: string | null) {
    token.value = t
    if (t) localStorage.setItem(TOKEN_KEY, t)
    else localStorage.removeItem(TOKEN_KEY)
  }

  async function login(username: string, password: string) {
    const body = new URLSearchParams({ username, password })
    const { data } = await axios.post('/api/v1/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    setToken(data.access_token)
    await fetchMe()
  }

  async function register(username: string, password: string, email?: string) {
    await axios.post('/api/v1/auth/register', { username, password, email: email || null })
    await login(username, password)
  }

  async function fetchMe() {
    const { data } = await http.get<UserInfo>('/users/me')
    user.value = data
    return data
  }

  function logout() {
    setToken(null)
    user.value = null
  }

  return { token, user, isAuthed, isAdmin, login, register, fetchMe, logout, setToken }
})
