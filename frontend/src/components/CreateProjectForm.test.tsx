import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createTranslator } from '../i18n'
import { CreateProjectForm } from './CreateProjectForm'

describe('CreateProjectForm', () => {
  it('creates projects with a valid interview agent mode and OpenCode answers enabled', () => {
    const onCreate = vi.fn()

    render(
      <CreateProjectForm
        onCreate={onCreate}
        onCreateDemo={vi.fn()}
        t={createTranslator('en')}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('Stateful Interview Demo'), {
      target: { value: 'Plan Mode Project' },
    })
    fireEvent.submit(screen.getByRole('button', { name: 'Create project' }).closest('form')!)

    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        agent_mode: 'understand_current_code',
        answer_provider_type: 'opencode',
        answer_automation_enabled: true,
      }),
    )
  })
})
