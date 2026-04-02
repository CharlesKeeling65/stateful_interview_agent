export type ProjectRead = {
  id: number
  project_name: string
  system_prompt: string
  current_stage: string
  turn_count: number
  status: string
  created_at: string
  updated_at: string
}

export type TurnRead = {
  id: number
  project_id: number
  turn_no: number
  stage: string
  question_text: string
  answer_text: string | null
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
}

export type TranscriptResponse = {
  project_id: number
  project_name: string
  turn_count: number
  transcript: string
}

export type CreateProjectPayload = {
  project_name: string
  system_prompt: string
}
