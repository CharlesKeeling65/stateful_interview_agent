import * as vscode from 'vscode'

export type ConfigSnapshot = {
  paths: {
    opencode_config: string
    env_file: string
  }
  opencode_mindflow: {
    base_url?: string | null
    api_key_masked: string
    has_api_key: boolean
    source?: string | null
  }
  effective_anthropic: {
    base_url?: string | null
    api_key_masked: string
    has_api_key: boolean
    source?: string | null
  }
  env_entries: Array<{
    key: string
    value: string
    is_secret: boolean
    has_value: boolean
  }>
}

export type HumanReviewInput = {
  verdict?: 'sufficient' | 'insufficient' | 'drifted' | null
  direction?: 'continue' | 'redirect'
  preferred_next_focus?: string | null
  note?: string | null
}

export type NextQuestionPayload = {
  human_review?: HumanReviewInput | null
}

function getApiBaseUrl() {
  return vscode.workspace
    .getConfiguration('statefulInterview')
    .get<string>('apiBaseUrl', 'http://127.0.0.1:8000')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, init)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.detail ?? `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export async function listProjects() {
  return request<any[]>('/projects')
}

export async function getProject(projectId: number) {
  return request<any>(`/projects/${projectId}`)
}

export async function getProjectTurns(projectId: number) {
  return request<any[]>(`/projects/${projectId}/turns`)
}

export async function getProjectStatus(projectId: number) {
  return request<any>(`/projects/${projectId}/status`)
}

export async function getLatestProjectRun(projectId: number) {
  return request<any>(`/projects/${projectId}/runs/latest`)
}

export async function createProject(payload: {
  project_name: string
  system_prompt: string
  answer_provider_type?: string
  answer_automation_enabled?: boolean
}) {
  return request<any>('/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function startProject(projectId: number) {
  return request<any>(`/projects/${projectId}/start`, { method: 'POST' })
}

export async function saveAnswer(projectId: number, answer_text: string) {
  return request<any>(`/projects/${projectId}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer_text }),
  })
}

export async function generateNext(projectId: number, payload?: NextQuestionPayload) {
  return request<any>(`/projects/${projectId}/next`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      human_review: payload?.human_review ?? null,
      human_gate: null,
    }),
  })
}

export async function autoAnswerLatest(projectId: number) {
  return request<any>(`/projects/${projectId}/auto-answer-latest`, { method: 'POST' })
}

export async function autoStep(projectId: number, payload?: NextQuestionPayload) {
  return request<any>(`/projects/${projectId}/auto-step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      human_review: payload?.human_review ?? null,
      human_gate: null,
    }),
  })
}

export async function getConfigSnapshot() {
  return request<ConfigSnapshot>('/config')
}

export async function updateOpencodeMindflow(payload: { base_url?: string | null; api_key?: string | null }) {
  return request<ConfigSnapshot>('/config/opencode-mindflow', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function updateEnvEntries(entries: Array<{ key: string; value: string }>) {
  return request<ConfigSnapshot>('/config/env', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entries }),
  })
}

export async function regenerateCurrentQuestion(
  projectId: number,
  turnId: number,
  human_review?: HumanReviewInput | null,
) {
  return request<any>(`/projects/${projectId}/turns/${turnId}/regenerate-question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_review: human_review ?? null }),
  })
}
