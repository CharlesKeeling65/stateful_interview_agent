import { useState } from 'react'

import { AnswerComposer } from './components/AnswerComposer'
import { ConfirmDeleteDialog } from './components/ConfirmDeleteDialog'
import { ProjectSidebar } from './components/ProjectSidebar'
import { StatusPanel } from './components/StatusPanel'
import { TranscriptPanel } from './components/TranscriptPanel'
import type { ProjectRead } from './types/api'
import { useProject } from './hooks/useProject'
import { copyTextToClipboard, exportTextFile } from './utils/export'
import { hasInterviewStarted, isProjectFinished } from './utils/status'

function App() {
  const {
    busyAction,
    createDemoProject,
    createProject,
    deleteProject,
    error,
    lastMessage,
    loading,
    project,
    projects,
    runs,
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
  const [exportLabel, setExportLabel] = useState<string | null>(null)
  const [latestQuestionCopyLabel, setLatestQuestionCopyLabel] = useState<string | null>(null)
  const [projectPendingDelete, setProjectPendingDelete] = useState<ProjectRead | null>(null)

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
    creating: 'Creating...',
    starting: 'Starting...',
    submitting: 'Generating...',
    updating: 'Saving...',
    deleting: 'Deleting...',
    selecting: 'Loading...',
    initializing: 'Loading...',
  } as const
  const workingLabel = busyAction ? workingLabelMap[busyAction] : null

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(14,165,233,0.16),_transparent_26%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] text-slate-950">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[size:24px_24px] opacity-40" />

      <div className="relative mx-auto min-h-screen w-full max-w-[1800px] px-4 py-4 sm:px-6 lg:px-8">
        <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[20rem_minmax(0,1fr)] xl:grid-cols-[22rem_minmax(0,1fr)_24rem]">
          <ProjectSidebar
            activeProjectId={project?.id ?? null}
            busyAction={busyAction}
            projects={projects}
            onCreate={createProject}
            onCreateDemo={createDemoProject}
            onRequestDelete={setProjectPendingDelete}
            onSelectProject={selectProject}
            disabled={loading}
          />

          <div className="flex min-h-[70vh] flex-col gap-4">
            <div className="min-h-0 flex-1">
              <TranscriptPanel
                key={project?.id ?? 'empty-project'}
                activeRun={activeRun}
                copyLabel={latestQuestionCopyLabel}
                onCopyLatestQuestion={handleCopyLatestQuestion}
                onRequestDelete={setProjectPendingDelete}
                onRenameProject={
                  project ? async (nextTitle: string) => updateProject(project.id, { project_name: nextTitle }) : undefined
                }
                project={project}
                renameDisabled={loading}
                runs={runs}
                turns={turns}
              />
            </div>

            <AnswerComposer
              estimateDraftUsage={estimateDraftUsage}
              onSubmit={submitNext}
              disabled={loading || !project || !projectStarted || projectFinished}
              projectFinished={projectFinished}
              projectStarted={projectStarted}
              workingLabel={busyAction === 'submitting' ? workingLabel : null}
            />
          </div>

          <div className="lg:col-span-2 xl:col-span-1">
            <StatusPanel
              errorMessage={error}
              exportLabel={exportLabel}
              infoMessage={lastMessage}
              onCopyTranscript={handleCopyTranscript}
              onExportMarkdown={handleExportMarkdown}
              onExportText={handleExportText}
              onStart={startProject}
              project={project}
              status={status}
              transcript={transcript}
              working={loading}
              workingLabel={workingLabel}
            />
          </div>
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
      />
    </div>
  )
}

export default App
