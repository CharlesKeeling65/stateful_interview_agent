import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { createTranslator } from '../i18n'
import type { RunRead } from '../types/api'
import { ActiveRunPanel } from './ExecutionTraceSection'

const run: RunRead = {
  id: 1,
  project_id: 1,
  turn_no: 3,
  request_id: 'req-1',
  trace_id: 'trace-1',
  status: 'running',
  started_at: '2026-04-04T08:00:00',
  ended_at: null,
  duration_ms: null,
  total_llm_tokens: 120,
  total_llm_calls: 1,
  step_count: 2,
  current_step_key: 'call_llm',
  current_step_label: 'Call model',
  current_step_status: 'running',
  steps: [
    {
      id: 11,
      step_index: 1,
      step_key: 'render_prompt',
      label: 'Render prompt',
      status: 'completed',
      description: 'Render the next prompt',
      method: 'prompt',
      started_at: '2026-04-04T08:00:00',
      ended_at: '2026-04-04T08:00:01',
      duration_ms: 1000,
      next_step_hint: 'Call model',
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      meta: {},
    },
    {
      id: 12,
      step_index: 2,
      step_key: 'call_llm',
      label: 'Call model',
      status: 'running',
      description: 'Call the LLM',
      method: 'llm',
      started_at: '2026-04-04T08:00:01',
      ended_at: null,
      duration_ms: null,
      next_step_hint: null,
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      meta: {},
    },
  ],
}

describe('ActiveRunPanel', () => {
  it('renders regeneration-specific copy when current question is being regenerated', () => {
    render(
      <ActiveRunPanel
        locale="en"
        run={run}
        t={createTranslator('en')}
        variant="regenerate"
      />,
    )

    expect(screen.getByText('Re-drafting the current question')).toBeInTheDocument()
    expect(
      screen.getByText('The agent is replaying the same next-question workflow from the previous answered turn and overwriting this current question when the run completes.'),
    ).toBeInTheDocument()
  })
})
