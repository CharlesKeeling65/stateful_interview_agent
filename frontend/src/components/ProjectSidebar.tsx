import type { ProjectRead } from '../types/api'
import { CreateProjectForm } from './CreateProjectForm'
import { formatTimestamp } from '../utils/format'

type ProjectSidebarProps = {
  activeProjectId: number | null
  busyAction?: 'initializing' | 'selecting' | 'creating' | 'starting' | 'submitting' | null
  disabled?: boolean
  onCreate: Parameters<typeof CreateProjectForm>[0]['onCreate']
  onCreateDemo: Parameters<typeof CreateProjectForm>[0]['onCreateDemo']
  onSelectProject: (projectId: number) => void
  projects: ProjectRead[]
}

export function ProjectSidebar({
  activeProjectId,
  busyAction = null,
  disabled = false,
  onCreate,
  onCreateDemo,
  onSelectProject,
  projects,
}: ProjectSidebarProps) {
  const createWorkingLabel = busyAction === 'creating' ? 'Creating project...' : null

  return (
    <aside className="flex h-full flex-col gap-4 border-b border-white/40 bg-[linear-gradient(180deg,rgba(248,250,252,0.95),rgba(241,245,249,0.92))] p-4 lg:border-b-0 lg:border-r">
      <div className="rounded-[1.75rem] border border-slate-200/80 bg-slate-950 px-5 py-5 text-white shadow-[0_20px_50px_rgba(15,23,42,0.32)]">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-amber-200/90">
          Stateful Interview Agent
        </p>
        <h1 className="mt-3 font-serif text-2xl leading-tight">
          Local orchestration console for your project sessions.
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          Create a project, start the interview, paste each opencode answer, and keep the thread durable turn by turn.
        </p>
      </div>

      <CreateProjectForm
        disabled={disabled}
        workingLabel={createWorkingLabel}
        onCreate={onCreate}
        onCreateDemo={onCreateDemo}
      />

      <section className="min-h-0 flex-1 rounded-[1.75rem] border border-white/60 bg-white/80 p-4 shadow-[0_18px_40px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              Project List
            </p>
            <h2 className="mt-2 font-serif text-xl text-slate-950">Recent sessions</h2>
        </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
            {busyAction === 'initializing' ? '...' : projects.length}
          </span>
        </div>

        <div className="mt-4 space-y-2 overflow-auto pr-1">
          {projects.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
              No project yet. Create one from the panel above.
            </div>
          ) : null}

          {projects.map((item) => {
            const isActive = item.id === activeProjectId

            return (
              <button
                key={item.id}
                type="button"
                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                  isActive
                    ? 'border-amber-400 bg-amber-50 shadow-[0_12px_30px_rgba(251,191,36,0.18)]'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                }`}
                onClick={() => onSelectProject(item.id)}
                disabled={disabled}
                aria-pressed={isActive}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-950">{item.project_name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">
                      {item.current_stage}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-1 text-[0.68rem] font-medium text-slate-600">
                    #{item.id}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                  <span>{item.turn_count} turns</span>
                  <span>{formatTimestamp(item.updated_at)}</span>
                </div>
              </button>
            )
          })}
        </div>
      </section>
    </aside>
  )
}
