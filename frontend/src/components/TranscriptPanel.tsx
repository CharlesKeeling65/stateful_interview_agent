import { useDeferredValue } from 'react'

import type { ProjectRead, TurnRead } from '../types/api'
import { ProjectMetadataEditor } from './ProjectMetadataEditor'
import { TurnCard } from './TurnCard'

type TranscriptPanelProps = {
  copyLabel?: string | null
  onCopyLatestQuestion?: (text: string) => Promise<void> | void
  onRenameProject?: (nextTitle: string) => Promise<void> | void
  project: ProjectRead | null
  renameDisabled?: boolean
  turns: TurnRead[]
}

function EmptyState() {
  return (
    <div className="flex h-full min-h-96 items-center justify-center">
      <div className="max-w-md rounded-[2rem] border border-dashed border-slate-300 bg-white/70 px-8 py-10 text-center shadow-[0_22px_50px_rgba(148,163,184,0.12)] backdrop-blur">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
          Transcript
        </p>
        <h2 className="mt-3 font-serif text-3xl text-slate-950">Select a project to inspect its interview thread.</h2>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          Once the interview starts, each generated question and pasted answer will accumulate here in chronological order.
        </p>
      </div>
    </div>
  )
}

export function TranscriptPanel({
  copyLabel = null,
  onCopyLatestQuestion,
  onRenameProject,
  project,
  renameDisabled = false,
  turns,
}: TranscriptPanelProps) {
  const deferredTurns = useDeferredValue(turns)

  if (!project) {
    return <EmptyState />
  }

  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-slate-500">
              Active Transcript
            </p>
            <h2 className="mt-3 font-serif text-3xl leading-tight text-slate-950">
              {project.project_name}
            </h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              Full original answers stay visible here even when older turns are compacted for backend prompting.
            </p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 px-4 py-3 text-right">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Current Stage</p>
              <p className="mt-1 text-sm font-semibold text-slate-950">{project.current_stage}</p>
            </div>
            {onRenameProject ? (
              <ProjectMetadataEditor
                disabled={renameDisabled}
                initialTitle={project.project_name}
                onSave={onRenameProject}
              />
            ) : null}
          </div>
        </div>
      </header>

      <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-[2rem] border border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(248,250,252,0.92))] p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="space-y-4">
          {deferredTurns.map((turn) => (
            <TurnCard
              key={turn.id}
              copyLabel={copyLabel}
              isLatestActiveTurn={!turn.answer_text && turn.id === deferredTurns[deferredTurns.length - 1]?.id}
              onCopyLatestQuestion={onCopyLatestQuestion}
              turn={turn}
            />
          ))}

          {deferredTurns.length === 0 ? (
            <div className="rounded-[1.75rem] border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-500">
              Interview not started yet. Use the left panel to start the first turn.
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
