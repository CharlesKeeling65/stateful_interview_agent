import type { Locale, Translator } from '../i18n'
import type { ProjectRead } from '../types/api'
import { CreateProjectForm } from './CreateProjectForm'
import { ActionButton } from './ActionButton'
import { TrashIcon } from './Icons'
import { ProjectStatusBadge } from './ProjectStatusBadge'
import { formatTimestamp } from '../utils/format'
import { formatTokenCount } from '../utils/tokens'
import { getDisplayStageLabel } from '../i18n'
import type { BusyAction } from '../hooks/useProject'

type ProjectSidebarProps = {
  activeProjectId: number | null
  busyAction?: BusyAction
  disabled?: boolean
  locale?: Locale
  onCreate: Parameters<typeof CreateProjectForm>[0]['onCreate']
  onCreateDemo: Parameters<typeof CreateProjectForm>[0]['onCreateDemo']
  onRequestDelete: (project: ProjectRead) => void
  onSelectProject: (projectId: number) => void
  projects: ProjectRead[]
  t: Translator
}

export function ProjectSidebar({
  activeProjectId,
  busyAction = null,
  disabled = false,
  locale = 'en',
  onCreate,
  onCreateDemo,
  onRequestDelete,
  onSelectProject,
  projects,
  t,
}: ProjectSidebarProps) {
  const createWorkingLabel = busyAction === 'creating' ? `${t('sidebar.createProject')}...` : null

  return (
    <aside className="flex h-full flex-col gap-4 border-b border-white/40 bg-[linear-gradient(180deg,rgba(248,250,252,0.95),rgba(241,245,249,0.92))] p-4 lg:border-b-0 lg:border-r">
      <div className="rounded-[1.75rem] border border-slate-200/80 bg-slate-950 px-5 py-5 text-white shadow-[0_20px_50px_rgba(15,23,42,0.32)]">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-amber-200/90">
          Stateful Interview Agent
        </p>
        <h1 className="mt-3 font-serif text-2xl leading-tight">
          {t('sidebar.title')}
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          {t('sidebar.copy')}
        </p>
      </div>

      <CreateProjectForm
        disabled={disabled}
        workingLabel={createWorkingLabel}
        onCreate={onCreate}
        onCreateDemo={onCreateDemo}
        t={t}
      />

      <section className="min-h-0 flex-1 rounded-[1.75rem] border border-white/60 bg-white/80 p-4 shadow-[0_18px_40px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              {t('sidebar.projectList')}
            </p>
            <h2 className="mt-2 font-serif text-xl text-slate-950">{t('sidebar.recentSessions')}</h2>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
            {busyAction === 'initializing' ? '...' : projects.length}
          </span>
        </div>

        <div className="mt-4 space-y-2 overflow-auto pr-1">
          {projects.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
              {t('sidebar.empty')}
            </div>
          ) : null}

          {projects.map((item) => {
            const isActive = item.id === activeProjectId

            return (
              <div
                key={item.id}
                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                  isActive
                    ? 'border-amber-400 bg-amber-50 shadow-[0_12px_30px_rgba(251,191,36,0.18)]'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => onSelectProject(item.id)}
                    disabled={disabled}
                    aria-pressed={isActive}
                    aria-label={`${t('sidebar.selectProject')}: ${item.project_name}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-950">{item.project_name}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">
                          {getDisplayStageLabel(item.current_stage, locale)}
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-slate-100 px-2 py-1 text-[0.68rem] font-medium text-slate-600">
                        #{item.id}
                      </span>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                      <ProjectStatusBadge locale={locale} project={item} />
                      <span className="text-xs text-slate-500">{item.turn_count} {t('sidebar.turnsSuffix')}</span>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                      <span>{t('sidebar.createdAt')} {formatTimestamp(item.created_at, locale)}</span>
                      <span>{t('sidebar.updatedAt')} {formatTimestamp(item.updated_at, locale)}</span>
                    </div>
                    <div className="mt-2 text-[11px] text-slate-400">
                      {t('sidebar.totalTokens')} {formatTokenCount(item.total_tokens, locale)}
                    </div>
                  </button>

                  <ActionButton
                    aria-label={`${t('sidebar.delete')} ${item.project_name}`}
                    className="shrink-0"
                    disabled={disabled}
                    icon={<TrashIcon />}
                    onClick={() => onRequestDelete(item)}
                    title={`${t('sidebar.delete')} ${item.project_name}`}
                    type="button"
                    variant="ghost"
                  />
                </div>
              </div>
            )
          })}
        </div>
      </section>
    </aside>
  )
}
