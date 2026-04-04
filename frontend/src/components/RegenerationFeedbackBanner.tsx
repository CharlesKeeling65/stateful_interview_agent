import { memo } from 'react'

import {
  getDisplayStageLabel,
  getReviewDirectionLabel,
  getReviewFocusLabel,
  getReviewVerdictLabel,
  type Locale,
  type Translator,
} from '../i18n'
import type { CurrentQuestionRegenerateResponse } from '../types/api'
import { CheckIcon, SparkIcon } from './Icons'

type RegenerationFeedbackBannerProps = {
  feedback: CurrentQuestionRegenerateResponse['applied_changes']
  locale?: Locale
  t: Translator
  tokensUsed: number
}

function Metric({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-2xl border border-teal-100 bg-white/75 px-4 py-3">
      <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-teal-700">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  )
}

export const RegenerationFeedbackBanner = memo(function RegenerationFeedbackBanner({
  feedback,
  locale = 'en',
  t,
  tokensUsed,
}: RegenerationFeedbackBannerProps) {
  const reviewState = feedback.planner_followed_review ? t('trace.reviewUsed') : t('trace.reviewPersisted')
  const questionState = feedback.question_changed ? t('trace.questionChanged') : t('trace.questionUnchanged')
  const stageState = feedback.stage_changed
    ? `${getDisplayStageLabel(feedback.previous_stage, locale)} -> ${getDisplayStageLabel(feedback.current_stage, locale)}`
    : `${t('trace.stageUnchanged')}: ${getDisplayStageLabel(feedback.current_stage, locale)}`

  return (
    <section className="rounded-[1.75rem] border border-teal-200 bg-[linear-gradient(180deg,rgba(240,253,250,0.96),rgba(255,255,255,0.98))] p-5 shadow-[0_18px_40px_rgba(20,184,166,0.12)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-teal-700">
            {t('trace.reviewAppliedTitle')}
          </p>
          <h3 className="mt-3 font-serif text-2xl text-slate-950">{reviewState}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-700">
            {t('trace.reviewAppliedCopy')}
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-teal-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-teal-800">
          <CheckIcon className="size-3.5" />
          {questionState}
        </span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Metric
          label={feedback.stage_changed ? t('trace.stageChanged') : t('trace.stageUnchanged')}
          value={stageState}
        />
        <Metric
          label={t('trace.versionMoved')}
          value={`V${feedback.question_version_before} -> V${feedback.question_version_after}`}
        />
        <Metric
          label={t('trace.regenerationMoved')}
          value={`${feedback.regeneration_count_before} -> ${feedback.regeneration_count_after}`}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {feedback.review_persisted ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <CheckIcon className="size-3.5 text-teal-600" />
            {t('trace.reviewPersisted')}
          </span>
        ) : null}
        {feedback.planner_followed_review ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <SparkIcon className="size-3.5 text-teal-600" />
            {t('trace.reviewUsed')}
          </span>
        ) : null}
        {feedback.requested_focus ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <span>{t('trace.focusApplied')}: {getReviewFocusLabel(feedback.requested_focus, locale)}</span>
          </span>
        ) : null}
        {feedback.requested_verdict ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <span>{t('trace.verdictApplied')}: {getReviewVerdictLabel(feedback.requested_verdict, locale)}</span>
          </span>
        ) : null}
        {feedback.requested_direction ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <span>{t('trace.directionApplied')}: {getReviewDirectionLabel(feedback.requested_direction, locale)}</span>
          </span>
        ) : null}
        {feedback.note_applied ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <span>{t('trace.noteApplied')}</span>
          </span>
        ) : null}
        {feedback.phase_ready_applied ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
            <span>{t('trace.phaseReadyApplied')}</span>
          </span>
        ) : null}
        <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-teal-100">
          <span>{t('trace.tokensUsed')}: {tokensUsed}</span>
        </span>
      </div>
    </section>
  )
})
