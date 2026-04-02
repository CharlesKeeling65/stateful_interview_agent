import { useState } from 'react'

import type { CreateProjectPayload } from '../types/api'

type CreateProjectFormProps = {
  disabled?: boolean
  workingLabel?: string | null
  onCreate: (payload: CreateProjectPayload) => Promise<void> | void
  onCreateDemo: () => Promise<void> | void
}

const DEFAULT_PROMPT =
  'You are a stateful interview agent. You must generate exactly one next English question each time. The interview must follow four stages: Panorama Mapping, Architecture Understanding, Code Detail Completion, and Use Cases & Scenarios. The conversation should remain coherent, cumulative, and non-redundant.'

export function CreateProjectForm({
  disabled = false,
  workingLabel = null,
  onCreate,
  onCreateDemo,
}: CreateProjectFormProps) {
  const [projectName, setProjectName] = useState('')
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_PROMPT)

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!projectName.trim() || !systemPrompt.trim()) {
      return
    }

    void onCreate({
      project_name: projectName.trim(),
      system_prompt: systemPrompt.trim(),
    })
  }

  return (
    <form className="space-y-3 rounded-[1.75rem] border border-white/60 bg-white/75 p-4 shadow-[0_20px_45px_rgba(148,163,184,0.18)] backdrop-blur" onSubmit={handleSubmit}>
      <div>
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
          New Project
        </p>
        <h2 className="mt-2 font-serif text-xl text-slate-950">Seed a local interview session</h2>
      </div>

      <label className="block space-y-2">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          Project Name
        </span>
        <input
          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          value={projectName}
          onChange={(event) => setProjectName(event.target.value)}
          placeholder="Stateful Interview Demo"
          disabled={disabled}
        />
      </label>

      <label className="block space-y-2">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          System Prompt
        </span>
        <textarea
          className="min-h-36 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          value={systemPrompt}
          onChange={(event) => setSystemPrompt(event.target.value)}
          disabled={disabled}
        />
      </label>

      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          disabled={disabled || !projectName.trim() || !systemPrompt.trim()}
        >
          {workingLabel ?? 'Create Project'}
        </button>
        <button
          type="button"
          className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          onClick={() => void onCreateDemo()}
          disabled={disabled}
        >
          {workingLabel === 'Creating project...' ? 'Please wait...' : 'Quick Demo'}
        </button>
      </div>
    </form>
  )
}
