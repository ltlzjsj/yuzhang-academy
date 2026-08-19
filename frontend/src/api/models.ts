import { http } from './http'

export interface OllamaModel {
  name: string
  size?: number
  modified_at?: string
  family?: string
  parameter_size?: string
}

export interface ModelsResp {
  items: OllamaModel[]
  default_chat: string
  embed: string
}

export async function fetchModels(): Promise<ModelsResp> {
  const { data } = await http.get<ModelsResp>('/models')
  return data
}
