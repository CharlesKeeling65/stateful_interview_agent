import type {
  AnswerSubmitResponse,
  CreateProjectPayload,
  CurrentQuestionRegenerateResponse,
  HumanReviewInput,
  NextQuestionRequestPayload,
  ProjectNextResponse,
  ProjectRead,
  ProjectStartResponse,
  ProjectStatusResponse,
  RunRead,
  TranscriptResponse,
  TurnRead,
  UpdateProjectPayload,
} from '../types/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

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
    body: JSON.stringify({ human_review: payload?.human_review ?? null }),
  })
}

export async function regenerateCurrentQuestion(projectId: number, turnId: number, human_review?: HumanReviewInput | null) {
  return request<CurrentQuestionRegenerateResponse>(`/projects/${projectId}/turns/${turnId}/regenerate-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_review: human_review ?? null }),
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
