import { http } from './http'

export type ActivityStatus = 'open' | 'ongoing' | 'closed'

export interface Activity {
  id: number
  category: string
  title: string
  summary: string
  body: string
  event_date: string
  period: string
  place: string
  audience: string
  status: ActivityStatus
  highlights: string[]
  image: string
  image_url: string | null
  is_published: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ActivityInput {
  category: string
  title: string
  summary?: string
  body?: string
  event_date?: string
  period?: string
  place?: string
  audience?: string
  status?: ActivityStatus
  highlights?: string[]
  image?: string
  is_published?: boolean
  sort_order?: number
}

export async function listActivities(params?: { category?: string; include_unpublished?: boolean }) {
  return (await http.get<Activity[]>('/activities', { params })).data
}

export async function createActivity(data: ActivityInput) {
  return (await http.post<Activity>('/activities', data)).data
}

export async function updateActivity(id: number, data: Partial<ActivityInput>) {
  return (await http.patch<Activity>(`/activities/${id}`, data)).data
}

export async function deleteActivity(id: number) {
  await http.delete(`/activities/${id}`)
}
