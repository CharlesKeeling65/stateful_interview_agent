import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createTranslator } from '../i18n'
import type { ProjectRead, ProjectStatusResponse, TranscriptResponse } from '../types/api'
import { StatusPanel } from './StatusPanel'

const project: ProjectRead = {
  id: 5,
  project_name: 'Repo Editable Project',
  system_prompt: 'prompt',
  current_stage: 'Architecture Understanding',
  turn_count: 3,
  status: 'active',
  total_prompt_tokens: 10,
  total_completion_tokens: 5,
  total_tokens: 15,
  estimated_total_tokens: 0,
  repository: {
    source_type: 'none',
    local_path: null,
    git_url: null,
    git_ref: null,
    cache_path: null,
    commit_sha: null,
  },
  repository_manifest: {
    root_path: null,
    file_count: 0,
    language_counts: {},
    top_level_directories: [],
    key_files: [],
    symbol_count: 0,
    last_indexed_at: null,
  },
  created_at: '2026-04-05T10:00:00',
  updated_at: '2026-04-05T10:00:00',
}

const status: ProjectStatusResponse = {
  project_id: 5,
  project_name: 'Repo Editable Project',
  status: 'active',
  current_stage: 'Architecture Understanding',
  turn_count: 3,
  minimum_goal_reached: false,
  max_turn_limit: 20,
  latest_turn_no: 3,
  latest_turn_answered: true,
  latest_turn_ready_for_next_generation: true,
  latest_question_text: 'Q3',
  latest_question_text_for_copy: 'Q3',
  latest_turn_regeneration_count: 0,
  latest_human_intervention_regeneration_usage_summary: {
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    estimated_total_tokens: 0,
  },
  cumulative_generation_time_ms: 2000,
  run_count: 2,
  average_run_duration_ms: 1000,
  repository: project.repository,
  repository_manifest: project.repository_manifest,
  usage_summary: {
    prompt_tokens: 10,
    completion_tokens: 5,
    total_tokens: 15,
    estimated_total_tokens: 0,
  },
}

const transcript: TranscriptResponse = {
  project_id: 5,
  project_name: 'Repo Editable Project',
  turn_count: 3,
  usage_summary: status.usage_summary,
  transcript: 'Transcript body',
}

describe('StatusPanel', () => {
  it('lets users update repository settings during an active project', () => {
    const onUpdateRepository = vi.fn()

    render(
      <StatusPanel
        errorMessage=""
        infoMessage=""
        onCopyTranscript={() => {}}
        onExportMarkdown={() => {}}
        onExportText={() => {}}
        onStart={() => {}}
        onUpdateRepository={onUpdateRepository}
        project={project}
        status={status}
        t={createTranslator('en')}
        transcript={transcript}
        working={false}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Edit repository settings' }))
    fireEvent.change(screen.getByLabelText('Repository source'), {
      target: { value: 'local_path' },
    })
    fireEvent.change(screen.getByLabelText('Local repository path'), {
      target: { value: '/tmp/repo' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save repository settings' }))

    expect(onUpdateRepository).toHaveBeenCalledWith({
      repository: {
        source_type: 'local_path',
        local_path: '/tmp/repo',
        git_url: null,
        git_ref: null,
      },
    })
  })
})
