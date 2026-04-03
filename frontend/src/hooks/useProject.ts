import { startTransition, useEffect, useEffectEvent, useState } from 'react'

import {
  createProject,
  deleteProject,
  getProject,
  getLatestProjectRun,
  getProjectRuns,
  getProjectStatus,
  getProjectTranscript,
  getProjectTurns,
  listProjects,
  startProject,
  submitNext,
  updateProject,
} from '../api/client'
import type {
  CreateProjectPayload,
  HumanReviewInput,
  ProjectRead,
  ProjectStatusResponse,
  RunRead,
  TranscriptResponse,
  TurnRead,
} from '../types/api'
import { parseApiDateMs } from '../utils/format'
import { estimateNextOutputTokens, estimateNextPromptTokens, estimateTokenCount } from '../utils/tokens'

const SELECTED_PROJECT_STORAGE_KEY = 'stateful-interview-agent:selected-project-id'

type ProjectDetails = {
  project: ProjectRead
  runs: RunRead[]
  turns: TurnRead[]
  status: ProjectStatusResponse
  transcript: TranscriptResponse
}

export type BusyAction =
  | 'initializing'
  | 'selecting'
  | 'creating'
  | 'starting'
  | 'submitting'
  | 'updating'
  | 'deleting'
  | null

async function loadProjectDetails(projectId: number): Promise<ProjectDetails> {
  const [project, turns, status, transcript, runs] = await Promise.all([
    getProject(projectId),
    getProjectTurns(projectId),
    getProjectStatus(projectId),
    getProjectTranscript(projectId),
    getProjectRuns(projectId).catch(() => []),
  ])

  return { project, turns, status, transcript, runs }
}

const DEFAULT_SYSTEM_PROMPT =
  'You are a stateful interview agent. You must generate exactly one next English question each time. The interview must follow four stages: Panorama Mapping, Architecture Understanding, Code Detail Completion, and Use Cases & Scenarios. The conversation should remain coherent, cumulative, and non-redundant.'

