import type { Locale } from '../i18n'
import type { ProjectRead, ProjectStatusResponse } from '../types/api'
import { getRuntimeStatusLabel, hasInterviewStarted, isProjectFinished } from '../utils/status'
import { CheckIcon, ClockIcon, SparkIcon } from './Icons'

type ProjectStatusBadgeProps = {
  locale?: Locale
  project: ProjectRead | null
  status?: ProjectStatusResponse | null
}

export function ProjectStatusBadge({
  locale = 'en',
  project,
  status = null,
}: ProjectStatusBadgeProps) {
  const finished = isProjectFinished(project, status)
  const started = hasInterviewStarted(project)
  const label = getRuntimeStatusLabel(project, status, locale)
  const toneClassName = finished
    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : started
      ? 'border-sky-200 bg-sky-50 text-sky-800'
      : 'border-amber-200 bg-amber-50 text-amber-800'

  const icon = finished ? (
    <CheckIcon className="size-3.5" />
  ) : started ? (
    <SparkIcon className="size-3.5" />
  ) : (
    <ClockIcon className="size-3.5" />
  )

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] ${toneClassName}`}
    >
      {icon}
      {label}
    </span>
  )
}
