import type { Locale, Translator } from '../i18n'
import { getDisplayStageLabel } from '../i18n'
import type { ProjectRead, ProjectStatusResponse, TurnRead } from '../types/api'
import { buildProjectAnalytics, type StageTransitionItem, type TurnTokenTrendItem } from '../utils/analytics'
import { formatDurationMs } from '../utils/format'
import { formatTokenCount } from '../utils/tokens'
import { RepositoryCoverageTree } from './RepositoryCoverageTree'
import type { 
  CoverageDebugResponse, 
  FileCoverageSummaryDebug, 
  QueueSummaryDebug 
} from '../types/api'

type StatsDashboardProps = {
  locale?: Locale
  project: ProjectRead | null
  projects: ProjectRead[]
  status: ProjectStatusResponse | null
  t: Translator
  turns: TurnRead[]
  coverageDebug?: CoverageDebugResponse | null
  queueSummary?: QueueSummaryDebug | null
  fileCoverageSummary?: FileCoverageSummaryDebug | null
}

const STAGE_SWATCHES = ['#0f172a', '#0ea5e9', '#f97316', '#10b981', '#a855f7', '#ef4444']

function ChartCard({
  children,
  eyebrow,
  title,
  subtitle,
  className = '',
}: {
  children: React.ReactNode
  eyebrow: string
  title: string
  subtitle?: string
  className?: string
}) {
  return (
    <section className={`rounded-[2rem] border border-white/60 bg-white/88 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur ${className}`}>
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">{eyebrow}</p>
      <h2 className="mt-3 font-serif text-2xl text-slate-950">{title}</h2>
      {subtitle ? <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{subtitle}</p> : null}
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

function getRatio(value: number, total: number) {
  if (total <= 0) {
    return 0
  }
  return value / total
}

function formatPercent(value: number, locale: Locale) {
  return new Intl.NumberFormat(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 0,
  }).format(value)
}

function describeArc(cx: number, cy: number, radius: number, startAngle: number, endAngle: number) {
  const startX = cx + radius * Math.cos(startAngle)
  const startY = cy + radius * Math.sin(startAngle)
  const endX = cx + radius * Math.cos(endAngle)
  const endY = cy + radius * Math.sin(endAngle)
  const largeArcFlag = endAngle - startAngle > Math.PI ? 1 : 0

  return `M ${cx} ${cy} L ${startX} ${startY} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY} Z`
}

function buildLinePath(points: Array<{ x: number; y: number }>) {
  if (points.length === 0) {
    return ''
  }
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
}

function buildAreaPath(points: Array<{ x: number; y: number }>, baselineY: number) {
  if (points.length === 0) {
    return ''
  }
  const start = points[0]
  const end = points[points.length - 1]
  return `M ${start.x} ${baselineY} L ${start.x} ${start.y} ${points
    .slice(1)
    .map((point) => `L ${point.x} ${point.y}`)
    .join(' ')} L ${end.x} ${baselineY} Z`
}

function TokenComposition({
  locale,
  t,
  total,
  values,
}: {
  locale: Locale
  t: Translator
  total: number
  values: Array<{ color: string; label: string; value: number }>
}) {
  const segments = values.reduce<Array<{ color: string; label: string; value: number; startAngle: number; endAngle: number }>>(
    (items, item) => {
      const previousEndAngle = items[items.length - 1]?.endAngle ?? -Math.PI / 2
      const sweep = getRatio(item.value, total) * Math.PI * 2
      items.push({
        ...item,
        startAngle: previousEndAngle,
        endAngle: previousEndAngle + sweep,
      })
      return items
    },
    [],
  )

  return (
    <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-center">
      <div className="mx-auto w-full max-w-[220px]">
        <svg viewBox="0 0 220 220" className="h-auto w-full">
          <defs>
            <radialGradient id="analytics-donut-glow">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#e2e8f0" stopOpacity="0.2" />
            </radialGradient>
          </defs>
          <circle cx="110" cy="110" r="92" fill="url(#analytics-donut-glow)" />
          {segments.map((item) => {
            const ratio = getRatio(item.value, total)
            if (ratio <= 0) {
              return null
            }
            return (
              <path
                key={item.label}
                d={describeArc(110, 110, 92, item.startAngle, item.endAngle)}
                fill={item.color}
                opacity={0.92}
                stroke="#f8fafc"
                strokeWidth="3"
              />
            )
          })}
          <circle cx="110" cy="110" r="58" fill="#fffdf8" />
          <text x="110" y="100" textAnchor="middle" className="fill-slate-500 text-[11px] font-semibold uppercase tracking-[0.28em]">
            {t('token.total')}
          </text>
          <text x="110" y="126" textAnchor="middle" className="fill-slate-950 text-[24px] font-semibold">
            {formatTokenCount(total, locale)}
          </text>
        </svg>
      </div>

      <div className="space-y-4">
        {values.map((item) => (
          <div key={item.label} className="rounded-[1.35rem] border border-slate-200/80 bg-slate-50/70 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-sm font-medium text-slate-700">{item.label}</span>
              </div>
              <span className="text-sm font-semibold text-slate-950">{formatTokenCount(item.value, locale)}</span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span>{t('analytics.shareOfTotal')}</span>
              <span>{formatPercent(getRatio(item.value, total), locale)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function TurnTrendChart({
  locale,
  points,
  t,
}: {
  locale: Locale
  points: TurnTokenTrendItem[]
  t: Translator
}) {
  const width = 620
  const height = 240
  const paddingX = 32
  const paddingTop = 24
  const paddingBottom = 34
  const chartWidth = width - paddingX * 2
  const chartHeight = height - paddingTop - paddingBottom
  const maxValue = Math.max(...points.map((item) => item.totalTokens), 1)
  const chartPoints = points.map((item, index) => ({
    ...item,
    x: paddingX + (points.length === 1 ? chartWidth / 2 : (chartWidth / Math.max(points.length - 1, 1)) * index),
    y: paddingTop + chartHeight - (item.totalTokens / maxValue) * chartHeight,
  }))

  return (
    <div className="space-y-4">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full overflow-visible">
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = paddingTop + chartHeight - chartHeight * ratio
          return (
            <g key={ratio}>
              <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} stroke="#e2e8f0" strokeDasharray="4 8" />
              <text x={8} y={y + 4} className="fill-slate-400 text-[10px]">
                {formatTokenCount(Math.round(maxValue * ratio), locale)}
              </text>
            </g>
          )
        })}

        <path d={buildAreaPath(chartPoints, paddingTop + chartHeight)} fill="url(#analytics-trend-area)" opacity="0.95" />
        <path d={buildLinePath(chartPoints)} fill="none" stroke="#0f172a" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />

        <defs>
          <linearGradient id="analytics-trend-area" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.38" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {chartPoints.map((point) => (
          <g key={point.turnNo}>
            <circle cx={point.x} cy={point.y} r={8} fill="#fffdf8" stroke="#0f172a" strokeWidth="2.5" />
            {point.regenerationCount > 0 ? (
              <circle cx={point.x} cy={point.y} r={12 + point.regenerationCount * 2} fill="#f97316" opacity="0.14" />
            ) : null}
            <text x={point.x} y={height - 10} textAnchor="middle" className="fill-slate-500 text-[11px] font-medium">
              {locale === 'zh-CN' ? `第${point.turnNo}轮` : point.label}
            </text>
          </g>
        ))}
      </svg>

      <div className="grid gap-3 md:grid-cols-3">
        {points.map((item) => (
          <div key={item.turnNo} className="rounded-[1.25rem] border border-slate-200 bg-slate-50/80 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                {locale === 'zh-CN' ? `第 ${item.turnNo} 轮` : `Turn ${item.turnNo}`}
              </span>
              <span className="text-sm font-semibold text-slate-950">{formatTokenCount(item.totalTokens, locale)}</span>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              {t('analytics.regenerationPressure')} {item.regenerationCount}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function CumulativeBars({
  locale,
  points,
  t,
}: {
  locale: Locale
  points: TurnTokenTrendItem[]
  t: Translator
}) {
  const maxCumulative = Math.max(...points.map((item) => item.cumulativeTokens), 1)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(88px,1fr))] gap-3">
        {points.map((item) => {
          const promptHeight = (item.promptTokens / maxCumulative) * 180
          const completionHeight = (item.completionTokens / maxCumulative) * 180
          const reviewHeight = (item.humanReviewTokens / maxCumulative) * 180
          return (
            <div key={item.turnNo} className="rounded-[1.35rem] border border-slate-200 bg-[linear-gradient(180deg,rgba(248,250,252,0.94),rgba(241,245,249,0.74))] px-3 py-4">
              <div className="flex h-48 items-end justify-center gap-0 rounded-[1rem] bg-white/85 px-3 py-3 shadow-inner shadow-slate-200/70">
                <div className="w-8 rounded-t-[0.85rem] bg-sky-500/85" style={{ height: `${promptHeight}px` }} />
                <div className="w-8 rounded-t-[0.85rem] bg-amber-500/85" style={{ height: `${completionHeight}px` }} />
                <div className="w-8 rounded-t-[0.85rem] bg-emerald-500/85" style={{ height: `${reviewHeight}px` }} />
              </div>
              <div className="mt-3 text-center">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {locale === 'zh-CN' ? `第${item.turnNo}轮` : item.label}
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-950">{formatTokenCount(item.cumulativeTokens, locale)}</p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-sky-500" />
          {t('token.input')}
        </span>
        <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
          {t('token.output')}
        </span>
        <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
          {t('transcript.humanRegenTokens')}
        </span>
      </div>
    </div>
  )
}

function StageBands({
  analytics,
  locale,
}: {
  analytics: ReturnType<typeof buildProjectAnalytics>
  locale: Locale
}) {
  const totalTurns = Math.max(analytics.totalTurns, 1)
  const stageColorMap = new Map<string, string>()
  analytics.stageBreakdown.forEach((item, index) => {
    stageColorMap.set(item.stage, STAGE_SWATCHES[index % STAGE_SWATCHES.length])
  })

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-[1.6rem] border border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.92))] p-4">
        <div className="flex items-center gap-2 pb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
          {Array.from({ length: totalTurns }, (_, index) => index + 1).map((turnNo) => (
            <div key={turnNo} className="min-w-0 flex-1 text-center">
              {locale === 'zh-CN' ? `${turnNo}` : `T${turnNo}`}
            </div>
          ))}
        </div>
        <div className="relative flex gap-1">
          {analytics.stageSegments.map((segment) => (
            <div
              key={`${segment.stage}-${segment.startTurnNo}`}
              className="min-w-0 rounded-[1.2rem] px-3 py-5 text-white shadow-[0_12px_30px_rgba(15,23,42,0.14)]"
              style={{
                flexGrow: segment.turnSpan,
                background: `linear-gradient(135deg, ${stageColorMap.get(segment.stage) ?? '#0f172a'}, rgba(255,255,255,0.18))`,
              }}
            >
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/70">
                {locale === 'zh-CN' ? `第 ${segment.startTurnNo}-${segment.endTurnNo} 轮` : `Turn ${segment.startTurnNo}-${segment.endTurnNo}`}
              </p>
              <p className="mt-2 text-sm font-semibold">{getDisplayStageLabel(segment.stage, locale)}</p>
              <p className="mt-2 text-xs text-white/80">{formatPercent(segment.share, locale)}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {analytics.stageBreakdown.map((item, index) => (
          <div key={item.stage} className="rounded-[1.25rem] border border-slate-200 bg-slate-50/80 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 rounded-full" style={{ backgroundColor: STAGE_SWATCHES[index % STAGE_SWATCHES.length] }} />
              <span className="text-sm font-medium text-slate-700">{getDisplayStageLabel(item.stage, locale)}</span>
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-500">{formatPercent(item.count / totalTurns, locale)}</span>
              <span className="font-semibold text-slate-950">{item.count}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StageNetwork({
  locale,
  stageBreakdown,
  transitions,
}: {
  locale: Locale
  stageBreakdown: Array<{ stage: string; count: number }>
  transitions: StageTransitionItem[]
}) {
  const width = 620
  const height = 300
  const nodeCount = Math.max(stageBreakdown.length, 1)
  const maxCount = Math.max(...stageBreakdown.map((item) => item.count), 1)
  const maxTransition = Math.max(...transitions.map((item) => item.count), 1)

  const nodes = stageBreakdown.map((item, index) => ({
    ...item,
    x: 90 + ((width - 180) / Math.max(nodeCount - 1, 1)) * index,
    y: height / 2 + (index % 2 === 0 ? -36 : 36),
    radius: 20 + (item.count / maxCount) * 24,
    color: STAGE_SWATCHES[index % STAGE_SWATCHES.length],
  }))

  const getNode = (stage: string) => nodes.find((node) => node.stage === stage)

  return (
    <div className="space-y-4">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full">
        <defs>
          <linearGradient id="analytics-network-link" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.72" />
            <stop offset="100%" stopColor="#0f172a" stopOpacity="0.72" />
          </linearGradient>
        </defs>

        {transitions.map((transition) => {
          const fromNode = getNode(transition.from)
          const toNode = getNode(transition.to)
          if (!fromNode || !toNode) {
            return null
          }
          const midX = (fromNode.x + toNode.x) / 2
          const directionLift = fromNode.stage === toNode.stage ? -110 : -48
          return (
            <g key={`${transition.from}-${transition.to}`}>
              <path
                d={`M ${fromNode.x} ${fromNode.y} C ${midX} ${fromNode.y + directionLift}, ${midX} ${toNode.y + directionLift}, ${toNode.x} ${toNode.y}`}
                fill="none"
                stroke="url(#analytics-network-link)"
                strokeWidth={2 + (transition.count / maxTransition) * 6}
                strokeLinecap="round"
                opacity="0.9"
              />
              <text x={midX} y={Math.min(fromNode.y, toNode.y) - 36} textAnchor="middle" className="fill-slate-400 text-[11px] font-semibold">
                {transition.count}
              </text>
            </g>
          )
        })}

        {nodes.map((node) => (
          <g key={node.stage}>
            <circle cx={node.x} cy={node.y} r={node.radius} fill={node.color} opacity="0.88" />
            <circle cx={node.x} cy={node.y} r={node.radius - 10} fill="#fffdf8" opacity="0.9" />
            <text x={node.x} y={node.y + 4} textAnchor="middle" className="fill-slate-950 text-[12px] font-semibold">
              {node.count}
            </text>
            <text x={node.x} y={node.y + node.radius + 20} textAnchor="middle" className="fill-slate-600 text-[12px] font-medium">
              {getDisplayStageLabel(node.stage, locale)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function RegenerationPressure({
  locale,
  points,
}: {
  locale: Locale
  points: TurnTokenTrendItem[]
}) {
  const maxRegeneration = Math.max(...points.map((item) => item.regenerationCount), 1)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(92px,1fr))] gap-3">
        {points.map((item) => (
          <div key={item.turnNo} className="rounded-[1.35rem] border border-slate-200 bg-slate-50/80 px-3 py-4">
            <div className="flex h-32 items-end justify-center rounded-[1rem] bg-white/80 px-3 py-3">
              <div
                className="w-10 rounded-t-[0.9rem] bg-[linear-gradient(180deg,#fb923c,#ea580c)] shadow-[0_12px_30px_rgba(234,88,12,0.22)]"
                style={{ height: `${Math.max((item.regenerationCount / maxRegeneration) * 100, item.regenerationCount > 0 ? 18 : 6)}%` }}
              />
            </div>
            <div className="mt-3 text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                {locale === 'zh-CN' ? `第${item.turnNo}轮` : item.label}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-950">{item.regenerationCount}</p>
            </div>
          </div>
        ))}
      </div>
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
  queueSummary,
  fileCoverageSummary,
}: StatsDashboardProps) {
  if (!project) {
    return <EmptyStats t={t} />
  }

  const analytics = buildProjectAnalytics(project, status, turns)
  const topProjects = [...projects]
    .toSorted((a, b) => b.total_tokens - a.total_tokens)
    .slice(0, 6)
  const maxProjectTokenTotal = Math.max(...topProjects.map((item) => item.total_tokens), 1)
  const largestTurn = analytics.turnTokenTrend.toSorted((left, right) => right.totalTokens - left.totalTokens)[0]
  const promptCompletionReview = [
    { color: '#0ea5e9', label: t('token.input'), value: analytics.tokenBreakdown.prompt },
    { color: '#f59e0b', label: t('token.output'), value: analytics.tokenBreakdown.completion },
    { color: '#10b981', label: t('transcript.humanRegenTokens'), value: analytics.humanRegenerationTokenTotal },
  ]

  return (
    <div className="grid gap-4">
      <section className="overflow-hidden rounded-[2.15rem] border border-white/60 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.12),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(249,115,22,0.12),transparent_34%),rgba(255,255,255,0.88)] p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
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
          <div className="rounded-[1.5rem] border border-white/80 bg-white/72 px-4 py-4 shadow-[0_12px_30px_rgba(148,163,184,0.15)]">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
              {t('analytics.currentStage')}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-950">
              {getDisplayStageLabel(analytics.currentStage, locale)}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-[1.5rem] border border-white/90 bg-white/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.totalTokens')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{formatTokenCount(analytics.tokenBreakdown.total, locale)}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/90 bg-white/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.totalRuntime')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{formatDurationMs(analytics.totalGenerationTimeMs, locale)}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/90 bg-white/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.totalRegenerations')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{analytics.totalRegenerations}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/90 bg-white/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.latestRunAverage')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">{formatDurationMs(analytics.averageRunDurationMs, locale)}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/90 bg-white/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.mostExpensiveTurn')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">
              {largestTurn ? (locale === 'zh-CN' ? `第 ${largestTurn.turnNo} 轮` : `Turn ${largestTurn.turnNo}`) : '—'}
            </p>
          </div>
          <div className="rounded-[1.5rem] border border-white/90 bg-white/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.18em] text-slate-500">{t('analytics.answerCompletion')}</p>
            <p className="mt-2 text-sm font-semibold text-slate-950">
              {analytics.totalTurns > 0 ? formatPercent(analytics.answeredTurns / analytics.totalTurns, locale) : formatPercent(0, locale)}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
        <ChartCard
          eyebrow={t('analytics.tokens')}
          title={t('analytics.tokenComposition')}
          subtitle={t('analytics.tokenCompositionHint')}
        >
          <TokenComposition
            locale={locale}
            t={t}
            total={analytics.tokenBreakdown.total}
            values={promptCompletionReview}
          />
        </ChartCard>

        <ChartCard
          eyebrow={t('analytics.turnFlow')}
          title={t('analytics.tokenTrend')}
          subtitle={t('analytics.tokenTrendHint')}
        >
          <TurnTrendChart locale={locale} points={analytics.turnTokenTrend} t={t} />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <ChartCard
          eyebrow={t('analytics.tokens')}
          title={t('analytics.cumulativeLoad')}
          subtitle={t('analytics.cumulativeLoadHint')}
        >
          <CumulativeBars locale={locale} points={analytics.turnTokenTrend} t={t} />
        </ChartCard>

        <ChartCard
          eyebrow={t('analytics.turnFlow')}
          title={t('analytics.regenerationPressure')}
          subtitle={t('analytics.regenerationPressureHint')}
        >
          <RegenerationPressure locale={locale} points={analytics.turnTokenTrend} />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <ChartCard
          eyebrow={t('analytics.timeline')}
          title={t('analytics.stageOccupancy')}
          subtitle={t('analytics.stageOccupancyHint')}
        >
          <StageBands analytics={analytics} locale={locale} />
        </ChartCard>

        <ChartCard
          eyebrow={t('analytics.turnFlow')}
          title={t('analytics.stageNetwork')}
          subtitle={t('analytics.stageNetworkHint')}
        >
          <StageNetwork
            locale={locale}
            stageBreakdown={analytics.stageBreakdown}
            transitions={analytics.stageTransitions}
          />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,0.6fr)]">
        <ChartCard
          eyebrow={t('status.repository')}
          title={t('analytics.repositoryCoverage')}
          subtitle={t('analytics.topCoverageGapsHint')}
        >
          <RepositoryCoverageTree 
            locale={locale} 
            summary={fileCoverageSummary ?? null} 
            t={t} 
          />
        </ChartCard>

        <ChartCard
          eyebrow={t('analytics.queueStatus')}
          title={t('analytics.queuedItems')}
          subtitle={t('composer.opencodePlanHint')}
        >
           {queueSummary && queueSummary.status !== 'empty' ? (
             <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-900 text-white shadow-lg">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-white/50">{t('analytics.queueStatus')}</p>
                    <p className="mt-1 font-serif text-xl">{t('analytics.activeQueue')}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold">{queueSummary.item_count}</p>
                    <p className="text-[10px] text-white/70 uppercase font-medium">{t('analytics.itemsPending')}</p>
                  </div>
                </div>

                {queueSummary.parent_group_intent && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[10px] font-semibold text-slate-400 uppercase">{t('analytics.parentTurn')} #{queueSummary.parent_turn_no}</p>
                    <p className="text-sm font-medium text-slate-700 mt-1">{queueSummary.parent_group_intent}</p>
                  </div>
                )}

                <div className="space-y-2">
                  {queueSummary.pending_questions.map((q, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 rounded-xl border border-white bg-white shadow-sm">
                      <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500">
                        {i + 1}
                      </span>
                      <p className="text-sm text-slate-600 line-clamp-2 italic">“{q.question_text}”</p>
                    </div>
                  ))}
                </div>
             </div>
           ) : (
             <div className="flex h-64 flex-col items-center justify-center rounded-[2rem] border border-dashed border-slate-200 bg-slate-50/50 text-center p-6">
                <div className="h-12 w-12 rounded-full bg-slate-100 flex items-center justify-center mb-3">
                   <svg className="h-6 w-6 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                   </svg>
                </div>
                <p className="text-sm font-medium text-slate-400">{t('analytics.emptyQueue')}</p>
                <p className="text-xs text-slate-300 mt-1">Planner queue is currently clear.</p>
             </div>
           )}
        </ChartCard>
      </div>

      <ChartCard
        eyebrow={t('analytics.portfolio')}
        title={t('analytics.projectComparison')}
        subtitle={t('analytics.projectComparisonHint')}
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {topProjects.map((item) => (
            <div key={item.id} className="rounded-[1.35rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-medium text-slate-700">{item.project_name}</span>
                <span className="text-sm font-semibold text-slate-950">{formatTokenCount(item.total_tokens, locale)}</span>
              </div>
              <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,#0f172a,#0ea5e9,#f97316)]"
                  style={{ width: `${(item.total_tokens / maxProjectTokenTotal) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </ChartCard>
    </div>
  )
}
