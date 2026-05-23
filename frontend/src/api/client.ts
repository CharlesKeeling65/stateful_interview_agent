import type {
  AnswerSubmitResponse,
  CoverageDebugResponse,
  CreateProjectPayload,
  CurrentQuestionRegenerateResponse,
  CurrentQuestionSaveResponse,
  FileCoverageSummaryDebug,
  HumanReviewInput,
  NextQuestionRequestPayload,
  OpenCodePlanStepPayload,
  OpenCodePlanStepResponse,
  OpenCodeSessionResponse,
  ProjectNextResponse,
  ProjectRead,
  ProjectStartResponse,
  ProjectStatusResponse,
  QuestionNetworkSummaryDebug,
  QueueSummaryDebug,
  RunRead,
  TranscriptResponse,
  TurnTailDeleteResponse,
  TurnRead,
  UpdateProjectPayload,
} from '../types/api'

function getDefaultApiBase() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  if (typeof window !== 'undefined' && ['5173', '4173'].includes(window.location.port)) {
    return 'http://127.0.0.1:8000'
  }

  return ''
}

const API_BASE = getDefaultApiBase()

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(data?.detail ?? `Request failed with status ${res.status}`)
  }

  if (res.status === 204 || res.status === 205) {
    return undefined as T
  }

  return (await res.json()) as T
}

async function request<T>(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, init)
  return handle<T>(res)
}

export async function listProjects() {
  return request<ProjectRead[]>('/projects')
}

export async function createProject(payload: CreateProjectPayload) {
  return request<ProjectRead>('/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function startProject(projectId: number) {
  return request<ProjectStartResponse>(`/projects/${projectId}/start`, {
    method: 'POST',
  })
}

export async function submitAnswer(projectId: number, answer_text: string) {
  return request<AnswerSubmitResponse>(`/projects/${projectId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer_text }),
  })
}

export async function submitNext(projectId: number, payload?: NextQuestionRequestPayload) {
  return request<ProjectNextResponse>(`/projects/${projectId}/next`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      human_review: payload?.human_review ?? null,
      human_gate: payload?.human_gate ?? null,
    }),
  })
}

export async function autoAnswerLatest(projectId: number) {
  return request<AnswerSubmitResponse>(`/projects/${projectId}/auto-answer-latest`, {
    method: 'POST',
  })
}

export async function autoStep(projectId: number, payload?: NextQuestionRequestPayload) {
  return request<ProjectNextResponse>(`/projects/${projectId}/auto-step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      human_review: payload?.human_review ?? null,
      human_gate: payload?.human_gate ?? null,
    }),
  })
}

export async function ensureOpenCodeSession(projectId: number) {
  return request<OpenCodeSessionResponse>(`/projects/${projectId}/opencode/session`, {
    method: 'POST',
  })
}

export async function runOpenCodePlanStep(projectId: number, payload?: OpenCodePlanStepPayload) {
  return request<OpenCodePlanStepResponse>(`/projects/${projectId}/opencode/plan-step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      human_review: payload?.human_review ?? null,
      question_text: payload?.question_text ?? null,
    }),
  })
}

export async function regenerateCurrentQuestion(projectId: number, turnId: number, human_review?: HumanReviewInput | null) {
  return request<CurrentQuestionRegenerateResponse>(`/projects/${projectId}/turns/${turnId}/regenerate-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_review: human_review ?? null }),
  })
}

export async function saveCurrentQuestion(projectId: number, turnId: number, question_text: string) {
  return request<CurrentQuestionSaveResponse>(`/projects/${projectId}/turns/${turnId}/question`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question_text }),
  })
}

export async function getProject(projectId: number) {
  return request<ProjectRead>(`/projects/${projectId}`)
}

export async function getProjectTurns(projectId: number) {
  return request<TurnRead[]>(`/projects/${projectId}/turns`)
}

export async function getProjectStatus(projectId: number) {
  return request<ProjectStatusResponse>(`/projects/${projectId}/status`)
}

export async function getProjectTranscript(projectId: number) {
  return request<TranscriptResponse>(`/projects/${projectId}/transcript`)
}

export async function getProjectRuns(projectId: number) {
  return request<RunRead[]>(`/projects/${projectId}/runs`)
}

export async function getLatestProjectRun(projectId: number) {
  return request<RunRead>(`/projects/${projectId}/runs/latest`)
}

export async function getProjectRun(projectId: number, runId: number) {
  return request<RunRead>(`/projects/${projectId}/runs/${runId}`)
}

