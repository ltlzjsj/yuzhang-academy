import { http } from './http'

export interface HistoricalFigure {
  id: string
  name: string
  dynasty: string
  title: string
  academy: string
  accent: string
  image_url: string | null
  bio: string
  quote: string
  suggestions: string[]
  system_prompt: string
  voice_id?: string | null
  voice_style?: string | null
  voice_desc?: string | null
}

export async function listFigures() {
  return (await http.get<HistoricalFigure[]>('/figures')).data
}
