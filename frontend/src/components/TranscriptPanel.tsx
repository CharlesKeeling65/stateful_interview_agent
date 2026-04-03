import { useDeferredValue, useMemo, useState } from 'react'

import type { ProjectRead, RunRead, TurnRead } from '../types/api'
import { ActionButton } from './ActionButton'
import { CopyIcon, TrashIcon } from './Icons'
import { ActiveRunPanel } from './ExecutionTraceSection'
import { ProjectMetadataEditor } from './ProjectMetadataEditor'
import { TranscriptPagination } from './TranscriptPagination'
import { TurnCard } from './TurnCard'

type TranscriptPanelProps = {
  copyLabel?: string | null
  onCopyLatestQuestion?: (text: string) => Promise<void> | void
  onRequestDelete?: (project: ProjectRead) => void
  onRenameProject?: (nextTitle: string) => Promise<void> | void
  project: ProjectRead | null
  renameDisabled?: boolean
  activeRun?: RunRead | null
  runs?: RunRead[]
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
  onRequestDelete,
  onRenameProject,
  project,
  renameDisabled = false,
  activeRun = null,
  runs = [],
  turns,
}: TranscriptPanelProps) {
  const deferredTurns = useDeferredValue(turns)
  const [pageSize, setPageSize] = useState(5)
  const [manualPage, setManualPage] = useState(1)
  const [followLatestPage, setFollowLatestPage] = useState(true)

  const totalPages = Math.max(1, Math.ceil(deferredTurns.length / pageSize))
  const safeCurrentPage = followLatestPage ? totalPages : Math.min(manualPage, totalPages)
  const pagedTurns = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize
    return deferredTurns.slice(startIndex, startIndex + pageSize)
  }, [deferredTurns, pageSize, safeCurrentPage])
  const latestTurnId = deferredTurns[deferredTurns.length - 1]?.id
  const runByTurnNo = useMemo(
    () => new Map(runs.filter((run) => run.turn_no != null).map((run) => [run.turn_no as number, run])),
    [runs],
  )

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
            <div className="flex flex-wrap justify-end gap-2">
              {onCopyLatestQuestion && deferredTurns.length > 0 ? (
                <ActionButton
                  aria-label="Copy latest question"
                  icon={<CopyIcon />}
                  label={copyLabel === 'Copied' ? 'Copied' : 'Copy latest'}
                  onClick={() => void onCopyLatestQuestion(deferredTurns[deferredTurns.length - 1].question_text_for_copy)}
                  title="Copy latest question"
                  type="button"
                />
              ) : null}
              {onRenameProject ? (
                <ProjectMetadataEditor
                  disabled={renameDisabled}
                  initialTitle={project.project_name}
                  onSave={onRenameProject}
                />
              ) : null}
              {onRequestDelete ? (
                <ActionButton
                  aria-label={`Delete ${project.project_name}`}
                  disabled={renameDisabled}
                  icon={<TrashIcon />}
                  label="Delete"
                  onClick={() => onRequestDelete(project)}
                  title={`Delete ${project.project_name}`}
                  type="button"
                  variant="danger"
                />
              ) : null}
            </div>
          </div>
        </div>
      </header>

      <div className="mt-4 min-h-0 flex-1 overflow-auto rounded-[2rem] border border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(248,250,252,0.92))] p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="space-y-4">
          {activeRun ? (
            <ActiveRunPanel run={activeRun} />
          ) : null}

          <TranscriptPagination
            currentPage={safeCurrentPage}
            onPageChange={(nextPage) => {
              setManualPage(nextPage)
              setFollowLatestPage(nextPage >= totalPages)
            }}
            onPageSizeChange={(nextPageSize) => {
              setPageSize(nextPageSize)
              setFollowLatestPage(true)
            }}
            pageSize={pageSize}
            totalItems={deferredTurns.length}
            totalPages={totalPages}
          />

          {pagedTurns.map((turn) => (
            <TurnCard
              key={turn.id}
              copyLabel={copyLabel}
              isLatestActiveTurn={!turn.answer_text && turn.id === latestTurnId}
              onCopyLatestQuestion={onCopyLatestQuestion}
              run={runByTurnNo.get(turn.turn_no) ?? null}
              turn={turn}
            />
          ))}

          {pagedTurns.length === 0 ? (
            <div className="rounded-[1.75rem] border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-500">
              Interview not started yet. Use the left panel to start the first turn.
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
