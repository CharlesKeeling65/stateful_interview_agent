import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createTranslator } from '../i18n'
import { AnswerComposer } from './AnswerComposer'

describe('AnswerComposer', () => {
  it('shows cleaned auto-filled answers without the leading question prefix', () => {
    render(
      <AnswerComposer
        estimateDraftUsage={() => ({
          estimatedAnswerInputTokens: 0,
          estimatedNextPromptTokens: 0,
          estimatedNextOutputTokens: 0,
        })}
        initialAnswer="Q1: The app starts in app/main.py"
        onSave={vi.fn()}
        projectStarted
        t={createTranslator('en')}
      />,
    )

    expect(screen.getByRole('textbox')).toHaveValue('The app starts in app/main.py')
  })
})
