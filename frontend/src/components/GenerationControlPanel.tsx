import { useState } from 'react'

import type { Locale, Translator } from '../i18n'
import type { HumanGateRead, HumanReviewInput, NextQuestionRequestPayload } from '../types/api'
import { formatTokenCount } from '../utils/tokens'
import { ChevronDownIcon } from './Icons'

type GenerationControlPanelProps = {
  canGenerateNext?: boolean
  disabled?: boolean
  estimateDraftUsage: (answerText: string) => {
    estimatedAnswerInputTokens: number
    estimatedNextPromptTokens: number
    estimatedNextOutputTokens: number
  }
  locale?: Locale
  pendingGate?: HumanGateRead | null
  projectFinished?: boolean
  projectStarted?: boolean
  savedAnswer?: string | null
  workingLabel?: string | null
  onGenerateNext: (payload?: NextQuestionRequestPayload) => Promise<void> | void
  t: Translator
}

export function GenerationControlPanel({
  canGenerateNext = false,
  disabled = false,
  estimateDraftUsage,
  locale = 'en',
  pendingGate = null,
  projectFinished = false,
  projectStarted = false,
  savedAnswer = null,
  workingLabel = null,
  onGenerateNext,
  t,
}: GenerationControlPanelProps) {
  const [reviewExpanded, setReviewExpanded] = useState(true)
  const [reviewVerdict, setReviewVerdict] = useState<'' | 'sufficient' | 'insufficient' | 'drifted'>('')
  const [reviewDirection, setReviewDirection] = useState<HumanReviewInput['direction']>('continue')
  const [preferredNextFocus, setPreferredNextFocus] = useState('')
  const [reviewNote, setReviewNote] = useState('')
  const [phaseCorrection, setPhaseCorrection] = useState('')
  const [phaseReady, setPhaseReady] = useState(false)
  const [gateAction, setGateAction] = useState('')
  const [gateFocus, setGateFocus] = useState('')
  const [gateNote, setGateNote] = useState('')

  function buildHumanReviewSignal(): HumanReviewInput | null {
    if (!reviewVerdict && !preferredNextFocus.trim() && !reviewNote.trim() && !phaseReady && !phaseCorrection) {
      return null
    }

    return {
      verdict: reviewVerdict || null,
      direction: reviewDirection,
      preferred_next_focus: preferredNextFocus.trim() || null,
      note: reviewNote.trim() || null,
      phase: phaseCorrection || null,
      phase_ready: phaseReady || null,
    }
  }

  const estimate = estimateDraftUsage(savedAnswer ?? '')
  const hasPendingGate = Boolean(pendingGate)
  const effectiveCanGenerateNext = hasPendingGate ? true : canGenerateNext

  function buildNextPayload(): NextQuestionRequestPayload {
    if (pendingGate) {
      const fallbackAction = pendingGate.default_action || pendingGate.options[0]?.action || 'continue'
      return {
        human_gate: {
          gate_id: pendingGate.gate_id,
          action: gateAction || fallbackAction,
          preferred_next_focus: gateFocus.trim() || null,
          note: gateNote.trim() || null,
          phase_ready: phaseReady || null,
        },
      }
    }

    return {
      human_review: buildHumanReviewSignal(),
    }
  }

  return (
    <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
            {t('generation.section')}
          </p>
          <h2 className="mt-3 font-serif text-2xl text-slate-950">
            {t('generation.title')}
          </h2>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            {t('generation.copy')}
          </p>
        </div>
        <button
          type="button"
          className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          onClick={() => void onGenerateNext(buildNextPayload())}
          disabled={disabled || !effectiveCanGenerateNext}
        >
          {workingLabel ?? t('generation.submit')}
        </button>
      </div>

      {pendingGate ? (
        <div className="mt-4 rounded-[1.5rem] border border-amber-200 bg-amber-50/80 px-4 py-4">
          <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-amber-700">
            {locale === 'zh-CN' ? '人工决策关卡' : 'Human Decision Gate'}
          </p>
          <p className="mt-2 text-sm leading-6 text-amber-950">{pendingGate.reason}</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {locale === 'zh-CN' ? '决策' : 'Decision'}
              </span>
              <select
                className="mt-2 w-full rounded-2xl border border-amber-200 bg-white px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={gateAction}
                onChange={(event) => setGateAction(event.target.value)}
              >
                <option value="">{locale === 'zh-CN' ? '使用默认决策' : 'Use default action'}</option>
                {pendingGate.options.map((option) => (
                  <option key={option.action} value={option.action}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.focus')}
              </span>
              <input
                className="mt-2 w-full rounded-2xl border border-amber-200 bg-white px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                placeholder={locale === 'zh-CN' ? '可选：下一问聚焦点' : 'Optional next focus'}
                value={gateFocus}
                onChange={(event) => setGateFocus(event.target.value)}
              />
            </label>
            <label className="md:col-span-2 text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.note')}
              </span>
              <textarea
                className="mt-2 min-h-24 w-full rounded-[1.25rem] border border-amber-200 bg-white px-3 py-3 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                placeholder={locale === 'zh-CN' ? '记录你的判断或重定向理由' : 'Capture the decision or redirection rationale'}
                value={gateNote}
                onChange={(event) => setGateNote(event.target.value)}
              />
            </label>
          </div>
        </div>
      ) : null}

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
              {t('generation.reviewHint')}
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

            <label className="text-sm text-slate-700">
              <span className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {t('composer.phaseCorrection')}
              </span>
              <select
                className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={phaseCorrection}
                onChange={(event) => setPhaseCorrection(event.target.value)}
              >
                <option value="">{t('composer.noPhaseCorrection')}</option>
                <option value="Panorama Mapping">{locale === 'zh-CN' ? '全景地图构建' : 'Panorama Mapping'}</option>
                <option value="Architecture Understanding">{locale === 'zh-CN' ? '架构理解' : 'Architecture Understanding'}</option>
                <option value="Code Detail Completion">{locale === 'zh-CN' ? '代码细节补全' : 'Code Detail Completion'}</option>
                <option value="Use Cases & Scenarios">{locale === 'zh-CN' ? '用例与场景' : 'Use Cases & Scenarios'}</option>
                <option value="Final Wrap-up">{locale === 'zh-CN' ? '最终收口' : 'Final Wrap-up'}</option>
              </select>
            </label>

            <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 md:col-span-2">
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
          {t('generation.estimate')}
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
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
      </div>

      <p className="mt-3 text-sm text-slate-500">
        {projectFinished
          ? t('composer.finishedHint')
          : !projectStarted
            ? t('composer.lockedHint')
            : effectiveCanGenerateNext
              ? t('generation.readyHint')
              : t('generation.lockedHint')}
      </p>
    </section>
  )
}
