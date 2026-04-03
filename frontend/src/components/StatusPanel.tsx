import type { ProjectRead, ProjectStatusResponse, TranscriptResponse } from '../types/api'
import { formatDurationMs } from '../utils/format'
import {
  formatBooleanLabel,
  hasInterviewStarted,
  isProjectFinished,
} from '../utils/status'
import { ActionButton } from './ActionButton'
import { CopyIcon, DownloadIcon, PlayIcon } from './Icons'
import { ProjectStatusBadge } from './ProjectStatusBadge'
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
          <ActionButton
            disabled={!project || started || projectFinished || working}
            icon={<PlayIcon />}
            label={workingLabel === 'Starting...' ? 'Starting...' : 'Start'}
            onClick={() => void onStart()}
            type="button"
            variant="primary"
          />
        </div>

        {project ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <StatusItem label="Project ID" value={`#${project.id}`} />
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Status
              </p>
              <div className="mt-2">
                <ProjectStatusBadge project={project} status={status} />
              </div>
            </div>
            <StatusItem label="Current Stage" value={status?.current_stage ?? project.current_stage} />
            <StatusItem label="Turns" value={String(status?.turn_count ?? project.turn_count)} />
            <StatusItem label="Runs" value={String(status?.run_count ?? 0)} />
            <StatusItem
              label="Total Generation"
              value={formatDurationMs(status?.cumulative_generation_time_ms ?? 0)}
            />
            <StatusItem
              label="Average Run"
              value={formatDurationMs(status?.average_run_duration_ms ?? 0)}
            />
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
            <h2 className="mt-3 font-serif text-2xl text-slate-950">Export actions</h2>
          </div>
        </div>

        <div className="mt-5 rounded-[1.75rem] border border-slate-200 bg-slate-50/80 p-4">
          <p className="text-sm leading-7 text-slate-600">
            Copy the full transcript or export it as a plain text or Markdown file. The transcript body stays hidden here to keep the runtime panel compact.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <ActionButton
              disabled={!transcript?.transcript}
              icon={<CopyIcon />}
              label={exportLabel === 'Copying...' || exportLabel === 'Copied' ? exportLabel : 'Copy'}
              onClick={() => void onCopyTranscript()}
              type="button"
            />
            <ActionButton
              disabled={!transcript?.transcript}
              icon={<DownloadIcon />}
              label={exportLabel === 'Exporting .txt...' ? '.txt...' : '.txt'}
              onClick={onExportText}
              type="button"
            />
            <ActionButton
              disabled={!transcript?.transcript}
              icon={<DownloadIcon />}
              label={exportLabel === 'Exporting .md...' ? '.md...' : '.md'}
              onClick={onExportMarkdown}
              type="button"
            />
          </div>
        </div>
        <p className="mt-3 text-xs leading-6 text-slate-500">
          {transcript?.transcript
            ? 'Exports are generated client-side from the latest backend transcript.'
            : 'Transcript actions unlock after the interview has generated at least one turn.'}
        </p>
      </section>
    </aside>
  )
}