export async function updateProject(projectId: number, payload: UpdateProjectPayload) {
  return request<ProjectRead>(`/projects/${projectId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteProject(projectId: number) {
  await request<void>(`/projects/${projectId}`, {
    method: 'DELETE',
  })
}

export async function deleteTurnTail(projectId: number, turnId: number) {
  return request<TurnTailDeleteResponse>(`/projects/${projectId}/turns/${turnId}/tail`, {
    method: 'DELETE',
  })
}

export async function getProjectCoverageDebug(projectId: number) {
  return request<CoverageDebugResponse>(`/debug/projects/${projectId}/coverage`)
}

export async function getProjectQueueSummary(projectId: number) {
  return request<QueueSummaryDebug>(`/debug/projects/${projectId}/queue-summary`)
}

export async function getProjectFileCoverageSummary(projectId: number) {
  return request<FileCoverageSummaryDebug>(`/debug/projects/${projectId}/file-coverage-summary`)
}

export async function getProjectQuestionNetworkSummary(projectId: number) {
  return request<QuestionNetworkSummaryDebug>(`/debug/projects/${projectId}/question-network-summary`)
}

// Question Set APIs

export interface QuestionSetCreatePayload {
  repository_url: string
  repository_source?: 'remote' | 'local'
  total_questions?: number
  code_detail_ratio?: number
  min_core_file_coverage?: number
}

export interface QuestionSetResponse {
  id: number
  repository_url: string
  status: string
  total_questions: number
  code_detail_ratio: number
  min_core_file_coverage: number
  question_count: number
  code_detail_count: number
  code_detail_ratio_actual: number
  repository_analysis: Record<string, unknown>
  validation_report: Record<string, unknown>
  coverage_report: Record<string, unknown>
  error_message: string | null
  created_at: string | null
  updated_at: string | null
  questions: GeneratedQuestionResponse[]
}

export interface GeneratedQuestionResponse {
  id: number
  question_set_id: number
  question_no: number
  phase: string
  question_text: string
  target_files: string[]
  target_symbols: string[]
  quality_score: number
  warnings: string[]
  created_at: string | null
  updated_at: string | null
  revision_count: number
  version_count: number
  current_version_no: number
}

export interface QuestionRevisionRequest {
  question_id: number
  chinese_instruction: string
}

export interface QuestionRevisionResponse {
  question_id: number
  original_question: string
  revised_question: string
  chinese_instruction: string
  phase_changed: boolean
  new_phase: string | null
  coverage_changed: boolean
  duplicate_check_passed: boolean
  validation_result: Record<string, unknown>
  warnings: string[]
}

export interface ValidationReport {
  is_valid: boolean
  total_questions: number
  code_detail_count: number
  code_detail_ratio: number
  core_files_detected: number
  core_files_covered: number
  core_file_coverage: number
  phase_counts: Record<string, number>
  warnings: string[]
  errors: string[]
}

export interface CoverageReport {
  total_core_files: number
  covered_core_files: number
  coverage_percentage: number
  uncovered_files: string[]
  file_importance: Record<string, number>
}

export interface QuestionSetListResponse {
  question_sets: QuestionSetResponse[]
  total: number
}

export async function createQuestionSet(payload: QuestionSetCreatePayload) {
  return request<QuestionSetResponse>('/question-sets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function listQuestionSets(skip = 0, limit = 100) {
  return request<QuestionSetListResponse>(`/question-sets?skip=${skip}&limit=${limit}`)
}

export async function getQuestionSet(questionSetId: number) {
  return request<QuestionSetResponse>(`/question-sets/${questionSetId}`)
}

export async function getQuestionSetQuestions(questionSetId: number) {
  return request<GeneratedQuestionResponse[]>(`/question-sets/${questionSetId}/questions`)
}

export async function reviseQuestion(questionSetId: number, payload: QuestionRevisionRequest) {
  return request<QuestionRevisionResponse>(`/question-sets/${questionSetId}/revise`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function validateQuestionSet(questionSetId: number) {
  return request<ValidationReport>(`/question-sets/${questionSetId}/validate`, {
    method: 'POST',
  })
}

export async function getQuestionSetCoverage(questionSetId: number) {
  return request<CoverageReport>(`/question-sets/${questionSetId}/coverage`)
}

export async function deleteQuestionSet(questionSetId: number) {
  await request<void>(`/question-sets/${questionSetId}`, {
    method: 'DELETE',
  })
}

// Version management interfaces and functions

export interface QuestionVersionResponse {
  id: number
  question_id: number
  version_no: number
  question_text: string
  change_type: string // 'generated', 'revised', 'rollback'
  change_summary: string
  parent_version_id: number | null
  created_at: string | null
}

export interface QuestionVersionDiff {
  version_from: QuestionVersionResponse
  version_to: QuestionVersionResponse
  diff_html: string
}

export interface QuestionVersionRollbackRequest {
  version_no: number
  reason?: string
}

export interface CascadeRevisionRequest {
  question_id: number
  chinese_instruction: string
  cascade?: boolean
}

export interface CascadeRevisionResponse {
  question_id: number
  original_question: string
  revised_question: string
  chinese_instruction: string
  cascade: boolean
  cascade_results: Array<{
    question_no: number
    status: string
    original_text?: string
    new_text?: string
    error?: string
  }>
}

export async function getQuestionVersions(questionSetId: number, questionId: number) {
  return request<QuestionVersionResponse[]>(`/question-sets/${questionSetId}/questions/${questionId}/versions`)
}

export async function getQuestionVersion(questionSetId: number, questionId: number, versionNo: number) {
  return request<QuestionVersionResponse>(`/question-sets/${questionSetId}/questions/${questionId}/versions/${versionNo}`)
}

export async function getQuestionVersionDiff(questionSetId: number, questionId: number, v1: number, v2: number) {
  return request<QuestionVersionDiff>(`/question-sets/${questionSetId}/questions/${questionId}/diff?v1=${v1}&v2=${v2}`)
}

export async function rollbackQuestionVersion(questionSetId: number, questionId: number, payload: QuestionVersionRollbackRequest) {
  return request<QuestionVersionResponse>(`/question-sets/${questionSetId}/questions/${questionId}/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function cascadeReviseQuestion(questionSetId: number, questionId: number, payload: CascadeRevisionRequest) {
  return request<CascadeRevisionResponse>(`/question-sets/${questionSetId}/questions/${questionId}/cascade-revise`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