export function useProject() {
  const [projects, setProjects] = useState<ProjectRead[]>([])
  const [project, setProject] = useState<ProjectRead | null>(null)
  const [turns, setTurns] = useState<TurnRead[]>([])
  const [status, setStatus] = useState<ProjectStatusResponse | null>(null)
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null)
  const [runs, setRuns] = useState<RunRead[]>([])
  const [activeRun, setActiveRun] = useState<RunRead | null>(null)
  const [loading, setLoading] = useState(false)
  const [busyAction, setBusyAction] = useState<BusyAction>(null)
  const [error, setError] = useState('')
  const [lastMessage, setLastMessage] = useState('')

  async function refreshProjects(preferredProjectId?: number) {
    const items = await listProjects()
    startTransition(() => {
      setProjects(items)
    })

    const persistedProjectId = Number(localStorage.getItem(SELECTED_PROJECT_STORAGE_KEY))
    const fallbackProjectId = project?.id ?? items[0]?.id
    const nextProjectId =
      preferredProjectId ??
      (Number.isFinite(persistedProjectId) &&
      items.some((item) => item.id === persistedProjectId)
        ? persistedProjectId
        : fallbackProjectId)

    if (nextProjectId) {
      await selectProject(nextProjectId)
    } else {
      startTransition(() => {
        setProject(null)
        setTurns([])
        setStatus(null)
        setTranscript(null)
        setRuns([])
        setActiveRun(null)
      })
    }
  }

  async function selectProject(projectId: number) {
    setBusyAction('selecting')
    setLoading(true)
    setError('')

    try {
      const details = await loadProjectDetails(projectId)
      localStorage.setItem(SELECTED_PROJECT_STORAGE_KEY, String(projectId))
      startTransition(() => {
        setProject(details.project)
        setTurns(details.turns)
        setStatus(details.status)
        setTranscript(details.transcript)
        setRuns(details.runs)
        setActiveRun(details.runs.find((run) => run.status === 'running') ?? null)
        setLastMessage('')
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load that project.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function refreshSelected(projectId: number) {
    const details = await loadProjectDetails(projectId)
    startTransition(() => {
      setProject(details.project)
        setTurns(details.turns)
        setStatus(details.status)
        setTranscript(details.transcript)
        setRuns(details.runs)
        setActiveRun(details.runs.find((run) => run.status === 'running') ?? null)
        setProjects((current) =>
        current
          .filter((item) => item.id !== details.project.id)
          .concat(details.project)
          .toSorted((a, b) => {
            if (a.updated_at === b.updated_at) {
              return b.id - a.id
            }
            return parseApiDateMs(b.updated_at) - parseApiDateMs(a.updated_at)
          }),
      )
    })
  }

  async function handleCreateProject(payload: CreateProjectPayload) {
    setBusyAction('creating')
    setLoading(true)
    setError('')

    try {
      const created = await createProject(payload)
      startTransition(() => {
        setLastMessage('Project created. Start the interview to generate the first question.')
      })
      await refreshProjects(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create the project.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleCreateDemoProject() {
    const demoName = `Demo Interview ${new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: 'Asia/Shanghai',
    }).format(new Date())}`
    await handleCreateProject({
      project_name: demoName,
      system_prompt: DEFAULT_SYSTEM_PROMPT,
    })
  }

  async function handleStart() {
    if (!project) {
      return
    }

    setBusyAction('starting')
    setLoading(true)
    setError('')

    try {
      const result = await startProject(project.id)
      startTransition(() => {
        setProject(result.project)
        setLastMessage('Interview started. The first question is ready.')
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start the interview.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleNext(answerText: string, humanReview?: HumanReviewInput | null) {
    if (!project || !answerText.trim()) {
      return
    }

    setBusyAction('submitting')
    setLoading(true)
    setError('')
    setLastMessage('Generating the next question...')

    let settled = false
    let pollActiveRun: Promise<void> | null = null

    try {
      pollActiveRun = (async () => {
        while (!settled) {
          try {
            const latestRun = await getLatestProjectRun(project.id)
            startTransition(() => {
              setActiveRun(latestRun.status === 'running' ? latestRun : null)
              setRuns((current) => {
                const nextRuns = current.filter((run) => run.id !== latestRun.id)
                return [latestRun, ...nextRuns].toSorted((a, b) => b.id - a.id)
              })
            })
          } catch {
            // Ignore until the backend creates or updates the run trace.
          }
          await new Promise((resolve) => window.setTimeout(resolve, 700))
        }

        try {
          const latestRun = await getLatestProjectRun(project.id)
          startTransition(() => {
            setRuns((current) => {
              const nextRuns = current.filter((run) => run.id !== latestRun.id)
              return [latestRun, ...nextRuns].toSorted((a, b) => b.id - a.id)
            })
            setActiveRun(latestRun.status === 'running' ? latestRun : null)
          })
        } catch {
          startTransition(() => {
            setActiveRun(null)
          })
        }
      })()

      const result = await submitNext(project.id, answerText.trim(), humanReview ?? null)
      settled = true
      await pollActiveRun
      startTransition(() => {
        setProject(result.project)
        setLastMessage(result.message)
      })
      await refreshSelected(project.id)
    } catch (err) {
      settled = true
      if (pollActiveRun) {
        await pollActiveRun
      }
      setError(err instanceof Error ? err.message : 'Unable to submit the answer.')
    } finally {
      settled = true
      startTransition(() => {
        setActiveRun(null)
      })
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleUpdateProject(projectId: number, payload: { project_name?: string }) {
    setBusyAction('updating')
    setLoading(true)
    setError('')

    try {
      const updatedProject = await updateProject(projectId, payload)
      startTransition(() => {
        setProject(updatedProject)
        setLastMessage('Project metadata updated.')
      })
      await refreshSelected(projectId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update the project.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleDeleteProject(projectId: number) {
    const deletingSelectedProject = project?.id === projectId

    setBusyAction('deleting')
    setLoading(true)
    setError('')

    try {
      await deleteProject(projectId)

      if (deletingSelectedProject) {
        localStorage.removeItem(SELECTED_PROJECT_STORAGE_KEY)
      }

      const remainingProjects = await listProjects()
      startTransition(() => {
        setProjects(remainingProjects)
        setLastMessage('Project deleted.')
      })

      if (!deletingSelectedProject) {
        return
      }

      const nextProjectId = remainingProjects[0]?.id
      if (nextProjectId) {
        await selectProject(nextProjectId)
        return
      }

      startTransition(() => {
        setProject(null)
        setTurns([])
        setStatus(null)
        setTranscript(null)
        setRuns([])
        setActiveRun(null)
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete the project.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  const initializeProjects = useEffectEvent(() => {
    setBusyAction('initializing')
    void refreshProjects()
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Unable to load projects.')
      })
      .finally(() => {
        setBusyAction(null)
        setLoading(false)
      })
  })

  useEffect(() => {
    setLoading(true)
    initializeProjects()
  }, [])

  return {
    busyAction,
    error,
    lastMessage,
    loading,
    project,
    projects,
    runs,
    status,
    transcript,
    turns,
    activeRun,
    estimateDraftUsage: (answerDraft: string) => ({
      estimatedAnswerInputTokens: estimateTokenCount(answerDraft),
      estimatedNextPromptTokens: estimateNextPromptTokens({
        answerDraft,
        project,
        turns,
      }),
      estimatedNextOutputTokens: estimateNextOutputTokens(answerDraft),
    }),
    createDemoProject: handleCreateDemoProject,
    createProject: handleCreateProject,
    selectProject,
    startProject: handleStart,
    submitNext: handleNext,
    deleteProject: handleDeleteProject,
    updateProject: handleUpdateProject,
  }
}
