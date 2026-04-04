import type { Locale, Translator } from '../i18n'
import type { TokenUsageSummary } from '../types/api'
import { formatTokenCount } from '../utils/tokens'

type TokenUsagePanelProps = {
  compact?: boolean
  label?: string
  locale?: Locale
  summary: TokenUsageSummary
  t: Translator
}

export function TokenUsagePanel({
  compact = false,
  label = 'Token Usage',
  locale = 'en',
  summary,
  t,
}: TokenUsagePanelProps) {
  const wrapperClass = compact
    ? 'rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3'
    : 'rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4'

  return (
    <div className={wrapperClass}>
      <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div>
          <p className="text-[0.64rem] uppercase tracking-[0.18em] text-slate-500">{t('token.input')}</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {formatTokenCount(summary.prompt_tokens, locale)}
          </p>
        </div>
        <div>
          <p className="text-[0.64rem] uppercase tracking-[0.18em] text-slate-500">{t('token.output')}</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {formatTokenCount(summary.completion_tokens, locale)}
          </p>
        </div>
        <div>
          <p className="text-[0.64rem] uppercase tracking-[0.18em] text-slate-500">{t('token.total')}</p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            {formatTokenCount(summary.total_tokens, locale)}
          </p>
        </div>
      </div>
      {summary.estimated_total_tokens > 0 ? (
        <p className="mt-3 text-xs leading-6 text-slate-500">
          {t('token.estimated')} {formatTokenCount(summary.estimated_total_tokens, locale)}.
        </p>
      ) : null}
    </div>
  )
}
