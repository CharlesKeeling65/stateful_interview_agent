import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { createTranslator } from '../i18n'
import type { TurnRead } from '../types/api'
import { TurnCard } from './TurnCard'

const turn: TurnRead = {
  id: 1,
  project_id: 1,
  turn_no: 19,
  stage: 'Architecture Understanding',
  question_text: 'Q19: Which modules coordinate the request path?',
  question_text_for_copy: 'Which modules coordinate the request path?',
  answer_text: null,
  answer_summary: null,
  human_review: {
    verdict: 'drifted',
    direction: 'redirect',
    preferred_next_focus: 'architecture',
    note: 'Move this back to architecture.',
    phase: 'Architecture Understanding',
    phase_ready: false,
  },
  question_plan: {
    phase: 'Architecture Understanding',
    question_intent: 'human_guided_redirect',
    why_this_question: 'The human redirected the interview toward architecture coverage.',
  },
  current_question_version_no: 2,
  question_regeneration_count: 1,
  human_intervention_regeneration_usage_summary: {
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    estimated_total_tokens: 0,
  },
  question_versions: [],
  prompt_tokens: 30,
  completion_tokens: 12,
  total_tokens: 42,
  llm_usages: [],
  created_at: '2026-04-04T08:00:00',
}

describe('TurnCard', () => {
  it('shows the corrected stage inside the persisted human review summary', () => {
    render(
      <TurnCard
        locale="en"
        t={createTranslator('en')}
        turn={turn}
      />,
    )

    expect(screen.getByText('Stage correction: Architecture Understanding')).toBeInTheDocument()
  })
})
