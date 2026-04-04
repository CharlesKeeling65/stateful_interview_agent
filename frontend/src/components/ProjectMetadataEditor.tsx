import { useEffect, useState } from 'react'

import type { Translator } from '../i18n'
import { ActionButton } from './ActionButton'
import { CheckIcon, PencilIcon } from './Icons'

type ProjectMetadataEditorProps = {
  disabled?: boolean
  initialTitle: string
  onSave: (nextTitle: string) => Promise<void> | void
  t: Translator
}

export function ProjectMetadataEditor({
  disabled = false,
  initialTitle,
  onSave,
  t,
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
      <ActionButton
        aria-label={t('sidebar.editProjectTitle')}
        disabled={disabled}
        icon={<PencilIcon />}
        label={t('sidebar.rename')}
        onClick={() => setEditing(true)}
        title={t('sidebar.editProjectTitle')}
        type="button"
      />
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
      <ActionButton
        disabled={disabled || !draftTitle.trim()}
        icon={<CheckIcon />}
        label={t('sidebar.save')}
        onClick={() => void handleSave()}
        type="button"
        variant="primary"
      />
      <ActionButton
        onClick={() => {
          setEditing(false)
          setDraftTitle(initialTitle)
        }}
        disabled={disabled}
        label={t('sidebar.cancel')}
        type="button"
      />
    </div>
  )
}
