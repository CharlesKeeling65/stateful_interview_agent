import { getBooleanLabel, getRuntimeStatusText, type Locale } from '../i18n'
import type { ProjectRead, ProjectStatusResponse } from '../types/api'

export function formatBooleanLabel(
  value: boolean | null | undefined,
  locale: Locale = 'en',
  options?: {
    trueLabel?: string
    falseLabel?: string
    nullLabel?: string
  },
) {
  return getBooleanLabel(value, locale, options)
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
  locale: Locale = 'en',
) {
  const currentStatus = status?.status ?? project?.status
  if (currentStatus === 'finished') {
    return getRuntimeStatusText('finished', locale)
  }
  if (project && project.turn_count > 0) {
    return getRuntimeStatusText('in_progress', locale)
  }
  if (project) {
    return getRuntimeStatusText('ready', locale)
  }
  return getRuntimeStatusText('empty', locale)
}
