import type { Locale } from '../i18n'
import type { ProjectRead, TokenUsageSummary, TurnRead } from '../types/api'

export function estimateTokenCount(value: string) {
  if (!value.trim()) {
    return 0
  }

  return Math.max(1, Math.ceil(value.trim().length / 4))
}

function getTurnContextValue(turn: TurnRead) {
  if (turn.answer_text) {
    return turn.answer_text
  }

  if (turn.answer_summary) {
    return turn.answer_summary
  }

  return ''
}

export function estimateNextPromptTokens({
  answerDraft,
  project,
  turns,
}: {
  answerDraft: string
  project: ProjectRead | null
  turns: TurnRead[]
}) {
  const systemPromptTokens = estimateTokenCount(project?.system_prompt ?? '')
  const turnTokens = turns.reduce((sum, turn) => {
    return (
      sum +
      estimateTokenCount(turn.question_text) +
      estimateTokenCount(getTurnContextValue(turn))
    )
  }, 0)

  return systemPromptTokens + turnTokens + estimateTokenCount(answerDraft) + 120
}

export function estimateNextOutputTokens(answerDraft: string) {
  const answerTokens = estimateTokenCount(answerDraft)
  return Math.max(48, Math.min(220, Math.ceil(answerTokens * 0.22) + 42))
}

export function formatTokenCount(value: number, locale: Locale = 'en') {
  return new Intl.NumberFormat(locale === 'zh-CN' ? 'zh-CN' : 'en-US').format(value)
}

export function summarizeOperationUsage(turn: TurnRead) {
  return turn.llm_usages.reduce<Record<string, TokenUsageSummary>>((acc, usage) => {
    const current = acc[usage.operation_type] ?? {
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      estimated_total_tokens: 0,
    }

    current.prompt_tokens += usage.prompt_tokens
    current.completion_tokens += usage.completion_tokens
    current.total_tokens += usage.total_tokens
    if (usage.is_estimated) {
      current.estimated_total_tokens += usage.total_tokens
    }
    acc[usage.operation_type] = current
    return acc
  }, {})
}
