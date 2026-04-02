import type { ProjectRead } from '../types/api'
import { ActionButton } from './ActionButton'
import { AlertTriangleIcon, TrashIcon } from './Icons'

type ConfirmDeleteDialogProps = {
  busy?: boolean
  onCancel: () => void
  onConfirm: (projectId: number) => Promise<void> | void
  project: ProjectRead | null
}

export function ConfirmDeleteDialog({
  busy = false,
  onCancel,
  onConfirm,
  project,
}: ConfirmDeleteDialogProps) {
  if (!project) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-[2rem] border border-white/60 bg-white/95 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.3)]">
        <div className="flex items-start gap-3">
          <span className="mt-1 inline-flex rounded-full bg-rose-100 p-2 text-rose-700">
            <AlertTriangleIcon className="size-5" />
          </span>
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-rose-500">
              Delete Project
            </p>
            <h2 className="mt-2 font-serif text-2xl text-slate-950">{project.project_name}</h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              This permanently removes the project, its turns, summaries, transcript, and recorded token usage.
            </p>
          </div>
        </div>

        <div className="mt-5 rounded-[1.5rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-900">
          This action cannot be undone.
        </div>

        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <ActionButton
            label="Cancel"
            onClick={onCancel}
            disabled={busy}
            type="button"
            variant="secondary"
          />
          <ActionButton
            icon={<TrashIcon />}
            label={busy ? 'Deleting...' : 'Delete'}
            onClick={() => void onConfirm(project.id)}
            disabled={busy}
            type="button"
            variant="danger"
          />
        </div>
      </div>
    </div>
  )
}
