import { useState } from 'react'

import type { Translator } from '../i18n'
import type { CreateProjectPayload } from '../types/api'

type CreateProjectFormProps = {
  disabled?: boolean
  workingLabel?: string | null
  onCreate: (payload: CreateProjectPayload) => Promise<void> | void
  onCreateDemo: () => Promise<void> | void
  t: Translator
}

const DEFAULT_PROMPT =
  'You are a stateful interview agent. You must generate exactly one next English question each time. The interview must follow four stages: Panorama Mapping, Architecture Understanding, Code Detail Completion, and Use Cases & Scenarios. The conversation should remain coherent, cumulative, and non-redundant.'

export function CreateProjectForm({
  disabled = false,
  workingLabel = null,
  onCreate,
  onCreateDemo,
  t,
}: CreateProjectFormProps) {
  const [projectName, setProjectName] = useState('')
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_PROMPT)
  const [repoSourceType, setRepoSourceType] = useState<'none' | 'local_path' | 'git_url'>('none')
  const [repoLocalPath, setRepoLocalPath] = useState('')
  const [repoGitUrl, setRepoGitUrl] = useState('')
  const [repoGitRef, setRepoGitRef] = useState('')

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!projectName.trim() || !systemPrompt.trim()) {
      return
    }

    void onCreate({
      project_name: projectName.trim(),
      system_prompt: systemPrompt.trim(),
      agent_mode: 'understand_current_code',
      answer_provider_type: 'opencode',
      answer_automation_enabled: true,
      repository: {
        source_type: repoSourceType,
        local_path: repoSourceType === 'local_path' ? repoLocalPath.trim() || null : null,
        git_url: repoSourceType === 'git_url' ? repoGitUrl.trim() || null : null,
        git_ref: repoSourceType === 'git_url' ? repoGitRef.trim() || null : null,
      },
    })
  }

  return (
    <form className="space-y-3 rounded-[1.75rem] border border-white/60 bg-white/75 p-4 shadow-[0_20px_45px_rgba(148,163,184,0.18)] backdrop-blur" onSubmit={handleSubmit}>
      <div>
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
          {t('sidebar.newProject')}
        </p>
        <h2 className="mt-2 font-serif text-xl text-slate-950">{t('sidebar.seedSession')}</h2>
      </div>

      <label className="block space-y-2">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          {t('sidebar.projectName')}
        </span>
        <input
          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          value={projectName}
          onChange={(event) => setProjectName(event.target.value)}
          placeholder={t('sidebar.demoPlaceholder')}
          disabled={disabled}
        />
      </label>

      <label className="block space-y-2">
        <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          {t('sidebar.systemPrompt')}
        </span>
        <textarea
          className="min-h-36 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          value={systemPrompt}
          onChange={(event) => setSystemPrompt(event.target.value)}
          disabled={disabled}
        />
      </label>

      <div className="grid gap-3">
        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
            {t('sidebar.repositorySource')}
          </span>
          <select
            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
            value={repoSourceType}
            onChange={(event) => setRepoSourceType(event.target.value as 'none' | 'local_path' | 'git_url')}
            disabled={disabled}
          >
            <option value="none">{t('sidebar.repositoryNone')}</option>
            <option value="local_path">{t('sidebar.repositoryLocal')}</option>
            <option value="git_url">{t('sidebar.repositoryGit')}</option>
          </select>
        </label>

        {repoSourceType === 'local_path' ? (
          <label className="block space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
              {t('sidebar.repositoryPath')}
            </span>
            <input
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
              value={repoLocalPath}
              onChange={(event) => setRepoLocalPath(event.target.value)}
              placeholder="/absolute/path/to/repository"
              disabled={disabled}
            />
          </label>
        ) : null}

        {repoSourceType === 'git_url' ? (
          <>
            <label className="block space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                {t('sidebar.repositoryUrl')}
              </span>
              <input
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={repoGitUrl}
                onChange={(event) => setRepoGitUrl(event.target.value)}
                placeholder="https://github.com/org/repo.git"
                disabled={disabled}
              />
            </label>
            <label className="block space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                {t('sidebar.repositoryRef')}
              </span>
              <input
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                value={repoGitRef}
                onChange={(event) => setRepoGitRef(event.target.value)}
                placeholder={t('sidebar.repositoryRefPlaceholder')}
                disabled={disabled}
              />
            </label>
          </>
        ) : null}

        <p className="text-xs leading-6 text-slate-500">
          {t('sidebar.repositoryHint')}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          disabled={disabled || !projectName.trim() || !systemPrompt.trim()}
        >
          {workingLabel ?? t('sidebar.createProject')}
        </button>
        <button
          type="button"
          className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          onClick={() => void onCreateDemo()}
          disabled={disabled}
        >
          {workingLabel ? t('sidebar.pleaseWait') : t('sidebar.quickDemo')}
        </button>
      </div>
    </form>
  )
}
