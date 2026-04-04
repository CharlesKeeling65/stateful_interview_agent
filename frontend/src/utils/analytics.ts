import type { ProjectRead, ProjectStatusResponse, TurnRead } from '../types/api'

export type StageBreakdownItem = {
  stage: string
  count: number
}

export type TurnTokenTrendItem = {
  turnNo: number
  label: string
  promptTokens: number
  completionTokens: number
  humanReviewTokens: number
  totalTokens: number
  cumulativeTokens: number
  regenerationCount: number
}

export type StageTransitionItem = {
  from: string
  to: string
  count: number
}

export type StageSegmentItem = {
  stage: string
  startTurnNo: number
  endTurnNo: number
  turnSpan: number
  share: number
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
  stageSegments: StageSegmentItem[]
  stageTransitions: StageTransitionItem[]
  timeline: Array<{ stage: string; turnNo: number }>
  tokenBreakdown: {
    completion: number
    prompt: number
    total: number
  }
  turnTokenTrend: TurnTokenTrendItem[]
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
  const transitionMap = new Map<string, number>()
  const orderedTurns = [...turns].toSorted((left, right) => left.turn_no - right.turn_no)
  const turnTokenTrend: TurnTokenTrendItem[] = []
  const stageSegments: StageSegmentItem[] = []
  let cumulativeTokens = 0

  for (const [index, turn] of orderedTurns.entries()) {
    cumulativeTokens += turn.total_tokens
    turnTokenTrend.push({
      turnNo: turn.turn_no,
      label: `T${turn.turn_no}`,
      promptTokens: turn.prompt_tokens,
      completionTokens: turn.completion_tokens,
      humanReviewTokens: turn.human_intervention_regeneration_usage_summary.total_tokens,
      totalTokens: turn.total_tokens,
      cumulativeTokens,
      regenerationCount: turn.question_regeneration_count,
    })

    const previousTurn = orderedTurns[index - 1]
    if (previousTurn) {
      const transitionKey = `${previousTurn.stage}→${turn.stage}`
      transitionMap.set(transitionKey, (transitionMap.get(transitionKey) ?? 0) + 1)
    }

    const lastSegment = stageSegments[stageSegments.length - 1]
    if (lastSegment && lastSegment.stage === turn.stage && lastSegment.endTurnNo === turn.turn_no - 1) {
      lastSegment.endTurnNo = turn.turn_no
      lastSegment.turnSpan += 1
      continue
    }

    stageSegments.push({
      stage: turn.stage,
      startTurnNo: turn.turn_no,
      endTurnNo: turn.turn_no,
      turnSpan: 1,
      share: 0,
    })
  }

  for (const turn of turns) {
    stageMap.set(turn.stage, (stageMap.get(turn.stage) ?? 0) + 1)
  }

  for (const segment of stageSegments) {
    segment.share = turns.length > 0 ? segment.turnSpan / turns.length : 0
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
    stageSegments,
    stageTransitions: [...transitionMap.entries()].map(([key, count]) => {
      const [from, to] = key.split('→')
      return { from, to, count }
    }),
    timeline: turns.map((turn) => ({ stage: turn.stage, turnNo: turn.turn_no })),
    tokenBreakdown: {
      completion: status?.usage_summary.completion_tokens ?? project.total_completion_tokens,
      prompt: status?.usage_summary.prompt_tokens ?? project.total_prompt_tokens,
      total: status?.usage_summary.total_tokens ?? project.total_tokens,
    },
    turnTokenTrend,
    totalGenerationTimeMs: status?.cumulative_generation_time_ms ?? 0,
    totalRegenerations: turns.reduce((sum, turn) => sum + turn.question_regeneration_count, 0),
    totalTurns: turns.length,
  }
}
