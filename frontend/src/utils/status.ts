import type { ProjectRead, ProjectStatusResponse } from '../types/api'

export function formatBooleanLabel(
  value: boolean | null | undefined,
  options?: {
    trueLabel?: string
    falseLabel?: string
    nullLabel?: string
  },
) {
  if (value == null) {
    return options?.nullLabel ?? 'Not available'
  }

  return value
    ? options?.trueLabel ?? 'Yes'
    : options?.falseLabel ?? 'No'
}

export function isProjectFinished(
  project: ProjectRead | null,
  status: ProjectStatusResponse | null,
) {
  return (status?.status ?? project?.status) === 'finished'
}

export function hasInterviewStarted(project: ProjectRead | null) {
  return Boolean(project && project.turn_count > 0)
}

export function getRuntimeStatusLabel(
  project: ProjectRead | null,
  status: ProjectStatusResponse | null,
) {
  const currentStatus = status?.status ?? project?.status
  if (currentStatus === 'finished') {
    return 'Finished'
  }
  if (project && project.turn_count > 0) {
    return 'In progress'
  }
  if (project) {
    return 'Ready to start'
  }
  return 'No project selected'
}
