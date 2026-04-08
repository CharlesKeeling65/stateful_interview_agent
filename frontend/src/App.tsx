import { useEffect, useMemo, useState } from 'react'

import { AnswerComposer } from './components/AnswerComposer'
import { ConfirmDeleteDialog } from './components/ConfirmDeleteDialog'
import { ActiveRunPanel } from './components/ExecutionTraceSection'
import { GenerationControlPanel } from './components/GenerationControlPanel'
import { ProjectSidebar } from './components/ProjectSidebar'
import { RegenerationFeedbackBanner } from './components/RegenerationFeedbackBanner'
import { StatsDashboard } from './components/StatsDashboard'
import { StatusPanel } from './components/StatusPanel'
import { TranscriptPanel } from './components/TranscriptPanel'
import { LOCALE_STORAGE_KEY, createTranslator, getDisplayStageLabel, normalizeLocale, type Locale } from './i18n'
import type { ProjectRead } from './types/api'
import { useProject } from './hooks/useProject'
import { copyTextToClipboard, exportTextFile } from './utils/export'
import { formatDurationMs } from './utils/format'
import { hasInterviewStarted, isProjectFinished } from './utils/status'

function App() {
  const {
    busyAction,
    createDemoProject,
    createProject,
    deleteProject,
    error,
    lastMessageKey,
    lastRegenerationFeedback,
    loading,
    project,
    projects,
    regenerateCurrentQuestion,
    runs,
    runOpenCodePlanStep,
    saveAnswer,
    selectProject,
    startProject,
    status,
    submitNext,
    transcript,
    turns,
    updateProject,
    estimateDraftUsage,
    activeRun,
  } = useProject()
  const [locale, setLocale] = useState<Locale>(() => normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY)))
  const [page, setPage] = useState<'workspace' | 'analytics'>('workspace')
  const [exportLabel, setExportLabel] = useState<string | null>(null)
  const [latestQuestionCopyLabel, setLatestQuestionCopyLabel] = useState<string | null>(null)
  const [projectPendingDelete, setProjectPendingDelete] = useState<ProjectRead | null>(null)
  const [skippedOpencodeTurnId, setSkippedOpencodeTurnId] = useState<number | null>(null)
  const t = useMemo(() => createTranslator(locale), [locale])

  useEffect(() => {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  }, [locale])

  async function handleCopyTranscript() {
    if (!transcript?.transcript) {
      return
    }

    setExportLabel('Copying...')
    try {
      await copyTextToClipboard(transcript.transcript)
      setExportLabel('Copied')
    } finally {
      window.setTimeout(() => setExportLabel(null), 1200)
    }
  }

  async function handleCopyLatestQuestion(text: string) {
    setLatestQuestionCopyLabel('Copied')
    try {
      await copyTextToClipboard(text)
    } finally {
      window.setTimeout(() => setLatestQuestionCopyLabel(null), 1200)
    }
  }

  function getExportFilename(extension: 'txt' | 'md') {
    const projectName =
      project?.project_name
        ?.trim()
        .replace(/[^a-z0-9-_]+/gi, '-')
        .replace(/^-+|-+$/g, '')
        .toLowerCase() || 'stateful-interview'

    return `${projectName}-transcript.${extension}`
  }

  function handleExportText() {
    if (!transcript?.transcript) {
      return
    }

    setExportLabel('Exporting .txt...')
    exportTextFile(
      getExportFilename('txt'),
      transcript.transcript,
      'text/plain;charset=utf-8',
    )
    window.setTimeout(() => setExportLabel(null), 1200)
  }

  function handleExportMarkdown() {
    if (!transcript?.transcript) {
      return
    }

    const markdown = `# ${transcript.project_name}\n\n${transcript.transcript}\n`
    setExportLabel('Exporting .md...')
    exportTextFile(
      getExportFilename('md'),
      markdown,
      'text/markdown;charset=utf-8',
    )
    window.setTimeout(() => setExportLabel(null), 1200)
  }

  const projectStarted = hasInterviewStarted(project)
  const projectFinished = isProjectFinished(project, status)
  const workingLabelMap = {
    creating: `${t('sidebar.createProject')}...`,
    starting: `${t('status.start')}...`,
    saving_answer: `${t('composer.saveAnswer')}...`,
    sending_opencode: `${t('composer.sendToOpenCode')}...`,
    generating_next: `${t('status.generating')}`,
    regenerating: `${t('status.regeneratingCurrent')}`,
    updating: `${t('sidebar.save')}...`,
    deleting: `${t('sidebar.delete')}...`,
    selecting: locale === 'zh-CN' ? '加载中...' : 'Loading...',
    initializing: locale === 'zh-CN' ? '加载中...' : 'Loading...',
  } as const
  const workingLabel = busyAction ? workingLabelMap[busyAction] : null
  const infoMessage = lastMessageKey ? t(lastMessageKey as Parameters<typeof t>[0]) : ''
  const latestTurn = turns[turns.length - 1] ?? null
  const opencodePlanEnabled = Boolean(
    project &&
    project.answer_provider_type === 'opencode' &&
    latestTurn &&
    !latestTurn.answer_text &&
    latestTurn.id !== skippedOpencodeTurnId,
  )

  useEffect(() => {
    if (!latestTurn || latestTurn.answer_text) {
      setSkippedOpencodeTurnId(null)
      return
    }
    if (latestTurn.id !== skippedOpencodeTurnId) {
      setSkippedOpencodeTurnId(null)
    }
  }, [latestTurn?.id, latestTurn?.answer_text])
  const overviewStats = [
    {
      label: t('app.activeSession'),
      value: project?.project_name ?? t('app.noSelection'),
    },
    {
      label: t('app.turns'),
      value: String(status?.turn_count ?? project?.turn_count ?? 0),
    },
    {
      label: t('app.stage'),
      value: getDisplayStageLabel(status?.current_stage ?? project?.current_stage, locale),
    },
    {
      label: t('app.runtime'),
      value: formatDurationMs(status?.cumulative_generation_time_ms ?? 0, locale),
    },
  ]

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(14,165,233,0.16),_transparent_26%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] text-slate-950">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[size:24px_24px] opacity-40" />

      <div className="relative mx-auto min-h-screen w-full max-w-[1800px] px-4 py-4 sm:px-6 lg:px-8">
        <section className="mb-4 rounded-[2rem] border border-white/60 bg-white/80 p-5 shadow-[0_20px_50px_rgba(148,163,184,0.16)] backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.32em] text-slate-500">
                {t('app.interviewFlow')}
              </p>
              <h1 className="mt-3 font-serif text-4xl leading-tight text-slate-950">
                {t('app.title')}
              </h1>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <nav className="inline-flex rounded-full border border-slate-200 bg-white p-1">
                {([
                  ['workspace', t('nav.workspace')],
                  ['analytics', t('nav.analytics')],
                ] as const).map(([value, label]) => {
                  const active = page === value
                  return (
                    <button
                      key={value}
                      type="button"
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        active ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100'
                      }`}
                      onClick={() => setPage(value)}
                      aria-pressed={active}
                    >
                      {label}
                    </button>
                  )
                })}
              </nav>

              <div className="inline-flex rounded-full border border-slate-200 bg-white p-1">
                {(['en', 'zh-CN'] as const).map((option) => {
                  const active = option === locale
                  return (
                    <button
                      key={option}
                      type="button"
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        active ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100'
                      }`}
                      onClick={() => setLocale(option)}
                      aria-pressed={active}
                    >
                      {option === 'en' ? t('language.enLabel') : t('language.zhLabel')}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
            {page === 'workspace' ? t('app.subtitle') : t('analytics.subtitle')}
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {overviewStats.map((item) => (
              <div key={item.label} className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 px-4 py-4">
                <p className="text-[0.64rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {item.label}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-950">{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
          <ProjectSidebar
            activeProjectId={project?.id ?? null}
            busyAction={busyAction}
            locale={locale}
            projects={projects}
            onCreate={createProject}
            onCreateDemo={createDemoProject}
            onRequestDelete={setProjectPendingDelete}
            onSelectProject={selectProject}
            disabled={loading}
            t={t}
          />

          {page === 'workspace' ? (
            <div className="flex min-h-[70vh] flex-col gap-4">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.95fr)]">
                <div className="flex min-h-0 flex-col gap-4">
                  <AnswerComposer
                    key={`${project?.id ?? 'no-project'}-${latestTurn?.id ?? 'no-turn'}-${latestTurn?.answer_text_for_display ?? latestTurn?.answer_text ?? ''}`}
                    estimateDraftUsage={estimateDraftUsage}
                    initialAnswer={latestTurn?.answer_text_for_display ?? latestTurn?.answer_text ?? ''}
                    locale={locale}
                    onSave={saveAnswer}
                    disabled={loading || !project || !projectStarted || projectFinished}
                    projectFinished={projectFinished}
                    projectStarted={projectStarted}
                    savedAnswer={latestTurn?.answer_text_for_display ?? latestTurn?.answer_text ?? null}
                    workingLabel={busyAction === 'saving_answer' ? workingLabel : null}
                    t={t}
                  />

                  <GenerationControlPanel
                    canGenerateNext={Boolean(status?.latest_turn_ready_for_next_generation)}
                    disabled={loading || !project || !projectStarted || projectFinished}
                    estimateDraftUsage={estimateDraftUsage}
                    locale={locale}
                    onGenerateNext={submitNext}
                    onOpenCodeSend={async () => {
                      setSkippedOpencodeTurnId(null)
                      await runOpenCodePlanStep(null)
                    }}
                    onOpenCodeRegenerateCurrentQuestion={async (humanReview) => {
                      if (!latestTurn) {
                        return
                      }
                      setSkippedOpencodeTurnId(null)
                      await regenerateCurrentQuestion(latestTurn.id, humanReview)
                    }}
                    onOpenCodeSkip={() => latestTurn ? setSkippedOpencodeTurnId(latestTurn.id) : undefined}
                    opencodePlan={opencodePlanEnabled && latestTurn ? {
                      enabled: true,
                      pendingQuestionText: latestTurn.question_text_for_copy,
                      sessionId: project?.opencode_session_id ?? null,
                    } : null}
                    pendingGate={project?.pending_gate ?? null}
                    projectFinished={projectFinished}
                    projectStarted={projectStarted}
                    savedAnswer={latestTurn?.answer_text ?? null}
                    workingLabel={busyAction === 'generating_next' || busyAction === 'sending_opencode' ? workingLabel : null}
                    t={t}
                  />

                  {activeRun ? (
                    <ActiveRunPanel
                      locale={locale}
                      run={activeRun}
                      t={t}
                      variant={busyAction === 'regenerating' ? 'regenerate' : 'next'}
                    />
                  ) : null}

                  {lastRegenerationFeedback ? (
                    <RegenerationFeedbackBanner
                      feedback={lastRegenerationFeedback.applied_changes}
                      locale={locale}
                      t={t}
                      tokensUsed={lastRegenerationFeedback.usage_summary.total_tokens}
                    />
                  ) : null}
                </div>

                <StatusPanel
                  errorMessage={error}
                  exportLabel={exportLabel}
                  infoMessage={infoMessage}
                  locale={locale}
                  onCopyTranscript={handleCopyTranscript}
                  onExportMarkdown={handleExportMarkdown}
                  onExportText={handleExportText}
                  onStart={startProject}
                  onUpdateRepository={
                    project ? async (payload) => updateProject(project.id, payload) : undefined
                  }
                  project={project}
                  status={status}
                  t={t}
                  transcript={transcript}
                  working={loading}
                  workingLabel={busyAction === 'starting' ? workingLabel : null}
                />
              </div>

              <div className="min-h-0 flex-1">
                <TranscriptPanel
                  key={project?.id ?? 'empty-project'}
                  copyLabel={latestQuestionCopyLabel}
                  locale={locale}
                  onCopyLatestQuestion={handleCopyLatestQuestion}
                  onRegenerateCurrentQuestion={regenerateCurrentQuestion}
                  onRequestDelete={setProjectPendingDelete}
                  onRenameProject={
                    project ? async (nextTitle: string) => updateProject(project.id, { project_name: nextTitle }) : undefined
                  }
                  project={project}
                  regenerateWorking={busyAction === 'regenerating'}
                  renameDisabled={loading}
                  runs={runs}
                  t={t}
                  turns={turns}
                />
              </div>
            </div>
          ) : (
            <StatsDashboard
              locale={locale}
              project={project}
              projects={projects}
              status={status}
              t={t}
              turns={turns}
            />
          )}
        </div>
      </div>

      <ConfirmDeleteDialog
        busy={busyAction === 'deleting'}
        onCancel={() => setProjectPendingDelete(null)}
        onConfirm={async (projectId) => {
          await deleteProject(projectId)
          setProjectPendingDelete(null)
        }}
        project={projectPendingDelete}
        t={t}
      />
    </div>
  )
}

export default App
