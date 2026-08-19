import { http } from './http'

export interface TrainingSession {
  id: number
  title: string
  topic: string
  question_type: string
  difficulty: string
  question_count: number
  kb_ids: number[] | null
  status: string
  total_score: number | null
  created_at: string
  updated_at: string
}

export interface QuestionOption {
  key: string
  text: string
}

export interface TrainingQuestion {
  id: number
  session_id: number
  seq: number
  question_type: string
  question: string
  reference_answer: string
  rubric: string
  max_score: number
  options: QuestionOption[] | null
  citations: Array<{
    idx: number
    chunk_id: number
    document_id: number
    filename: string
    page?: number | null
  }> | null
  created_at: string
}

export interface TrainingAnswer {
  id: number
  session_id: number
  question_id: number
  answer: string
  score: number
  feedback: string
  suggestion: string
  created_at: string
  updated_at: string
}

export interface TrainingReport {
  session: TrainingSession
  questions: TrainingQuestion[]
  answers: TrainingAnswer[]
}

export async function createTrainingSession(payload: {
  title?: string
  topic: string
  question_type: string
  difficulty: string
  question_count: number
  kb_ids: number[]
}) {
  return (await http.post<TrainingSession>('/training/sessions', payload)).data
}

// AI 出题/批改可能耗时较久，单独放宽超时（默认 30s 会超时）。
const AI_TIMEOUT = 180000

export async function generateTrainingQuestions(sessionId: number, fresh = false) {
  return (
    await http.post<TrainingQuestion[]>(
      `/training/sessions/${sessionId}/generate`,
      undefined,
      { params: { fresh }, timeout: AI_TIMEOUT },
    )
  ).data
}

export async function gradeTrainingSession(
  sessionId: number,
  answers: Array<{ question_id: number; answer: string }>,
) {
  return (
    await http.post<TrainingReport>(`/training/sessions/${sessionId}/grade`, { answers }, { timeout: AI_TIMEOUT })
  ).data
}

export async function buildQuestionBank(payload: {
  kb_ids: number[]
  topic?: string
  question_type?: string
  difficulty?: string
  count?: number
}) {
  return (
    await http.post<{ added: number; total: number }>('/training/bank/build', payload, {
      timeout: 300000, // 批量出题较久，给 5 分钟
    })
  ).data
}

export async function listTrainingSessions() {
  return (await http.get<TrainingSession[]>('/training/sessions')).data
}

// 【管理后台】题库管理
export interface BankItem {
  id: number
  kb_id: number
  topic: string
  question_type: string
  difficulty: string
  question: string
  reference_answer: string
  rubric: string
  max_score: number
  options: QuestionOption[] | null
  citations: any[] | null
  created_at: string
}

export async function listQuestionBank(params: { kb_id?: number; limit?: number; offset?: number } = {}) {
  return (await http.get<{ items: BankItem[]; total: number }>('/training/bank', { params })).data
}

export async function deleteBankItem(id: number) {
  await http.delete(`/training/bank/${id}`)
}

export async function getTrainingReport(sessionId: number) {
  return (await http.get<TrainingReport>(`/training/sessions/${sessionId}/report`)).data
}

// ---- 学生考试：按科目+难度从题库成卷 ----
export interface Subject {
  subject: string
  total: number
  easy: number
  normal: number
  hard: number
}

export async function listSubjects() {
  return (await http.get<Subject[]>('/training/subjects')).data
}

export async function startExam(payload: { subject: string; difficulty: string; count?: number }) {
  return (
    await http.post<{ session: TrainingSession; questions: TrainingQuestion[] }>(
      '/training/exam',
      payload,
      { timeout: 60000 },
    )
  ).data
}
