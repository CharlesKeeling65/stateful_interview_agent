import { useDeferredValue, useMemo, useState } from 'react'

import { getDisplayStageLabel, type Locale, type Translator } from '../i18n'
import type { ProjectRead, RunRead, TurnRead } from '../types/api'
import { ActionButton } from './ActionButton'
import { CopyIcon, TrashIcon } from './Icons'
import { ProjectMetadataEditor } from './ProjectMetadataEditor'
import { TranscriptPagination } from './TranscriptPagination'
import { TurnCard } from './TurnCard'

type TranscriptPanelProps = {
  copyLabel?: string | null
  onCopyLatestQuestion?: (text: string) => Promise<void> | void
  onDeleteTurnTail?: (turnId: number) => Promise<void> | void
  onRegenerateCurrentQuestion?: (turnId: number, humanReview?: TurnRead['human_review']) => Promise<void> | void
  onRequestDelete?: (project: ProjectRead) => void
  onRenameProject?: (nextTitle: string) => Promise<void> | void
  project: ProjectRead | null
  renameDisabled?: boolean
  regenerateWorking?: boolean
  runs?: RunRead[]
  turns: TurnRead[]
  locale?: Locale
  t: Translator
}

function EmptyState({ t }: { t: Translator }) {
  return (
    <div className="flex h-full min-h-96 items-center justify-center">
      <div className="max-w-md rounded-[2rem] border border-dashed border-slate-300 bg-white/70 px-8 py-10 text-center shadow-[0_22px_50px_rgba(148,163,184,0.12)] backdrop-blur">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
          {t('transcript.emptyEyebrow')}
        </p>
        <h2 className="mt-3 font-serif text-3xl text-slate-950">{t('transcript.emptyTitle')}</h2>
        <p className="mt-4 text-sm leading-7 text-slate-600">
          {t('transcript.emptyCopy')}
        </p>
      </div>
    </div>
  )
}

export function TranscriptPanel({
  copyLabel = null,
  onCopyLatestQuestion,
  onDeleteTurnTail,
  onRegenerateCurrentQuestion,
  onRequestDelete,
  onRenameProject,
  project,
  renameDisabled = false,
  regenerateWorking = false,
  runs = [],
  turns,
  locale = 'en',
  t,
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
    return <EmptyState t={t} />
  }

  return (
    <section className="flex h-full min-h-0 flex-col">
      <header className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-slate-500">
              {t('transcript.active')}
            </p>
            <h2 className="mt-3 font-serif text-3xl leading-tight text-slate-950">
              {t('transcript.readingTitle')}
            </h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              {t('transcript.readingCopy')}
            </p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 px-4 py-3 text-right">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{t('transcript.stageSummary')}</p>
              <p className="mt-1 text-sm font-semibold text-slate-950">{getDisplayStageLabel(project.current_stage, locale)}</p>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              {onCopyLatestQuestion && deferredTurns.length > 0 ? (
                <ActionButton
                  aria-label={t('transcript.copyLatest')}
                  icon={<CopyIcon />}
                  label={copyLabel === 'Copied' ? t('transcript.copied') : t('transcript.copyLatest')}
                  onClick={() => void onCopyLatestQuestion(deferredTurns[deferredTurns.length - 1].question_text_for_copy)}
                  title={t('transcript.copyLatest')}
                  type="button"
                />
              ) : null}
              {onRenameProject ? (
                <ProjectMetadataEditor
                  disabled={renameDisabled}
                  initialTitle={project.project_name}
                  onSave={onRenameProject}
                  t={t}
                />
              ) : null}
              {onRequestDelete ? (
                <ActionButton
                  aria-label={`${t('sidebar.delete')} ${project.project_name}`}
                  disabled={renameDisabled}
                  icon={<TrashIcon />}
                  label={t('sidebar.delete')}
                  onClick={() => onRequestDelete(project)}
                  title={`${t('sidebar.delete')} ${project.project_name}`}
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
            t={t}
            totalItems={deferredTurns.length}
            totalPages={totalPages}
          />

          {pagedTurns.map((turn) => (
            <TurnCard
              key={turn.id}
              copyLabel={copyLabel}
              isLatestActiveTurn={!turn.answer_text && turn.id === latestTurnId}
              locale={locale}
              onCopyLatestQuestion={onCopyLatestQuestion}
              onDeleteFromTurn={onDeleteTurnTail}
              onRegenerateCurrentQuestion={onRegenerateCurrentQuestion}
              regenerateWorking={regenerateWorking && turn.id === latestTurnId}
              run={runByTurnNo.get(turn.turn_no) ?? null}
              t={t}
              turn={turn}
            />
          ))}

          {pagedTurns.length === 0 ? (
            <div className="rounded-[1.75rem] border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-500">
              {t('transcript.emptyTurns')}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
