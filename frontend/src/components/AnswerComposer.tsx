import { useEffect, useState } from 'react'

import type { Locale, Translator } from '../i18n'
import { normalizeAnswerText } from '../utils/text'
import { formatTokenCount } from '../utils/tokens'

type AnswerComposerProps = {
  disabled?: boolean
  estimateDraftUsage: (answerText: string) => {
    estimatedAnswerInputTokens: number
    estimatedNextPromptTokens: number
    estimatedNextOutputTokens: number
  }
  initialAnswer?: string | null
  locale?: Locale
  onSave: (answerText: string) => Promise<void> | void
  projectFinished?: boolean
  projectStarted?: boolean
  savedAnswer?: string | null
  workingLabel?: string | null
  t: Translator
}

export function AnswerComposer({
  disabled = false,
  estimateDraftUsage,
  initialAnswer = null,
  locale = 'en',
  onSave,
  projectFinished = false,
  projectStarted = false,
  savedAnswer = null,
  workingLabel = null,
  t,
}: AnswerComposerProps) {
  const [answer, setAnswer] = useState(normalizeAnswerText(initialAnswer ?? ''))

  useEffect(() => {
    setAnswer(normalizeAnswerText(initialAnswer ?? ''))
  }, [initialAnswer])

  async function handleSave() {
    if (!answer.trim()) {
      return
    }
    await onSave(answer.trim())
  }

  const estimate = estimateDraftUsage(answer)
  const answerMatchesSaved = (savedAnswer ?? '').trim() === answer.trim() && Boolean(answer.trim())

  return (
    <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            {t('composer.section')}
          </p>
          <h2 className="mt-3 font-serif text-2xl text-slate-950">
            {t('composer.title')}
          </h2>
        </div>
        <button
          type="button"
          className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          onClick={() => void handleSave()}
          disabled={disabled || !answer.trim()}
        >
          {workingLabel ?? t('composer.saveAnswer')}
        </button>
      </div>

      <textarea
        className="mt-5 min-h-48 w-full rounded-[1.75rem] border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-7 text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
        placeholder={
          projectFinished
            ? t('composer.placeholder.finished')
            : !projectStarted
              ? t('composer.placeholder.notStarted')
              : t('composer.placeholder.ready')
        }
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        disabled={disabled}
      />

      {savedAnswer?.trim() ? (
        <div className="mt-4 rounded-[1.5rem] border border-emerald-200 bg-emerald-50/80 px-4 py-3">
          <p className="text-sm leading-6 text-emerald-900">
            {answerMatchesSaved ? t('composer.answerSavedReady') : t('composer.answerEditedNotSaved')}
          </p>
        </div>
      ) : null}

      <div className="mt-4 rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
        <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
          {t('composer.estimate')}
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-[0.64rem] uppercase tracking-[0.18em] text-slate-500">{t('composer.answerInput')}</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {formatTokenCount(estimate.estimatedAnswerInputTokens, locale)}
            </p>
          </div>
          <div>
            <p className="text-[0.64rem] uppercase tracking-[0.18em] text-slate-500">{t('composer.nextPrompt')}</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {formatTokenCount(estimate.estimatedNextPromptTokens, locale)}
            </p>
          </div>
          <div>
            <p className="text-[0.64rem] uppercase tracking-[0.18em] text-slate-500">{t('composer.nextOutput')}</p>
            <p className="mt-1 text-sm font-semibold text-slate-950">
              {formatTokenCount(estimate.estimatedNextOutputTokens, locale)}
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs leading-6 text-slate-500">
          {t('composer.estimateHint')}
        </p>
      </div>

      <p className="mt-3 text-sm text-slate-500">
        {projectFinished
          ? t('composer.finishedHint')
          : !projectStarted
            ? t('composer.lockedHint')
            : t('composer.saveHint')}
      </p>
    </section>
  )
}
