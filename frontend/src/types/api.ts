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
  latest_question_text: string | null
  latest_question_text_for_copy: string | null
  usage_summary: TokenUsageSummary
}

export type TranscriptResponse = {
  project_id: number
  project_name: string
  turn_count: number
  usage_summary: TokenUsageSummary
  transcript: string
}

export type CreateProjectPayload = {
  project_name: string
  system_prompt: string
}

export type UpdateProjectPayload = {
  project_name?: string
  system_prompt?: string
}
