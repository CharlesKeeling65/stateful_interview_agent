import { useEffect, useState } from 'react'

type ProjectMetadataEditorProps = {
  disabled?: boolean
  initialTitle: string
  onSave: (nextTitle: string) => Promise<void> | void
}

export function ProjectMetadataEditor({
  disabled = false,
  initialTitle,
  onSave,
}: ProjectMetadataEditorProps) {
  const [editing, setEditing] = useState(false)
  const [draftTitle, setDraftTitle] = useState(initialTitle)

  useEffect(() => {
    setDraftTitle(initialTitle)
  }, [initialTitle])

  async function handleSave() {
    if (!draftTitle.trim() || draftTitle.trim() === initialTitle) {
      setEditing(false)
      setDraftTitle(initialTitle)
      return
    }

    await onSave(draftTitle.trim())
    setEditing(false)
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="rounded-full border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
        onClick={() => setEditing(true)}
        disabled={disabled}
      >
        Edit Title
      </button>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        className="min-w-52 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
        value={draftTitle}
        onChange={(event) => setDraftTitle(event.target.value)}
        disabled={disabled}
      />
      <button
        type="button"
        className="rounded-full bg-slate-950 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        onClick={() => void handleSave()}
        disabled={disabled || !draftTitle.trim()}
      >
        Save
      </button>
      <button
        type="button"
        className="rounded-full border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
        onClick={() => {
          setEditing(false)
          setDraftTitle(initialTitle)
        }}
        disabled={disabled}
      >
        Cancel
      </button>
    </div>
  )
}
