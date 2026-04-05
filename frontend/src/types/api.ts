export type LLMUsageRead = {
  id: number
  project_id: number
  turn_id: number | null
  operation_type: 'question_generation' | 'answer_summarization' | string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  is_estimated: boolean
  created_at: string
}

export type TokenUsageSummary = {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated_total_tokens: number
}

export type RepositorySourceConfig = {
  source_type: 'none' | 'local_path' | 'git_url' | string
  local_path?: string | null
  git_url?: string | null
  git_ref?: string | null
  cache_path?: string | null
  commit_sha?: string | null
}

export type RepositoryManifestRead = {
  root_path?: string | null
  file_count: number
  language_counts: Record<string, number>
  top_level_directories: string[]
  key_files: string[]
  symbol_count: number
  last_indexed_at?: string | null
}

export type HumanReviewInput = {
  verdict?: 'sufficient' | 'insufficient' | 'drifted' | null
  direction: 'continue' | 'redirect'
  preferred_next_focus?: string | null
  note?: string | null
  phase?: string | null
  phase_ready?: boolean | null
}

export type QuestionVersionRead = {
  id: number
  version_no: number
  generation_kind: string
  question_text: string
  question_plan: QuestionPlanRead | null
  human_review: HumanReviewInput | null
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  is_estimated: boolean
  created_at: string
}

export type QuestionPlanRead = {
  phase?: string | null
  intent_mode?: string | null
  question_intent?: string | null
  target_branch_id?: string | null
  target_type?: string | null
  target_label?: string | null
  selected_framework_gap?: string | null
  selected_branch_ids?: string[]
  selected_turn_ids?: number[]
  human_review_applied?: boolean | null
  drift_detected?: boolean | null
  why_this_question?: string | null
  repo_queries?: string[]
  repo_selected_paths?: string[]
  repo_selected_symbols?: string[]
  repo_commit_sha?: string | null
  repo_tool_calls?: Array<Record<string, unknown>>
}

export type AnswerAnalysisChunkRead = {
  index: number
  text: string
}

export type AnswerAnalysisRead = {
  stage_focus?: string | null
  summary_source?: string | null
  key_points?: string[]
  follow_up_anchors?: string[]
  rag_chunks?: AnswerAnalysisChunkRead[]
}

export type RunStepRead = {
  id: number
  step_index: number
  step_key: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed' | string
  description: string | null
  method: string | null
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  next_step_hint: string | null
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  meta: Record<string, unknown>
}

export type RunRead = {
  id: number
  project_id: number
  turn_no: number | null
  request_id: string | null
  trace_id: string | null
  status: 'running' | 'completed' | 'failed' | string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  total_llm_tokens: number
  total_llm_calls: number
  step_count: number
  current_step_key: string | null
  current_step_label: string | null
  current_step_status: string | null
  steps: RunStepRead[]
}

export type ProjectRead = {
  id: number
  project_name: string
  system_prompt: string
  current_stage: string
  turn_count: number
  status: string
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  estimated_total_tokens: number
  repository: RepositorySourceConfig
  repository_manifest: RepositoryManifestRead
  created_at: string
  updated_at: string
}

export type TurnRead = {
  id: number
  project_id: number
  turn_no: number
  stage: string
  question_text: string
  question_text_for_copy: string
  answer_text: string | null
  answer_summary: string | null
  answer_analysis?: AnswerAnalysisRead | null
  human_review: HumanReviewInput | null
  question_plan: QuestionPlanRead | null
  current_question_version_no: number
  question_regeneration_count: number
  human_intervention_regeneration_usage_summary: TokenUsageSummary
  question_versions: QuestionVersionRead[]
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  llm_usages: LLMUsageRead[]
  created_at: string
}

export type ProjectStartResponse = {
  project: ProjectRead
  first_turn: TurnRead
}

export type ProjectNextResponse = {
  project: ProjectRead
  previous_turn: TurnRead
  next_turn: TurnRead | null
  run_id: number | null
  interview_finished: boolean
  minimum_goal_reached: boolean
  usage_summary: TokenUsageSummary
  message: string
}

export type ProjectStatusResponse = {
  project_id: number
  project_name: string
  status: string
  current_stage: string
  turn_count: number
  minimum_goal_reached: boolean
  max_turn_limit: number
  latest_turn_no: number | null
  latest_turn_answered: boolean | null
  latest_turn_ready_for_next_generation: boolean
  latest_question_text: string | null
  latest_question_text_for_copy: string | null
  latest_turn_regeneration_count: number
  latest_human_intervention_regeneration_usage_summary: TokenUsageSummary
  cumulative_generation_time_ms: number
  run_count: number
  average_run_duration_ms: number
  repository: RepositorySourceConfig
  repository_manifest: RepositoryManifestRead
  usage_summary: TokenUsageSummary
}

export type TranscriptResponse = {
  project_id: number
  project_name: string
  turn_count: number
  usage_summary: TokenUsageSummary
  transcript: string
}

export type AnswerSubmitResponse = {
  project_id: number
  updated_turn: TurnRead
  can_generate_next: boolean
  message: string
}

export type CreateProjectPayload = {
  project_name: string
  system_prompt: string
  repository?: {
    source_type: 'none' | 'local_path' | 'git_url'
    local_path?: string | null
    git_url?: string | null
    git_ref?: string | null
  }
}

export type UpdateProjectPayload = {
  project_name?: string
  system_prompt?: string
  repository?: {
    source_type: 'none' | 'local_path' | 'git_url'
    local_path?: string | null
    git_url?: string | null
    git_ref?: string | null
  }
}

export type NextQuestionRequestPayload = {
  human_review?: HumanReviewInput | null
}

export type CurrentQuestionRegenerateResponse = {
  project_id: number
  turn: TurnRead
  run_id: number | null
  usage_summary: TokenUsageSummary
  applied_changes: {
    review_persisted: boolean
    planner_followed_review: boolean
    question_changed: boolean
    previous_stage: string
    current_stage: string
    stage_changed: boolean
    requested_focus?: string | null
    requested_verdict?: string | null
    requested_direction?: string | null
    note_applied: boolean
    phase_ready_applied: boolean
    question_version_before: number
    question_version_after: number
    regeneration_count_before: number
    regeneration_count_after: number
  }
  message: string
}
