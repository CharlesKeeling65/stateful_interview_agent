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
import { buildQuestionVersionDiff, normalizeAnswerText, normalizeQuestionText } from '../utils/text'
import { formatTokenCount, summarizeOperationUsage } from '../utils/tokens'
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
  onRegenerateCurrentQuestion?: (turnId: number, humanReview?: TurnRead['human_review']) => Promise<void> | void
  regenerateWorking?: boolean
  run?: RunRead | null
  t: Translator
  turn: TurnRead
}

export const TurnCard = memo(function TurnCard({
  copyLabel = null,
  isLatestActiveTurn = false,
  locale = 'en',
  onCopyLatestQuestion,
  onRegenerateCurrentQuestion,
  regenerateWorking = false,
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
  const [reviewExpanded, setReviewExpanded] = useState(false)
  const [versionHistoryExpanded, setVersionHistoryExpanded] = useState(false)
  const [reviewVerdict, setReviewVerdict] = useState<'' | 'sufficient' | 'insufficient' | 'drifted'>('')
  const [reviewDirection, setReviewDirection] = useState<'continue' | 'redirect'>('continue')
  const [preferredNextFocus, setPreferredNextFocus] = useState('')
  const [reviewNote, setReviewNote] = useState('')
  const [phaseReady, setPhaseReady] = useState(false)
  const showingCollapsedAnswer = shouldCollapseAnswer && !answerExpanded
  function buildHumanReviewSignal() {
    if (!reviewVerdict && !preferredNextFocus.trim() && !reviewNote.trim() && !phaseReady) {
      return {
        direction: reviewDirection,
      }
    }

    return {
      verdict: reviewVerdict || null,
      direction: reviewDirection,
      preferred_next_focus: preferredNextFocus.trim() || null,
      note: reviewNote.trim() || null,
      phase_ready: phaseReady || null,
    }
  }

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
            <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
              {t('transcript.version')} {turn.current_question_version_no}
            </span>
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
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[0.72rem] font-semibold text-slate-700">
              {t('transcript.regeneratedTimes')}: {turn.question_regeneration_count}
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[0.72rem] font-semibold text-slate-700">
              {t('transcript.humanRegenTokens')}: {formatTokenCount(turn.human_intervention_regeneration_usage_summary.total_tokens, locale)}
            </span>
          </div>
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

        {turn.question_versions.length > 1 ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-4">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 text-left"
              onClick={() => setVersionHistoryExpanded((current) => !current)}
            >
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  {t('transcript.versionHistory')}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  {turn.question_versions.length} {locale === 'zh-CN' ? '个版本' : 'versions'}
                </p>
              </div>
              <ChevronDownIcon className={`size-4 text-slate-500 transition ${versionHistoryExpanded ? 'rotate-180' : ''}`} />
            </button>

            {versionHistoryExpanded ? (
              <div className="mt-4 space-y-3">
                {turn.question_versions.map((version) => (
                  <div key={version.id} className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-[0.72rem] font-semibold text-slate-700">
                          {t('transcript.version')} {version.version_no}
                        </span>
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-[0.72rem] font-semibold text-slate-700">
                          {version.generation_kind}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500">{formatTimestamp(version.created_at, locale)}</span>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-slate-800">
                      {version.question_text}
                    </p>
                    {version.version_no > 1 ? (() => {
                      const previousVersion = turn.question_versions.find((item) => item.version_no === version.version_no - 1)
                      if (!previousVersion) {
                        return null
                      }
                      const diff = buildQuestionVersionDiff(previousVersion.question_text, version.question_text)
                      if (!diff.hasChanges) {
                        return null
                      }

                      return (
                        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                          <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
                            {t('transcript.versionDiff')}
                          </p>
                          {diff.sharedPrefix || diff.sharedSuffix ? (
                            <div className="mt-3 rounded-xl bg-white px-3 py-2">
                              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                                {t('transcript.diffShared')}
                              </p>
                              <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-6 text-slate-600">
                                {[diff.sharedPrefix, diff.sharedSuffix].filter(Boolean).join(' ... ')}
                              </p>
                            </div>
                          ) : null}
                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div className="rounded-xl border border-rose-200 bg-rose-50/70 px-3 py-3">
                              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-rose-700">
                                {t('transcript.diffBefore')}
                              </p>
                              <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-6 text-rose-950">
                                {diff.before || (locale === 'zh-CN' ? '无' : 'None')}
                              </p>
                            </div>
                            <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 px-3 py-3">
                              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-emerald-700">
                                {t('transcript.diffAfter')}
                              </p>
                              <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-6 text-emerald-950">
                                {diff.after || (locale === 'zh-CN' ? '无' : 'None')}
                              </p>
                            </div>
                          </div>
                        </div>
                      )
                    })() : null}
                    {version.human_review?.note ? (
                      <p className="mt-2 text-xs leading-6 text-slate-500">{version.human_review.note}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {waitingForAnswer && isLatestActiveTurn && onRegenerateCurrentQuestion ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-4">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 text-left"
              onClick={() => setReviewExpanded((current) => !current)}
            >
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-amber-700">
                  {t('transcript.reviewAndRegenerate')}
                </p>
                <p className="mt-1 text-sm leading-6 text-amber-900">
                  {t('transcript.reviewAndRegenerateHint')}
                </p>
              </div>
              <ChevronDownIcon className={`size-4 text-amber-700 transition ${reviewExpanded ? 'rotate-180' : ''}`} />
            </button>

            {reviewExpanded ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <label className="text-sm text-slate-700">
                  <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Verdict
                  </span>
                  <select
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                    value={reviewVerdict}
                    onChange={(event) =>
                      setReviewVerdict(event.target.value as '' | 'sufficient' | 'insufficient' | 'drifted')
                    }
                  >
                    <option value="">{locale === 'zh-CN' ? '不设置明确评审' : 'No explicit review'}</option>
                    <option value="sufficient">{locale === 'zh-CN' ? '信息充分' : 'Sufficient'}</option>
                    <option value="insufficient">{locale === 'zh-CN' ? '信息不足' : 'Insufficient'}</option>
                    <option value="drifted">{locale === 'zh-CN' ? '已跑偏' : 'Drifted'}</option>
                  </select>
                </label>

                <label className="text-sm text-slate-700">
                  <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Direction
                  </span>
                  <select
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                    value={reviewDirection}
                    onChange={(event) => setReviewDirection(event.target.value as 'continue' | 'redirect')}
                  >
                    <option value="continue">{locale === 'zh-CN' ? '继续当前分支' : 'Continue current branch'}</option>
                    <option value="redirect">{locale === 'zh-CN' ? '调整下一问方向' : 'Redirect next question'}</option>
                  </select>
                </label>

                <label className="text-sm text-slate-700">
                  <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Preferred next focus
                  </span>
                  <select
                    className="mt-2 w-full rounded-2xl border border-slate-200 bg-white px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                    value={preferredNextFocus}
                    onChange={(event) => setPreferredNextFocus(event.target.value)}
                  >
                    <option value="">{locale === 'zh-CN' ? '不指定焦点' : 'No explicit focus'}</option>
                    <option value="panorama">{locale === 'zh-CN' ? '全景' : 'Panorama'}</option>
                    <option value="architecture">{locale === 'zh-CN' ? '架构' : 'Architecture'}</option>
                    <option value="code_detail">{locale === 'zh-CN' ? '代码细节' : 'Code detail'}</option>
                    <option value="code path">{locale === 'zh-CN' ? '代码路径' : 'Code path'}</option>
                    <option value="scenario">{locale === 'zh-CN' ? '场景' : 'Scenario'}</option>
                    <option value="use_case">{locale === 'zh-CN' ? '用例' : 'Use case'}</option>
                  </select>
                </label>

                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                  <input
                    checked={phaseReady}
                    className="size-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                    onChange={(event) => setPhaseReady(event.target.checked)}
                    type="checkbox"
                  />
                  {locale === 'zh-CN' ? '将当前阶段标记为“信息已足够”' : 'Mark the current phase as sufficiently complete'}
                </label>

                <label className="md:col-span-2 text-sm text-slate-700">
                  <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Human note
                  </span>
                  <textarea
                    className="mt-2 min-h-24 w-full rounded-[1.25rem] border border-slate-200 bg-white px-3 py-3 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                    placeholder={locale === 'zh-CN' ? '说明当前问题为何需要重生成。' : 'Explain why the current question should be regenerated.'}
                    value={reviewNote}
                    onChange={(event) => setReviewNote(event.target.value)}
                  />
                </label>

                <div className="md:col-span-2">
                  <ActionButton
                    disabled={regenerateWorking}
                    label={regenerateWorking ? `${t('transcript.regenerate')}...` : t('transcript.regenerate')}
                    onClick={() => void onRegenerateCurrentQuestion(turn.id, buildHumanReviewSignal())}
                    type="button"
                    variant="primary"
                  />
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

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
