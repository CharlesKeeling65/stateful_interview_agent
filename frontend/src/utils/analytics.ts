import type { ProjectRead, ProjectStatusResponse, TurnRead } from '../types/api'

export type StageBreakdownItem = {
  stage: string
  count: number
}

export type ProjectAnalytics = {
  answeredTurns: number
  pendingTurns: number
  averageRunDurationMs: number
  currentStage: string
  humanRegenerationTokenTotal: number
  latestTurnRegenerationCount: number
  minimumGoalReached: boolean
  projectId: number
  projectName: string
  runCount: number
  stageBreakdown: StageBreakdownItem[]
  timeline: Array<{ stage: string; turnNo: number }>
  tokenBreakdown: {
    completion: number
    prompt: number
    total: number
  }
  totalGenerationTimeMs: number
  totalRegenerations: number
  totalTurns: number
}

export function buildProjectAnalytics(
  project: ProjectRead,
  status: ProjectStatusResponse | null,
  turns: TurnRead[],
): ProjectAnalytics {
  const stageMap = new Map<string, number>()
  for (const turn of turns) {
    stageMap.set(turn.stage, (stageMap.get(turn.stage) ?? 0) + 1)
  }

  return {
    answeredTurns: turns.filter((turn) => Boolean(turn.answer_text)).length,
    pendingTurns: turns.filter((turn) => !turn.answer_text).length,
    averageRunDurationMs: status?.average_run_duration_ms ?? 0,
    currentStage: status?.current_stage ?? project.current_stage,
    humanRegenerationTokenTotal: turns.reduce(
      (sum, turn) => sum + turn.human_intervention_regeneration_usage_summary.total_tokens,
      0,
    ),
    latestTurnRegenerationCount: status?.latest_turn_regeneration_count ?? 0,
    minimumGoalReached: status?.minimum_goal_reached ?? false,
    projectId: project.id,
    projectName: project.project_name,
    runCount: status?.run_count ?? 0,
    stageBreakdown: [...stageMap.entries()].map(([stage, count]) => ({ stage, count })),
    timeline: turns.map((turn) => ({ stage: turn.stage, turnNo: turn.turn_no })),
    tokenBreakdown: {
      completion: status?.usage_summary.completion_tokens ?? project.total_completion_tokens,
      prompt: status?.usage_summary.prompt_tokens ?? project.total_prompt_tokens,
      total: status?.usage_summary.total_tokens ?? project.total_tokens,
    },
    totalGenerationTimeMs: status?.cumulative_generation_time_ms ?? 0,
    totalRegenerations: turns.reduce((sum, turn) => sum + turn.question_regeneration_count, 0),
    totalTurns: turns.length,
  }
}
