import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createTranslator } from '../i18n'
import { GenerationControlPanel } from './GenerationControlPanel'

afterEach(() => {
  cleanup()
})

describe('GenerationControlPanel', () => {
  it('shows OpenCode session controls in the generation area', () => {
    render(
      <GenerationControlPanel
        canGenerateNext
        estimateDraftUsage={() => ({
          estimatedAnswerInputTokens: 0,
          estimatedNextPromptTokens: 0,
          estimatedNextOutputTokens: 0,
        })}
        onGenerateNext={vi.fn()}
        onOpenCodeSend={vi.fn()}
        onOpenCodeRegenerateCurrentQuestion={vi.fn()}
        onOpenCodeSkip={vi.fn()}
        opencodePlan={{
          enabled: true,
          sessionId: 'sess_123',
          pendingQuestionText: 'How is the repository bootstrapped?',
        }}
        projectStarted
        savedAnswer="saved answer"
        t={createTranslator('en')}
      />,
    )

    expect(screen.getByText('sess_123')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send to OpenCode' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Regenerate current question' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Skip this round' })).toBeInTheDocument()
  })

  it('shows the cleaned question text that will be sent to OpenCode', () => {
    render(
      <GenerationControlPanel
        canGenerateNext
        estimateDraftUsage={() => ({
          estimatedAnswerInputTokens: 0,
          estimatedNextPromptTokens: 0,
          estimatedNextOutputTokens: 0,
        })}
        onGenerateNext={vi.fn()}
        onOpenCodeSend={vi.fn()}
        onOpenCodeRegenerateCurrentQuestion={vi.fn()}
        onOpenCodeSkip={vi.fn()}
        opencodePlan={{
          enabled: true,
          sessionId: 'sess_123',
          pendingQuestionText: 'Based on your initial exploration, what are the core modules?',
        }}
        projectStarted
        savedAnswer="saved answer"
        t={createTranslator('en')}
      />,
    )

    expect(screen.getByText('Based on your initial exploration, what are the core modules?')).toBeInTheDocument()
    expect(screen.queryByText(/^Q3:/)).not.toBeInTheDocument()
  })

  it('passes human review details when users regenerate the current question', () => {
    const onOpenCodeRegenerateCurrentQuestion = vi.fn()

    render(
      <GenerationControlPanel
        canGenerateNext
        estimateDraftUsage={() => ({
          estimatedAnswerInputTokens: 0,
          estimatedNextPromptTokens: 0,
          estimatedNextOutputTokens: 0,
        })}
        onGenerateNext={vi.fn()}
        onOpenCodeSend={vi.fn()}
        onOpenCodeRegenerateCurrentQuestion={onOpenCodeRegenerateCurrentQuestion}
        onOpenCodeSkip={vi.fn()}
        opencodePlan={{
          enabled: true,
          sessionId: 'sess_123',
          pendingQuestionText: 'Original question',
        }}
        projectStarted
        savedAnswer="saved answer"
        t={createTranslator('en')}
      />,
    )

    fireEvent.change(screen.getByDisplayValue('No explicit review'), {
      target: { value: 'drifted' },
    })
    fireEvent.change(screen.getByDisplayValue('No explicit focus'), {
      target: { value: 'architecture' },
    })
    fireEvent.change(screen.getByPlaceholderText('Optional note: what is still unclear, where the interview drifted, or which branch matters most.'), {
      target: { value: 'Focus on module wiring' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate current question' }))

    expect(onOpenCodeRegenerateCurrentQuestion).toHaveBeenCalledWith({
      verdict: 'drifted',
      direction: 'continue',
      preferred_next_focus: 'architecture',
      note: 'Focus on module wiring',
      phase: null,
      phase_ready: null,
    })
  })
})
