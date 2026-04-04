import { memo, useMemo, useState } from 'react'

import { getRunStatusLabel, getStepStatusLabel, type Locale, type Translator } from '../i18n'
import type { RunRead, RunStepRead } from '../types/api'
import { formatDurationMs } from '../utils/format'
import {
  CheckIcon,
  ChevronDownIcon,
  ClockIcon,
  SparkIcon,
  AlertTriangleIcon,
} from './Icons'
import { PretextElapsedTime } from './pretext/PretextElapsedTime'
import { PretextLiveText } from './pretext/PretextLiveText'

type ExecutionTraceSectionProps = {
  defaultExpanded?: boolean
  locale?: Locale
  run: RunRead
  t: Translator
  title?: string
}

function getStatusIcon(step: RunStepRead | RunRead) {
  if (step.status === 'failed') {
    return <AlertTriangleIcon className="size-4" />
  }
  if (step.status === 'completed') {
    return <CheckIcon className="size-4" />
  }
  if (step.status === 'running') {
    return <SparkIcon className="size-4 animate-pulse" />
  }
  return <ClockIcon className="size-4" />
}

function StepRow({
  isCurrent,
  locale,
  step,
  t,
}: {
  isCurrent: boolean
  locale: Locale
  step: RunStepRead
  t: Translator
}) {
  const statusClassName =
    step.status === 'failed'
      ? 'border-rose-200 bg-rose-50 text-rose-800'
      : step.status === 'completed'
        ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
        : step.status === 'running'
          ? 'border-amber-200 bg-amber-50 text-amber-800'
          : 'border-slate-200 bg-slate-50 text-slate-600'

  return (
    <div className={`rounded-2xl border px-4 py-3 ${statusClassName}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {getStatusIcon(step)}
            <p className="text-sm font-semibold">{step.label}</p>
            {isCurrent ? (
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-[0.64rem] font-semibold uppercase tracking-[0.18em]">
                {t('trace.live')}
              </span>
            ) : null}
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-[0.64rem] font-semibold uppercase tracking-[0.18em]">
              {getStepStatusLabel(step.status, locale)}
            </span>
          </div>
          {step.description ? (
            <p className="mt-2 text-xs leading-6 opacity-85">{step.description}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.72rem] uppercase tracking-[0.16em] opacity-80">
            {step.method ? <span>{step.method}</span> : null}
            {step.next_step_hint ? <span>{t('trace.next')}: {step.next_step_hint}</span> : null}
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] opacity-75">{t('trace.duration')}</p>
          {step.status === 'running' ? (
            <PretextElapsedTime
              className="mt-1 block text-sm font-semibold"
              locale={locale}
              startedAt={step.started_at}
            />
          ) : (
            <p className="mt-1 text-sm font-semibold">{formatDurationMs(step.duration_ms, locale)}</p>
          )}
          {step.total_tokens > 0 ? (
            <p className="mt-1 text-xs opacity-75">
              {step.total_tokens} {locale === 'zh-CN' ? 'tokens' : 'tokens'}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export const ExecutionTraceSection = memo(function ExecutionTraceSection({
  defaultExpanded = false,
  locale = 'en',
  run,
  t,
  title,
}: ExecutionTraceSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const completedSteps = useMemo(
    () => run.steps.filter((step) => step.status === 'completed').length,
    [run.steps],
  )
  const currentStep = useMemo(
    () =>
      run.steps.find((step) => step.status === 'running') ??
      run.steps[run.steps.length - 1] ??
      null,
    [run.steps],
  )

  const runStatusLabel = getRunStatusLabel(run.status, locale)

  return (
    <section className="rounded-[1.5rem] border border-slate-200 bg-slate-50/75">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded((current) => !current)}
      >
        <div className="min-w-0">
          <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
            {title ?? t('trace.title')}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-700">
            <span className="font-semibold text-slate-950">{runStatusLabel}</span>
            <span className="text-slate-400">•</span>
            <span>{completedSteps}/{Math.max(run.step_count, run.steps.length)} {t('trace.steps')}</span>
            {currentStep ? (
              <>
                <span className="text-slate-400">•</span>
                {run.status === 'running' ? (
                  <PretextLiveText text={currentStep.label} />
                ) : (
                  <span>{currentStep.label}</span>
                )}
              </>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
              {t('trace.total')}
            </p>
            {run.status === 'running' ? (
              <PretextElapsedTime className="mt-1 block text-sm font-semibold text-slate-950" locale={locale} startedAt={run.started_at} />
            ) : (
              <p className="mt-1 text-sm font-semibold text-slate-950">{formatDurationMs(run.duration_ms, locale)}</p>
            )}
          </div>
          <ChevronDownIcon className={`size-4 text-slate-500 transition ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {expanded ? (
        <div className="space-y-3 border-t border-slate-200 px-4 py-4">
          {run.steps.map((step) => (
            <StepRow
              key={step.id}
              locale={locale}
              step={step}
              isCurrent={run.status === 'running' && step.id === currentStep?.id}
              t={t}
            />
          ))}
        </div>
      ) : null}
    </section>
  )
})

type ActiveRunPanelProps = {
  run: RunRead
}

export const ActiveRunPanel = memo(function ActiveRunPanel({
  locale = 'en',
  run,
  t,
}: ActiveRunPanelProps & { locale?: Locale; t: Translator }) {
  return (
    <div className="rounded-[1.75rem] border border-amber-200 bg-[linear-gradient(180deg,rgba(255,251,235,0.96),rgba(255,255,255,0.98))] p-5 shadow-[0_18px_40px_rgba(251,191,36,0.12)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-amber-700">
            {t('trace.active')}
          </p>
          <h3 className="mt-3 font-serif text-2xl text-slate-950">{t('trace.activeTitle')}</h3>
          <p className="mt-2 text-sm leading-7 text-slate-700">
            {t('trace.activeCopy')}
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-800">
          <SparkIcon className="size-3.5 animate-pulse" />
          {t('trace.running')}
        </span>
      </div>

      <div className="mt-4">
        <ExecutionTraceSection defaultExpanded locale={locale} run={run} t={t} title={t('trace.currentRun')} />
      </div>
    </div>
  )
})
