import type { ProjectRead, ProjectStatusResponse, TranscriptResponse } from '../types/api'
import {
  formatBooleanLabel,
  getRuntimeStatusLabel,
  hasInterviewStarted,
  isProjectFinished,
} from '../utils/status'
import { TokenUsagePanel } from './TokenUsagePanel'

type StatusPanelProps = {
  errorMessage: string
  exportLabel?: string | null
  infoMessage: string
  onCopyTranscript: () => Promise<void> | void
  onExportMarkdown: () => void
  onExportText: () => void
  onStart: () => Promise<void> | void
  project: ProjectRead | null
  status: ProjectStatusResponse | null
  transcript: TranscriptResponse | null
  working?: boolean
  workingLabel?: string | null
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  )
}

export function StatusPanel({
  errorMessage,
  exportLabel = null,
  infoMessage,
  onCopyTranscript,
  onExportMarkdown,
  onExportText,
  onStart,
  project,
  status,
  transcript,
  working = false,
  workingLabel = null,
}: StatusPanelProps) {
  const projectFinished = isProjectFinished(project, status)
  const started = hasInterviewStarted(project)

  return (
    <aside className="flex h-full flex-col gap-4">
      <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              Project Status
            </p>
            <h2 className="mt-3 font-serif text-2xl text-slate-950">Runtime snapshot</h2>
          </div>
          <button
            type="button"
            className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            onClick={() => void onStart()}
            disabled={!project || started || projectFinished || working}
          >
            {workingLabel === 'Starting interview...' ? workingLabel : 'Start Interview'}
          </button>
        </div>

        {project ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <StatusItem label="Project ID" value={`#${project.id}`} />
            <StatusItem label="Status" value={getRuntimeStatusLabel(project, status)} />
            <StatusItem label="Current Stage" value={status?.current_stage ?? project.current_stage} />
            <StatusItem label="Turns" value={String(status?.turn_count ?? project.turn_count)} />
            <StatusItem
              label="Minimum Goal"
              value={formatBooleanLabel(status?.minimum_goal_reached, {
                trueLabel: 'Reached',
                falseLabel: 'Not yet',
              })}
            />
            <StatusItem
              label="Latest Answered"
              value={formatBooleanLabel(status?.latest_turn_answered, {
                trueLabel: 'Yes',
                falseLabel: 'Waiting',
                nullLabel: 'No turns yet',
              })}
            />
          </div>
        ) : (
          <p className="mt-5 text-sm leading-7 text-slate-600">
            No active project. Pick one from the left column or create a new session.
          </p>
        )}

        {errorMessage ? (
          <div className="mt-5 rounded-[1.5rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-900">
            {errorMessage}
          </div>
        ) : null}

        {infoMessage ? (
          <div className="mt-5 rounded-[1.5rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
            {infoMessage}
          </div>
        ) : null}

        {status?.usage_summary ? (
          <div className="mt-5">
            <TokenUsagePanel label="Session Token Usage" summary={status.usage_summary} />
          </div>
        ) : null}
      </section>

      <section className="flex min-h-0 flex-1 flex-col rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              Transcript Export
            </p>
            <h2 className="mt-3 font-serif text-2xl text-slate-950">Raw transcript</h2>
          </div>
          <button
            type="button"
            className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            onClick={() => void onCopyTranscript()}
            disabled={!transcript?.transcript}
          >
            {exportLabel === 'Copying...' || exportLabel === 'Copied' ? exportLabel : 'Copy'}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-full border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            onClick={onExportText}
            disabled={!transcript?.transcript}
          >
            {exportLabel === 'Exporting .txt...' ? exportLabel : 'Export .txt'}
          </button>
          <button
            type="button"
            className="rounded-full border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            onClick={onExportMarkdown}
            disabled={!transcript?.transcript}
          >
            {exportLabel === 'Exporting .md...' ? exportLabel : 'Export .md'}
          </button>
        </div>

        <pre className="mt-5 min-h-0 flex-1 overflow-auto rounded-[1.75rem] border border-slate-800 bg-[linear-gradient(180deg,#0f172a,#111827)] px-5 py-5 text-xs leading-7 text-slate-200 shadow-inner">
          {transcript?.transcript || 'No transcript yet.'}
        </pre>
        <p className="mt-3 text-xs leading-6 text-slate-500">
          Export preview only. Backend data remains unchanged.
        </p>
      </section>
    </aside>
  )
}
