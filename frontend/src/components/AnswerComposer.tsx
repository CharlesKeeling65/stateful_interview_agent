import { useState } from 'react'

import type { Locale, Translator } from '../i18n'
import type { HumanReviewInput } from '../types/api'
import { formatTokenCount } from '../utils/tokens'
import { ChevronDownIcon } from './Icons'

type AnswerComposerProps = {
  disabled?: boolean
  estimateDraftUsage: (answerText: string) => {
    estimatedAnswerInputTokens: number
    estimatedNextPromptTokens: number
    estimatedNextOutputTokens: number
  }
  projectFinished?: boolean
  projectStarted?: boolean
  workingLabel?: string | null
  locale?: Locale
  onSubmit: (answerText: string, humanReview?: HumanReviewInput | null) => Promise<void> | void
  t: Translator
}

export function AnswerComposer({
  disabled = false,
  estimateDraftUsage,
  projectFinished = false,
  projectStarted = false,
  workingLabel = null,
  locale = 'en',
  onSubmit,
  t,
}: AnswerComposerProps) {
  const [answer, setAnswer] = useState('')
  const [reviewExpanded, setReviewExpanded] = useState(false)
  const [reviewVerdict, setReviewVerdict] = useState<'' | 'sufficient' | 'insufficient' | 'drifted'>('')
  const [reviewDirection, setReviewDirection] = useState<HumanReviewInput['direction']>('continue')
  const [preferredNextFocus, setPreferredNextFocus] = useState('')
  const [reviewNote, setReviewNote] = useState('')
  const [phaseReady, setPhaseReady] = useState(false)

  function buildHumanReviewSignal(): HumanReviewInput | null {
    if (!reviewVerdict && !preferredNextFocus.trim() && !reviewNote.trim() && !phaseReady) {
      return null
    }

    return {
      verdict: reviewVerdict || null,
      direction: reviewDirection,
      preferred_next_focus: preferredNextFocus.trim() || null,
      note: reviewNote.trim() || null,
      phase_ready: phaseReady || null,
    }
  }

  async function handleSubmit() {
    if (!answer.trim()) {
      return
    }

    await onSubmit(answer, buildHumanReviewSignal())
    setAnswer('')
    setReviewVerdict('')
    setReviewDirection('continue')
    setPreferredNextFocus('')
    setReviewNote('')
    setPhaseReady(false)
    setReviewExpanded(false)
  }

  const estimate = estimateDraftUsage(answer)

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
          onClick={() => void handleSubmit()}
          disabled={disabled || !answer.trim()}
        >
          {workingLabel ?? t('composer.submit')}
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
      <div className="mt-4 rounded-[1.5rem] border border-slate-200 bg-white/80">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left"
          onClick={() => setReviewExpanded((current) => !current)}
        >
          <div>
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
              {t('composer.review')}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {t('composer.reviewHint')}
            </p>
          </div>
          <ChevronDownIcon className={`size-4 text-slate-500 transition ${reviewExpanded ? 'rotate-180' : ''}`} />
        </button>

        {reviewExpanded ? (
          <div className="grid gap-4 border-t border-slate-200 px-4 py-4 md:grid-cols-2">
            <label className="text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.verdict')}
              </span>
              <select
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={reviewVerdict}
                onChange={(event) =>
                  setReviewVerdict(event.target.value as '' | 'sufficient' | 'insufficient' | 'drifted')
                }
              >
                <option value="">{t('composer.noExplicitReview')}</option>
                <option value="sufficient">{locale === 'zh-CN' ? '信息充分' : 'Sufficient'}</option>
                <option value="insufficient">{locale === 'zh-CN' ? '信息不足' : 'Insufficient'}</option>
                <option value="drifted">{locale === 'zh-CN' ? '已跑偏' : 'Drifted'}</option>
              </select>
            </label>

            <label className="text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.direction')}
              </span>
              <select
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={reviewDirection}
                onChange={(event) => setReviewDirection(event.target.value as HumanReviewInput['direction'])}
              >
                <option value="continue">{locale === 'zh-CN' ? '继续当前分支' : 'Continue current branch'}</option>
                <option value="redirect">{locale === 'zh-CN' ? '调整下一问方向' : 'Redirect next question'}</option>
              </select>
            </label>

            <label className="text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.focus')}
              </span>
              <select
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={preferredNextFocus}
                onChange={(event) => setPreferredNextFocus(event.target.value)}
              >
                <option value="">{t('composer.noExplicitFocus')}</option>
                <option value="panorama">{locale === 'zh-CN' ? '全景' : 'Panorama'}</option>
                <option value="architecture">{locale === 'zh-CN' ? '架构' : 'Architecture'}</option>
                <option value="code_detail">{locale === 'zh-CN' ? '代码细节' : 'Code detail'}</option>
                <option value="code path">{locale === 'zh-CN' ? '代码路径' : 'Code path'}</option>
                <option value="scenario">{locale === 'zh-CN' ? '场景' : 'Scenario'}</option>
                <option value="use_case">{locale === 'zh-CN' ? '用例' : 'Use case'}</option>
              </select>
            </label>

            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
              <input
                checked={phaseReady}
                className="size-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                onChange={(event) => setPhaseReady(event.target.checked)}
                type="checkbox"
              />
              {t('composer.phaseReady')}
            </label>

            <label className="md:col-span-2 text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.note')}
              </span>
              <textarea
                className="mt-2 min-h-24 w-full rounded-[1.25rem] border border-slate-200 bg-slate-50 px-3 py-3 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                placeholder={t('composer.noteHint')}
                value={reviewNote}
                onChange={(event) => setReviewNote(event.target.value)}
              />
            </label>
          </div>
        ) : null}
      </div>
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
            : t('composer.readyHint')}
      </p>
    </section>
  )
}
