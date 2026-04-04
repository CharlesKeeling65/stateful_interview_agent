import type { Locale, Translator } from '../i18n'
import { getDisplayStageLabel } from '../i18n'
import type { ProjectRead, ProjectStatusResponse, TurnRead } from '../types/api'
import { buildProjectAnalytics } from '../utils/analytics'
import { formatDurationMs } from '../utils/format'
import { formatTokenCount } from '../utils/tokens'

type StatsDashboardProps = {
  locale?: Locale
  project: ProjectRead | null
  projects: ProjectRead[]
  status: ProjectStatusResponse | null
  t: Translator
  turns: TurnRead[]
}

function ChartCard({
  children,
  eyebrow,
  title,
}: {
  children: React.ReactNode
  eyebrow: string
  title: string
}) {
  return (
    <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">{eyebrow}</p>
      <h2 className="mt-3 font-serif text-2xl text-slate-950">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function EmptyStats({ t }: { t: Translator }) {
  return (
    <div className="rounded-[2rem] border border-dashed border-slate-300 bg-white/70 px-8 py-12 text-center shadow-[0_22px_50px_rgba(148,163,184,0.12)]">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
        {t('nav.analytics')}
      </p>
      <h2 className="mt-3 font-serif text-3xl text-slate-950">
        {t('analytics.emptyTitle')}
      </h2>
      <p className="mt-4 text-sm leading-7 text-slate-600">
        {t('analytics.emptyCopy')}
      </p>
    </div>
  )
}

export function StatsDashboard({
  locale = 'en',
  project,
  projects,
  status,
  t,
  turns,
}: StatsDashboardProps) {
  if (!project) {
    return <EmptyStats t={t} />
  }

  const analytics = buildProjectAnalytics(project, status, turns)
  const maxStageCount = Math.max(...analytics.stageBreakdown.map((item) => item.count), 1)
  const topProjects = [...projects]
    .toSorted((a, b) => b.total_tokens - a.total_tokens)
    .slice(0, 6)
  const maxProjectTokenTotal = Math.max(...topProjects.map((item) => item.total_tokens), 1)

  return (
    <div className="grid gap-4">
      <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              {t('analytics.workspace')}
            </p>
            <h1 className="mt-3 font-serif text-3xl text-slate-950">{project.project_name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              {t('analytics.subtitle')}
            </p>
          </div>
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
              {t('analytics.currentStage')}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-950">
              {getDisplayStageLabel(analytics.currentStage, locale)}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.totalTokens')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{formatTokenCount(analytics.tokenBreakdown.total, locale)}</p>
          </div>
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.totalRuntime')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{formatDurationMs(analytics.totalGenerationTimeMs, locale)}</p>
          </div>
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.totalRegenerations')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{analytics.totalRegenerations}</p>
          </div>
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.latestRunAverage')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{formatDurationMs(analytics.averageRunDurationMs, locale)}</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <ChartCard eyebrow={t('analytics.tokens')} title={t('analytics.tokenMix')}>
          <div className="space-y-4">
            {[
              { label: t('token.input'), value: analytics.tokenBreakdown.prompt, tone: 'bg-sky-500' },
              { label: t('token.output'), value: analytics.tokenBreakdown.completion, tone: 'bg-amber-500' },
              { label: t('transcript.humanRegenTokens'), value: analytics.humanRegenerationTokenTotal, tone: 'bg-emerald-500' },
            ].map((item) => {
              const width = analytics.tokenBreakdown.total > 0
                ? Math.max((item.value / analytics.tokenBreakdown.total) * 100, item.value > 0 ? 8 : 0)
                : 0
              return (
                <div key={item.label}>
                  <div className="flex items-center justify-between gap-3 text-sm text-slate-700">
                    <span>{item.label}</span>
                    <span className="font-semibold text-slate-950">{formatTokenCount(item.value, locale)}</span>
                  </div>
                  <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full ${item.tone}`} style={{ width: `${width}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </ChartCard>

        <ChartCard eyebrow={t('analytics.turnFlow')} title={t('analytics.stageDistribution')}>
          <div className="space-y-4">
            {analytics.stageBreakdown.map((item) => (
              <div key={item.stage}>
                <div className="flex items-center justify-between gap-3 text-sm text-slate-700">
                  <span>{getDisplayStageLabel(item.stage, locale)}</span>
                  <span className="font-semibold text-slate-950">{item.count}</span>
                </div>
                <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-slate-900"
                    style={{ width: `${(item.count / maxStageCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ChartCard eyebrow={t('analytics.timeline')} title={t('analytics.stageTimeline')}>
          <div className="flex flex-wrap gap-2">
            {analytics.timeline.map((item) => (
              <div key={`${item.turnNo}-${item.stage}`} className="min-w-28 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {locale === 'zh-CN' ? `第 ${item.turnNo} 轮` : `Turn ${item.turnNo}`}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-950">
                  {getDisplayStageLabel(item.stage, locale)}
                </p>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard eyebrow={t('analytics.portfolio')} title={t('analytics.projectComparison')}>
          <div className="space-y-4">
            {topProjects.map((item) => (
              <div key={item.id}>
                <div className="flex items-center justify-between gap-3 text-sm text-slate-700">
                  <span className="truncate">{item.project_name}</span>
                  <span className="font-semibold text-slate-950">{formatTokenCount(item.total_tokens, locale)}</span>
                </div>
                <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-[linear-gradient(90deg,#0f172a,#0ea5e9)]"
                    style={{ width: `${(item.total_tokens / maxProjectTokenTotal) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
