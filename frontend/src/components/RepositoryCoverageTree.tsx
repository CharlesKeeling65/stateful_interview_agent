import type { Translator, Locale } from '../i18n'
import type { FileCoverageSummaryDebug } from '../types/api'

type RepositoryCoverageTreeProps = {
  locale: Locale
  summary: FileCoverageSummaryDebug | null
  t: Translator
}

function ProgressBar({ 
  value, 
  total = 1.0, 
  colorClass = 'bg-sky-500', 
  bgClass = 'bg-slate-100' 
}: { 
  value: number
  total?: number
  colorClass?: string
  bgClass?: string
}) {
  const percentage = Math.min((value / total) * 100, 100)
  return (
    <div className={`h-2.5 w-full overflow-hidden rounded-full ${bgClass}`}>
      <div 
        className={`h-full rounded-full transition-all duration-500 ${colorClass}`} 
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}

function FilePathDisplay({ path }: { path: string }) {
  const parts = path.split('/')
  if (parts.length <= 2) return <span className="truncate font-medium text-slate-950">{path}</span>
  
  const filename = parts[parts.length - 1]
  const dir = parts.slice(0, parts.length - 1).join('/')
  return (
    <span className="truncate">
      <span className="text-slate-400 text-[10px] mr-1">{dir}/</span>
      <span className="font-medium text-slate-950">{filename}</span>
    </span>
  )
}

export function RepositoryCoverageTree({ 
  locale, 
  summary, 
  t 
}: RepositoryCoverageTreeProps) {
  if (!summary) {
    return (
      <div className="flex h-48 items-center justify-center rounded-[2rem] border border-dashed border-slate-200 bg-slate-50/50">
        <p className="text-sm text-slate-400 italic">No coverage data available yet</p>
      </div>
    )
  }

  const sortedTreeEntries = Object.entries(summary.tree_summary).sort(
    (a, b) => b[1].total_importance - a[1].total_importance
  )

  return (
    <div className="space-y-8">
      {/* Directory Summaries */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sortedTreeEntries.map(([dir, stats]) => (
          <div key={dir} className="group rounded-[1.5rem] border border-slate-200/80 bg-white/70 p-4 shadow-sm transition-all hover:shadow-md hover:border-slate-300">
            <div className="flex items-center justify-between gap-3">
              <h3 className="truncate font-serif text-lg text-slate-950">{dir}</h3>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">
                {stats.file_count} {locale === 'zh-CN' ? '文件' : 'files'}
              </span>
            </div>
            
            <div className="mt-4 space-y-3">
              <div>
                <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
                  <span>{t('analytics.explorationProgress')}</span>
                  <span>{Math.round((stats.total_exploration / Math.max(stats.total_importance, 0.1)) * 100)}%</span>
                </div>
                <ProgressBar 
                  value={stats.total_exploration} 
                  total={stats.total_importance} 
                  colorClass="bg-[linear-gradient(90deg,#0ea5e9,#10b981)]"
                />
              </div>
              
              {stats.unexplored_important_count > 0 && (
                <div className="flex items-center gap-2 text-[11px] text-amber-600 font-medium">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                  {stats.unexplored_important_count} {t('analytics.itemsPending')}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Top 10 Gap Files Section */}
      <div className="rounded-[2rem] border border-slate-200/60 bg-slate-50/40 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="font-serif text-xl text-slate-950">{t('analytics.topCoverageGaps')}</h3>
            <p className="text-xs text-slate-500 mt-1">{t('analytics.topCoverageGapsHint')}</p>
          </div>
          <span className="hidden sm:inline-block rounded-full bg-slate-200/50 px-3 py-1 text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
            {t('analytics.rankByImportance')}
          </span>
        </div>

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200">
                <th className="px-4 py-3 font-semibold text-slate-600 w-[50%]">{t('status.repoFiles')}</th>
                <th className="px-4 py-3 font-semibold text-slate-600 text-center">{t('analytics.fileImportance')}</th>
                <th className="px-4 py-3 font-semibold text-slate-600 text-center">{t('analytics.explorationProgress')}</th>
                <th className="px-4 py-3 font-semibold text-slate-600 text-right">{t('analytics.coverageGap')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.top_gap_files.map((file) => (
                <tr key={file.path} className="group hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3 max-w-0">
                    <div className="flex items-center gap-2">
                       <FilePathDisplay path={file.path} />
                    </div>
                  </td>
                  <td className="px-4 py-3 w-32">
                    <div className="flex flex-col items-center">
                      <span className="text-[10px] font-mono mb-1">{file.importance_score.toFixed(2)}</span>
                      <ProgressBar value={file.importance_score} colorClass="bg-slate-400" bgClass="bg-slate-100" />
                    </div>
                  </td>
                  <td className="px-4 py-3 w-32">
                    <div className="flex flex-col items-center">
                      <span className="text-[10px] font-mono mb-1">{file.exploration_score.toFixed(2)}</span>
                      <ProgressBar value={file.exploration_score} total={file.importance_score} colorClass="bg-emerald-500" />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-amber-600">
                    {file.coverage_gap_score > 0 ? `+${file.coverage_gap_score.toFixed(2)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {summary.top_gap_files.length === 0 && (
             <div className="p-8 text-center text-slate-400 italic">
               Excellent coverage! No major gaps detected.
             </div>
          )}
        </div>
      </div>
    </div>
  )
}
