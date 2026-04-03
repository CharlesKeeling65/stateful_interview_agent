import { memo, useState } from 'react'

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
  onCopyLatestQuestion?: (text: string) => Promise<void> | void
  run?: RunRead | null
  turn: TurnRead
}

export const TurnCard = memo(function TurnCard({
  copyLabel = null,
  isLatestActiveTurn = false,
  onCopyLatestQuestion,
  run = null,
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
            <p className="mt-2 text-sm font-medium text-slate-700">{turn.stage}</p>
            <p className="mt-2 text-xs text-slate-500">{formatTimestamp(turn.created_at)}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isLatestActiveTurn ? (
              <ActionButton
                aria-label="Copy latest question"
                icon={<CopyIcon />}
                label={copyLabel === 'Copied' ? 'Copied' : 'Copy question'}
                onClick={() => void onCopyLatestQuestion?.(turn.question_text_for_copy)}
                title="Copy latest question"
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
              {waitingForAnswer ? 'Waiting' : 'Answered'}
            </span>
            {run ? (
              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
                Trace {formatDurationMs(run.duration_ms)}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="space-y-5 px-5 py-5">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            Question
          </p>
          <p className="mt-3 whitespace-pre-wrap break-words text-base leading-7 text-slate-950">
            {normalizedQuestion}
          </p>
        </div>

        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            Answer
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
                  ? 'Waiting for the latest pasted answer.'
                  : normalizedAnswer}
              </p>
              {showingCollapsedAnswer ? (
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-50/95 to-transparent" />
              ) : null}
            </div>
            {turn.answer_summary && !waitingForAnswer ? (
              <p className="mt-3 text-xs leading-6 text-slate-500">
                Stored compact summary available for future question generation.
              </p>
            ) : null}
            {shouldCollapseAnswer ? (
              <div className="mt-4">
                <ActionButton
                  aria-label={answerExpanded ? 'Collapse answer text' : 'Expand answer text'}
                  icon={
                    <ChevronDownIcon
                      className={`size-4 transition ${answerExpanded ? 'rotate-180' : ''}`}
                    />
                  }
                  label={answerExpanded ? 'Show less' : 'Show more'}
                  onClick={() => setAnswerExpanded((current) => !current)}
                  title={answerExpanded ? 'Collapse answer' : 'Expand answer'}
                  type="button"
                />
              </div>
            ) : null}
          </div>
        </div>

        {turn.total_tokens > 0 ? (
          <TokenUsagePanel
            compact
            label="Turn Token Usage"
            summary={{
              prompt_tokens: turn.prompt_tokens,
              completion_tokens: turn.completion_tokens,
              total_tokens: turn.total_tokens,
              estimated_total_tokens: turn.llm_usages
                .filter((usage) => usage.is_estimated)
                .reduce((sum, usage) => sum + usage.total_tokens, 0),
            }}
          />
        ) : null}

        {Object.entries(usageByOperation).length > 1 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {Object.entries(usageByOperation).map(([operationType, usageSummary]) => (
              <TokenUsagePanel
                key={operationType}
                compact
                label={operationType.replace(/_/g, ' ')}
                summary={usageSummary}
              />
            ))}
          </div>
        ) : null}

        {run ? <ExecutionTraceSection run={run} /> : null}
      </div>
    </article>
  )
})
