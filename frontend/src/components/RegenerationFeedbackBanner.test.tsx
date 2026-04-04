import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { createTranslator } from '../i18n'
import { RegenerationFeedbackBanner } from './RegenerationFeedbackBanner'

describe('RegenerationFeedbackBanner', () => {
  it('renders the applied regeneration signals and transitions', () => {
    render(
      <RegenerationFeedbackBanner
        feedback={{
          review_persisted: true,
          planner_followed_review: true,
          question_changed: true,
          previous_stage: 'Panorama Mapping',
          current_stage: 'Architecture Understanding',
          stage_changed: true,
          requested_focus: 'architecture',
          requested_verdict: 'drifted',
          requested_direction: 'redirect',
          note_applied: true,
          phase_ready_applied: false,
          question_version_before: 1,
          question_version_after: 2,
          regeneration_count_before: 0,
          regeneration_count_after: 1,
        }}
        locale="en"
        t={createTranslator('en')}
        tokensUsed={150}
      />,
    )

    expect(screen.getByText('Applied review changes')).toBeInTheDocument()
    expect(screen.getAllByText('Planner followed review').length).toBeGreaterThan(0)
    expect(screen.getByText('Panorama Mapping -> Architecture Understanding')).toBeInTheDocument()
    expect(screen.getByText('Focus applied: Architecture')).toBeInTheDocument()
    expect(screen.getByText('Question wording changed')).toBeInTheDocument()
    expect(screen.getByText('This regeneration: 150')).toBeInTheDocument()
  })
})
