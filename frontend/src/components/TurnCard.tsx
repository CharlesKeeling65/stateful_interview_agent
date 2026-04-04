import { memo, useState } from 'react'

import {
  getDisplayStageLabel,
  getOperationTypeLabel,
  getQuestionIntentLabel,
  getReviewDirectionLabel,
  getReviewVerdictLabel,
  type Locale,
  type Translator,
} from '../i18n'
import type { RunRead, TurnRead } from '../types/api'
import { formatDurationMs, formatTimestamp } from '../utils/format'
import { normalizeAnswerText, normalizeQuestionText } from '../utils/text'
import { summarizeOperationUsage } from '../utils/tokens'
import { ActionButton } from './ActionButton'
import { CheckIcon, ChevronDownIcon, ClockIcon, CopyIcon } from './Icons'
import { ExecutionTraceSection } from './ExecutionTraceSection'
import { TokenUsagePanel } from './TokenUsagePanel'

const ANSWER_COLLAPSE_THRESHOLD = 680

type TurnCardProps = {
  copyLabel?: string | null
  isLatestActiveTurn?: boolean
  locale?: Locale
  onCopyLatestQuestion?: (text: string) => Promise<void> | void
  run?: RunRead | null
  t: Translator
  turn: TurnRead
}

export const TurnCard = memo(function TurnCard({
  copyLabel = null,
  isLatestActiveTurn = false,
  locale = 'en',
  onCopyLatestQuestion,
  run = null,
  t,
  turn,
}: TurnCardProps) {
  const normalizedQuestion = normalizeQuestionText(turn.question_text)
  const normalizedAnswer = normalizeAnswerText(turn.answer_text)
  const waitingForAnswer = !turn.answer_text
  const usageByOperation = summarizeOperationUsage(turn)
  const shouldCollapseAnswer =
    !waitingForAnswer && normalizedAnswer.length > ANSWER_COLLAPSE_THRESHOLD
  const [answerExpanded, setAnswerExpanded] = useState(false)
  const showingCollapsedAnswer = shouldCollapseAnswer && !answerExpanded

  return (
    <article
      className={`overflow-hidden rounded-[1.75rem] border shadow-[0_14px_30px_rgba(148,163,184,0.12)] ${
        waitingForAnswer
          ? 'border-amber-200 bg-[linear-gradient(180deg,rgba(255,251,235,0.96),rgba(255,255,255,0.98))]'
          : 'border-slate-200 bg-white'
      }`}
    >
      <div
        className={`border-b px-5 py-4 ${
          waitingForAnswer
            ? 'border-amber-100 bg-amber-50/70'
            : 'border-slate-100 bg-slate-50/80'
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              Turn {turn.turn_no}
            </p>
            <p className="mt-2 text-sm font-medium text-slate-700">{getDisplayStageLabel(turn.stage, locale)}</p>
            <p className="mt-2 text-xs text-slate-500">{formatTimestamp(turn.created_at, locale)}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isLatestActiveTurn ? (
              <ActionButton
                aria-label={t('transcript.copyLatest')}
                icon={<CopyIcon />}
                label={copyLabel === 'Copied' ? t('transcript.copied') : t('transcript.copyLatest')}
                onClick={() => void onCopyLatestQuestion?.(turn.question_text_for_copy)}
                title={t('transcript.copyLatest')}
                type="button"
              />
            ) : null}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                waitingForAnswer
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-emerald-100 text-emerald-800'
              }`}
            >
              {waitingForAnswer ? <ClockIcon className="size-3.5" /> : <CheckIcon className="size-3.5" />}
              {waitingForAnswer ? t('transcript.waiting') : t('transcript.answered')}
            </span>
            {run ? (
              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
                {t('transcript.trace')} {formatDurationMs(run.duration_ms, locale)}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="space-y-5 px-5 py-5">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            {t('transcript.question')}
          </p>
          <p className="mt-3 whitespace-pre-wrap break-words text-base leading-7 text-slate-950">
            {normalizedQuestion}
          </p>
          {turn.question_plan ? (
            <div className="mt-3 rounded-2xl border border-sky-200 bg-sky-50/70 px-4 py-3">
              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-sky-700">
                {t('transcript.whyThisQuestion')}
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-sky-800">
                {turn.question_plan.phase ? (
                  <span className="rounded-full bg-white/80 px-3 py-1">
                    {getDisplayStageLabel(turn.question_plan.phase, locale)}
                  </span>
                ) : null}
                {turn.question_plan.question_intent ? (
                  <span className="rounded-full bg-white/80 px-3 py-1">
                    {getQuestionIntentLabel(turn.question_plan.question_intent, locale)}
                  </span>
                ) : null}
                {turn.question_plan.selected_framework_gap ? (
                  <span className="rounded-full bg-white/80 px-3 py-1">
                    {locale === 'zh-CN' ? '缺口' : 'Gap'}: {turn.question_plan.selected_framework_gap.replace(/_/g, ' ')}
                  </span>
                ) : null}
                {turn.question_plan.human_review_applied ? (
                  <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800">
                    {t('transcript.followedReview')}
                  </span>
                ) : null}
                {turn.question_plan.drift_detected ? (
                  <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">
                    {t('transcript.driftRepair')}
                  </span>
                ) : null}
              </div>
              {turn.question_plan.why_this_question ? (
                <p className="mt-3 text-sm leading-6 text-sky-950">
                  {turn.question_plan.why_this_question}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            {t('transcript.answer')}
          </p>
          <div
            className={`relative mt-3 rounded-2xl border px-4 py-4 ${
              waitingForAnswer
                ? 'border-dashed border-amber-200 bg-amber-50/60'
                : 'border-slate-200 bg-slate-50/70'
            }`}
          >
            <div className="relative">
              <p
                className={`whitespace-pre-wrap break-words text-sm leading-7 text-slate-700 ${
                  showingCollapsedAnswer ? 'max-h-44 overflow-hidden' : ''
                }`}
              >
                {waitingForAnswer
                  ? t('transcript.answerWaiting')
                  : normalizedAnswer}
              </p>
              {showingCollapsedAnswer ? (
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-50/95 to-transparent" />
              ) : null}
            </div>
            {turn.answer_summary && !waitingForAnswer ? (
              <p className="mt-3 text-xs leading-6 text-slate-500">
                {t('transcript.summaryStored')}
              </p>
            ) : null}
            {shouldCollapseAnswer ? (
              <div className="mt-4">
                <ActionButton
                  aria-label={answerExpanded ? t('transcript.showLess') : t('transcript.showMore')}
                  icon={
                    <ChevronDownIcon
                      className={`size-4 transition ${answerExpanded ? 'rotate-180' : ''}`}
                    />
                  }
                  label={answerExpanded ? t('transcript.showLess') : t('transcript.showMore')}
                  onClick={() => setAnswerExpanded((current) => !current)}
                  title={answerExpanded ? t('transcript.showLess') : t('transcript.showMore')}
                  type="button"
                />
              </div>
            ) : null}
          </div>
        </div>

        {turn.human_review ? (
          <div className="rounded-2xl border border-indigo-200 bg-indigo-50/70 px-4 py-4">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-indigo-700">
              {t('transcript.humanReview')}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-indigo-800">
              {turn.human_review.verdict ? (
                <span className="rounded-full bg-white/80 px-3 py-1">
                  {getReviewVerdictLabel(turn.human_review.verdict, locale)}
                </span>
              ) : null}
              <span className="rounded-full bg-white/80 px-3 py-1">
                {getReviewDirectionLabel(turn.human_review.direction, locale)}
              </span>
              {turn.human_review.preferred_next_focus ? (
                <span className="rounded-full bg-white/80 px-3 py-1">
                  {locale === 'zh-CN' ? '焦点' : 'Focus'}: {turn.human_review.preferred_next_focus}
                </span>
              ) : null}
            </div>
            {turn.human_review.note ? (
              <p className="mt-3 text-sm leading-7 text-indigo-950">{turn.human_review.note}</p>
            ) : null}
            {turn.human_review.phase_ready ? (
              <p className="mt-2 text-xs leading-6 text-indigo-700">
                {t('transcript.phaseReady')}
              </p>
            ) : null}
          </div>
        ) : null}

        {turn.total_tokens > 0 ? (
          <TokenUsagePanel
            compact
            label={t('transcript.turnUsage')}
            locale={locale}
            summary={{
              prompt_tokens: turn.prompt_tokens,
              completion_tokens: turn.completion_tokens,
              total_tokens: turn.total_tokens,
              estimated_total_tokens: turn.llm_usages
                .filter((usage) => usage.is_estimated)
                .reduce((sum, usage) => sum + usage.total_tokens, 0),
            }}
            t={t}
          />
        ) : null}

        {Object.entries(usageByOperation).length > 1 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {Object.entries(usageByOperation).map(([operationType, usageSummary]) => (
              <TokenUsagePanel
                key={operationType}
                compact
                label={getOperationTypeLabel(operationType, locale)}
                locale={locale}
                summary={usageSummary}
                t={t}
              />
            ))}
          </div>
        ) : null}

        {run ? <ExecutionTraceSection locale={locale} run={run} t={t} /> : null}
      </div>
    </article>
  )
})
