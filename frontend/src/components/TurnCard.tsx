import type { TurnRead } from '../types/api'
import { formatTimestamp } from '../utils/format'
import { normalizeAnswerText, normalizeQuestionText } from '../utils/text'
import { summarizeOperationUsage } from '../utils/tokens'
import { TokenUsagePanel } from './TokenUsagePanel'

type TurnCardProps = {
  copyLabel?: string | null
  isLatestActiveTurn?: boolean
  onCopyLatestQuestion?: (text: string) => Promise<void> | void
  turn: TurnRead
}

export function TurnCard({
  copyLabel = null,
  isLatestActiveTurn = false,
  onCopyLatestQuestion,
  turn,
}: TurnCardProps) {
  const normalizedQuestion = normalizeQuestionText(turn.question_text)
  const normalizedAnswer = normalizeAnswerText(turn.answer_text)
  const waitingForAnswer = !turn.answer_text
  const usageByOperation = summarizeOperationUsage(turn)

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
              <button
                type="button"
                className="rounded-full border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400"
                onClick={() => void onCopyLatestQuestion?.(turn.question_text_for_copy)}
              >
                {copyLabel === 'Copied' ? copyLabel : 'Copy latest question'}
              </button>
            ) : null}
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                waitingForAnswer
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-emerald-100 text-emerald-800'
              }`}
            >
              {waitingForAnswer ? 'Waiting for answer' : 'Answered'}
            </span>
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
            className={`mt-3 rounded-2xl border px-4 py-4 ${
              waitingForAnswer
                ? 'border-dashed border-amber-200 bg-amber-50/60'
                : 'border-slate-200 bg-slate-50/70'
            }`}
          >
            <p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">
              {waitingForAnswer
                ? 'Waiting for the latest pasted answer.'
                : normalizedAnswer}
            </p>
            {turn.answer_summary && !waitingForAnswer ? (
              <p className="mt-3 text-xs leading-6 text-slate-500">
                Stored compact summary available for future question generation.
              </p>
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
      </div>
    </article>
  )
}
