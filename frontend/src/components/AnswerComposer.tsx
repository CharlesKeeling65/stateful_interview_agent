import { useState } from 'react'

type AnswerComposerProps = {
  disabled?: boolean
  projectFinished?: boolean
  projectStarted?: boolean
  workingLabel?: string | null
  onSubmit: (answerText: string) => Promise<void> | void
}

export function AnswerComposer({
  disabled = false,
  projectFinished = false,
  projectStarted = false,
  workingLabel = null,
  onSubmit,
}: AnswerComposerProps) {
  const [answer, setAnswer] = useState('')

  async function handleSubmit() {
    if (!answer.trim()) {
      return
    }

    await onSubmit(answer)
    setAnswer('')
  }

  return (
    <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            Answer Composer
          </p>
          <h2 className="mt-3 font-serif text-2xl text-slate-950">
            Paste the latest opencode answer and advance one turn.
          </h2>
        </div>
        <button
          type="button"
          className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          onClick={() => void handleSubmit()}
          disabled={disabled || !answer.trim()}
        >
          {workingLabel ?? 'Submit Answer & Generate Next'}
        </button>
      </div>

      <textarea
        className="mt-5 min-h-48 w-full rounded-[1.75rem] border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-7 text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
        placeholder={
          projectFinished
            ? 'This interview is finished.'
            : !projectStarted
              ? 'Start the interview to receive the first question.'
              : 'Paste the latest opencode answer here...'
        }
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        disabled={disabled}
      />
      <p className="mt-3 text-sm text-slate-500">
        {projectFinished
          ? 'No more turns can be submitted after the session finishes.'
          : !projectStarted
            ? 'The composer unlocks after the first question is generated.'
            : 'Long answers are preserved as-is and normalized only for display.'}
      </p>
    </section>
  )
}
