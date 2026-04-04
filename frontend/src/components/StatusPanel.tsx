import type { Locale, Translator } from '../i18n'
import type { ProjectRead, ProjectStatusResponse, TranscriptResponse } from '../types/api'
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
