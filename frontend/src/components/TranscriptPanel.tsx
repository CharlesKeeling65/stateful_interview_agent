import { useDeferredValue } from 'react'

import type { ProjectRead, TurnRead } from '../types/api'
import { formatTimestamp } from '../utils/format'
import { normalizeAnswerText, normalizeQuestionText } from '../utils/text'

type TranscriptPanelProps = {
  project: ProjectRead | null
  turns: TurnRead[]
}

function EmptyState() {
  return (
    <div className="flex h-full min-h-96 items-center justify-center">
      <div className="max-w-md rounded-[2rem] border border-dashed border-slate-300 bg-white/70 px-8 py-10 text-center shadow-[0_22px_50px_rgba(148,163,184,0.12)] backdrop-blur">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
          Transcript
        </p>
        <h2 className="mt-3 font-serif text-3xl text-slate-950">Select a project to inspect its interview thread.</h2>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          Once the interview starts, each generated question and pasted answer will accumulate here in chronological order.
        </p>
      </div>
    </div>
  )
}

export function TranscriptPanel({ project, turns }: TranscriptPanelProps) {
  const deferredTurns = useDeferredValue(turns)

  if (!project) {
    return <EmptyState />
  }

  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-slate-500">
              Active Transcript
            </p>
            <h2 className="mt-3 font-serif text-3xl leading-tight text-slate-950">
              {project.project_name}
            </h2>
          </div>
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Current Stage</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">{project.current_stage}</p>
          </div>
        </div>
      </header>

      <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-[2rem] border border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(248,250,252,0.92))] p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="space-y-4">
          {deferredTurns.map((turn) => {
            const normalizedQuestion = normalizeQuestionText(turn.question_text)
            const normalizedAnswer = normalizeAnswerText(turn.answer_text)
            const waitingForAnswer = !turn.answer_text

            return (
              <article
                key={turn.id}
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
                    </div>
                  </div>
                </div>
              </article>
            )
          })}

          {deferredTurns.length === 0 ? (
            <div className="rounded-[1.75rem] border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-500">
              Interview not started yet. Use the left panel to start the first turn.
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
