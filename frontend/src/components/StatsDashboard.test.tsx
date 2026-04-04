import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { createTranslator } from '../i18n'
import type { ProjectRead, ProjectStatusResponse, TurnRead } from '../types/api'
import { StatsDashboard } from './StatsDashboard'

const project: ProjectRead = {
  id: 1,
  project_name: 'Alpha',
  system_prompt: 'prompt',
  current_stage: 'Architecture Understanding',
  turn_count: 3,
  status: 'active',
  total_prompt_tokens: 300,
  total_completion_tokens: 120,
  total_tokens: 420,
  estimated_total_tokens: 0,
  repository: {
    source_type: 'none',
  },
  repository_manifest: {
    file_count: 0,
    language_counts: {},
    top_level_directories: [],
    key_files: [],
    symbol_count: 0,
  },
  created_at: '2026-04-04T08:00:00',
  updated_at: '2026-04-04T10:00:00',
}

const status: ProjectStatusResponse = {
  project_id: 1,
  project_name: 'Alpha',
  status: 'active',
  current_stage: 'Architecture Understanding',
  turn_count: 3,
  minimum_goal_reached: false,
  max_turn_limit: 40,
  latest_turn_no: 3,
  latest_turn_answered: false,
  latest_question_text: 'Q3',
  latest_question_text_for_copy: 'Q3',
  latest_turn_regeneration_count: 2,
  latest_human_intervention_regeneration_usage_summary: {
    prompt_tokens: 40,
    completion_tokens: 20,
    total_tokens: 60,
    estimated_total_tokens: 0,
  },
  cumulative_generation_time_ms: 12_500,
  run_count: 4,
  average_run_duration_ms: 3_125,
  repository: {
    source_type: 'none',
  },
  repository_manifest: {
    file_count: 0,
    language_counts: {},
    top_level_directories: [],
    key_files: [],
    symbol_count: 0,
  },
  usage_summary: {
    prompt_tokens: 300,
    completion_tokens: 120,
    total_tokens: 420,
    estimated_total_tokens: 0,
  },
}

const turns: TurnRead[] = [
  {
    id: 11,
    project_id: 1,
    turn_no: 1,
    stage: 'Panorama Mapping',
    question_text: 'Q1',
    question_text_for_copy: 'Q1',
    answer_text: 'A1',
    answer_summary: 'S1',
    human_review: null,
    question_plan: null,
    current_question_version_no: 1,
    question_regeneration_count: 0,
    human_intervention_regeneration_usage_summary: {
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      estimated_total_tokens: 0,
    },
    question_versions: [],
    prompt_tokens: 100,
    completion_tokens: 30,
    total_tokens: 130,
    llm_usages: [],
    created_at: '2026-04-04T08:10:00',
  },
  {
    id: 12,
    project_id: 1,
    turn_no: 2,
    stage: 'Architecture Understanding',
    question_text: 'Q2',
    question_text_for_copy: 'Q2',
    answer_text: 'A2',
    answer_summary: 'S2',
    human_review: null,
    question_plan: null,
    current_question_version_no: 3,
    question_regeneration_count: 2,
    human_intervention_regeneration_usage_summary: {
      prompt_tokens: 40,
      completion_tokens: 20,
      total_tokens: 60,
      estimated_total_tokens: 0,
    },
    question_versions: [],
    prompt_tokens: 160,
    completion_tokens: 60,
    total_tokens: 220,
    llm_usages: [],
    created_at: '2026-04-04T09:10:00',
  },
  {
    id: 13,
    project_id: 1,
    turn_no: 3,
    stage: 'Architecture Understanding',
    question_text: 'Q3',
    question_text_for_copy: 'Q3',
    answer_text: null,
    answer_summary: null,
    human_review: null,
    question_plan: null,
    current_question_version_no: 1,
    question_regeneration_count: 0,
    human_intervention_regeneration_usage_summary: {
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      estimated_total_tokens: 0,
    },
    question_versions: [],
    prompt_tokens: 70,
    completion_tokens: 30,
    total_tokens: 100,
    llm_usages: [],
    created_at: '2026-04-04T09:40:00',
  },
]

describe('StatsDashboard', () => {
  it('renders richer chart sections for trends, composition, and stage flow', () => {
    render(
      <StatsDashboard
        locale="en"
        project={project}
        projects={[project]}
        status={status}
        t={createTranslator('en')}
        turns={turns}
      />,
    )

    expect(screen.getByText('Token composition')).toBeInTheDocument()
    expect(screen.getByText('Token trend by turn')).toBeInTheDocument()
    expect(screen.getByText('Cumulative token load')).toBeInTheDocument()
    expect(screen.getByText('Stage occupancy')).toBeInTheDocument()
    expect(screen.getByText('Stage transition network')).toBeInTheDocument()
    expect(screen.getByText('Regeneration pressure')).toBeInTheDocument()
  })
})
