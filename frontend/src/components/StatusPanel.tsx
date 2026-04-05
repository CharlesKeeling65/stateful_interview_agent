import { useState } from 'react'

import type { Locale, Translator } from '../i18n'
import type { ProjectRead, ProjectStatusResponse, TranscriptResponse, UpdateProjectPayload } from '../types/api'
import { getDisplayStageLabel } from '../i18n'
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
  locale?: Locale
  onCopyTranscript: () => Promise<void> | void
  onExportMarkdown: () => void
  onExportText: () => void
  onStart: () => Promise<void> | void
  onUpdateRepository?: (payload: UpdateProjectPayload) => Promise<void> | void
  project: ProjectRead | null
  status: ProjectStatusResponse | null
  t: Translator
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
  locale = 'en',
  onCopyTranscript,
  onExportMarkdown,
  onExportText,
  onStart,
  onUpdateRepository,
  project,
  status,
  t,
  transcript,
  working = false,
  workingLabel = null,
}: StatusPanelProps) {
  const projectFinished = isProjectFinished(project, status)
  const started = hasInterviewStarted(project)
  const canExport = Boolean(transcript?.transcript)
  const repositoryProject = project && project.repository.source_type !== 'none' ? project : null
  const [repositoryEditorOpen, setRepositoryEditorOpen] = useState(false)
  const [repoSourceType, setRepoSourceType] = useState<'none' | 'local_path' | 'git_url'>('none')
  const [repoLocalPath, setRepoLocalPath] = useState('')
  const [repoGitUrl, setRepoGitUrl] = useState('')
  const [repoGitRef, setRepoGitRef] = useState('')

  function resetRepositoryEditor() {
    if (!project) {
      setRepoSourceType('none')
      setRepoLocalPath('')
      setRepoGitUrl('')
      setRepoGitRef('')
      return
    }
    setRepoSourceType((project.repository.source_type as 'none' | 'local_path' | 'git_url') ?? 'none')
    setRepoLocalPath(project.repository.local_path ?? '')
    setRepoGitUrl(project.repository.git_url ?? '')
    setRepoGitRef(project.repository.git_ref ?? '')
  }

  function handleRepositorySave() {
    if (!project || !onUpdateRepository) {
      return
    }

    void onUpdateRepository({
      repository: {
        source_type: repoSourceType,
        local_path: repoSourceType === 'local_path' ? repoLocalPath.trim() || null : null,
        git_url: repoSourceType === 'git_url' ? repoGitUrl.trim() || null : null,
        git_ref: repoSourceType === 'git_url' ? repoGitRef.trim() || null : null,
      },
    })
    setRepositoryEditorOpen(false)
  }

  function openRepositoryEditor() {
    resetRepositoryEditor()
    setRepositoryEditorOpen(true)
  }

  return (
    <aside className="flex h-full flex-col gap-4">
      <section className="rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              {t('status.projectStatus')}
            </p>
            <h2 className="mt-3 font-serif text-2xl text-slate-950">{t('status.snapshot')}</h2>
          </div>
          <ActionButton
            disabled={!project || started || projectFinished || working}
            icon={<PlayIcon />}
            label={workingLabel ?? t('status.start')}
            onClick={() => void onStart()}
            type="button"
            variant="primary"
          />
        </div>

        {project ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <StatusItem label={t('status.projectId')} value={`#${project.id}`} />
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
                {t('status.projectStatus')}
              </p>
              <div className="mt-2">
                <ProjectStatusBadge locale={locale} project={project} status={status} />
              </div>
            </div>
            <StatusItem
              label={t('status.currentStage')}
              value={getDisplayStageLabel(status?.current_stage ?? project.current_stage, locale)}
            />
            <StatusItem label={t('app.turns')} value={String(status?.turn_count ?? project.turn_count)} />
            <StatusItem label={t('status.runs')} value={String(status?.run_count ?? 0)} />
            <StatusItem
              label={t('status.totalGeneration')}
              value={formatDurationMs(status?.cumulative_generation_time_ms ?? 0, locale)}
            />
            <StatusItem
              label={t('status.averageRun')}
              value={formatDurationMs(status?.average_run_duration_ms ?? 0, locale)}
            />
            <StatusItem
              label={t('status.minimumGoal')}
              value={formatBooleanLabel(status?.minimum_goal_reached, locale, {
                trueLabel: t('status.reached'),
                falseLabel: t('status.notYet'),
              })}
            />
            <StatusItem
              label={t('status.latestAnswered')}
              value={formatBooleanLabel(status?.latest_turn_answered, locale, {
                trueLabel: locale === 'zh-CN' ? '已回答' : 'Answered',
                falseLabel: t('status.waiting'),
                nullLabel: t('status.noTurns'),
              })}
            />
            <StatusItem
              label={t('status.repoSource')}
              value={
                project.repository.source_type === 'local_path'
                  ? (locale === 'zh-CN' ? '本地路径' : 'Local path')
                  : project.repository.source_type === 'git_url'
                    ? (locale === 'zh-CN' ? '仓库链接' : 'Git URL')
                    : t('status.repoNotConfigured')
              }
            />
            <StatusItem
              label={t('status.repoCommit')}
              value={project.repository.commit_sha?.slice(0, 12) || t('status.repoUnknown')}
            />
            <StatusItem
              label={t('status.repoFiles')}
              value={String(project.repository_manifest.file_count ?? 0)}
            />
            <StatusItem
              label={t('status.repoSymbols')}
              value={String(project.repository_manifest.symbol_count ?? 0)}
            />
          </div>
        ) : (
          <p className="mt-5 text-sm leading-7 text-slate-600">
            {t('status.noProject')}
          </p>
        )}

        {repositoryProject ? (
          <div className="mt-5 rounded-[1.5rem] border border-slate-200 bg-slate-50/70 px-4 py-4">
            <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
              {t('status.repository')}
            </p>
            <p className="mt-3 break-all text-sm leading-6 text-slate-700">
              {repositoryProject.repository.source_type === 'local_path'
                ? repositoryProject.repository.local_path
                : repositoryProject.repository.git_url}
            </p>
            {repositoryProject.repository.git_ref ? (
              <p className="mt-2 text-xs leading-6 text-slate-500">
                {t('status.repoRef')}: {repositoryProject.repository.git_ref}
              </p>
            ) : null}
            {repositoryProject.repository_manifest.key_files.length > 0 ? (
              <p className="mt-2 text-xs leading-6 text-slate-500">
                {t('status.repoKeyFiles')}: {repositoryProject.repository_manifest.key_files.slice(0, 4).join(', ')}
              </p>
            ) : null}
          </div>
        ) : null}

        {project ? (
          <div className="mt-5 rounded-[1.5rem] border border-slate-200 bg-slate-50/70 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[0.64rem] font-semibold uppercase tracking-[0.22em] text-slate-500">
                  {t('status.repositorySettings')}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  {t('status.repositorySettingsHint')}
                </p>
              </div>
              <ActionButton
                aria-label={t('status.editRepository')}
                disabled={working || !onUpdateRepository}
                label={repositoryEditorOpen ? t('sidebar.cancel') : t('status.editRepository')}
                onClick={() => {
                  if (repositoryEditorOpen) {
                    resetRepositoryEditor()
                    setRepositoryEditorOpen(false)
                    return
                  }
                  openRepositoryEditor()
                }}
                type="button"
              />
            </div>

            {repositoryEditorOpen ? (
              <div className="mt-4 grid gap-3">
                <label className="block space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                    {t('sidebar.repositorySource')}
                  </span>
                  <select
                    aria-label={t('sidebar.repositorySource')}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                    value={repoSourceType}
                    onChange={(event) => setRepoSourceType(event.target.value as 'none' | 'local_path' | 'git_url')}
                    disabled={working}
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
                      aria-label={t('sidebar.repositoryPath')}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                      value={repoLocalPath}
                      onChange={(event) => setRepoLocalPath(event.target.value)}
                      disabled={working}
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
                        aria-label={t('sidebar.repositoryUrl')}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                        value={repoGitUrl}
                        onChange={(event) => setRepoGitUrl(event.target.value)}
                        disabled={working}
                      />
                    </label>
                    <label className="block space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                        {t('sidebar.repositoryRef')}
                      </span>
                      <input
                        aria-label={t('sidebar.repositoryRef')}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
                        value={repoGitRef}
                        onChange={(event) => setRepoGitRef(event.target.value)}
                        disabled={working}
                      />
                    </label>
                  </>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  <ActionButton
                    aria-label={t('status.saveRepository')}
                    disabled={
                      working
                      || !onUpdateRepository
                      || (repoSourceType === 'local_path' && !repoLocalPath.trim())
                      || (repoSourceType === 'git_url' && !repoGitUrl.trim())
                    }
                    label={t('status.saveRepository')}
                    onClick={handleRepositorySave}
                    type="button"
                    variant="primary"
                  />
                  <ActionButton
                    aria-label={t('sidebar.cancel')}
                    disabled={working}
                    label={t('sidebar.cancel')}
                    onClick={() => {
                      resetRepositoryEditor()
                      setRepositoryEditorOpen(false)
                    }}
                    type="button"
                  />
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

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
            <TokenUsagePanel
              label={locale === 'zh-CN' ? '会话 Token 使用' : 'Session token usage'}
              locale={locale}
              summary={status.usage_summary}
              t={t}
            />
          </div>
        ) : null}
      </section>

      <section className="flex min-h-0 flex-1 flex-col rounded-[2rem] border border-white/60 bg-white/85 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-slate-500">
              {t('status.export')}
            </p>
            <h2 className="mt-3 font-serif text-2xl text-slate-950">{t('status.sessionHealth')}</h2>
          </div>
        </div>

        <div className="mt-5 rounded-[1.75rem] border border-slate-200 bg-slate-50/80 p-4">
          <p className="text-sm leading-7 text-slate-600">
            {t('status.exportHint')}
          </p>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <ActionButton
              disabled={!canExport}
              icon={<CopyIcon />}
              label={
                exportLabel === 'Copying...' ? `${t('status.copyTranscript')}...`
                  : exportLabel === 'Copied' ? t('transcript.copied')
                    : t('status.copyTranscript')
              }
              onClick={() => void onCopyTranscript()}
              type="button"
            />
            <ActionButton
              disabled={!canExport}
              icon={<DownloadIcon />}
              label={exportLabel === 'Exporting .txt...' ? `${t('status.exportTxt')}...` : t('status.exportTxt')}
              onClick={onExportText}
              type="button"
            />
            <ActionButton
              disabled={!canExport}
              icon={<DownloadIcon />}
              label={exportLabel === 'Exporting .md...' ? `${t('status.exportMd')}...` : t('status.exportMd')}
              onClick={onExportMarkdown}
              type="button"
            />
          </div>
        </div>

        <p className="mt-3 text-xs leading-6 text-slate-500">
          {canExport
            ? t('status.exportReady')
            : t('status.exportLocked')}
        </p>
      </section>
    </aside>
  )
}
