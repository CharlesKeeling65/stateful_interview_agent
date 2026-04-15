import { startTransition, useEffect, useEffectEvent, useState } from 'react'

import {
  autoAnswerLatest,
  autoStep,
  createProject,
  deleteTurnTail,
  deleteProject,
  ensureOpenCodeSession,
  getProject,
  getLatestProjectRun,
  getProjectRuns,
  getProjectStatus,
  getProjectTranscript,
  getProjectTurns,
  listProjects,
  regenerateCurrentQuestion,
  saveCurrentQuestion,
  runOpenCodePlanStep,
  submitAnswer,
  startProject,
  submitNext,
  updateProject,
} from '../api/client'
import type {
  CreateProjectPayload,
  CurrentQuestionRegenerateResponse,
  HumanReviewInput,
  NextQuestionRequestPayload,
  ProjectRead,
  ProjectStatusResponse,
  RunRead,
  TranscriptResponse,
  TurnRead,
  UpdateProjectPayload,
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
  | 'saving_answer'
  | 'sending_opencode'
  | 'generating_next'
  | 'regenerating'
  | 'saving_question'
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
  const [opencodeStartedAt, setOpencodeStartedAt] = useState<number | null>(null)
  const [opencodeElapsedSeconds, setOpencodeElapsedSeconds] = useState(0)
  const [error, setError] = useState('')
  const [lastMessageKey, setLastMessageKey] = useState('')
  const [lastRegenerationFeedback, setLastRegenerationFeedback] =
    useState<CurrentQuestionRegenerateResponse | null>(null)

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
        setLastMessageKey('')
        setLastRegenerationFeedback(null)
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
        setLastMessageKey('status.created')
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
      agent_mode: 'understand_current_code',
      answer_provider_type: 'opencode',
      answer_automation_enabled: true,
    })
  }

  async function handleStart() {
    if (!project) {
      return
    }

    setBusyAction('starting')
    setLoading(true)
    setError('')
    setLastRegenerationFeedback(null)

    try {
      const result = await startProject(project.id)
      startTransition(() => {
        setProject(result.project)
        setLastMessageKey('status.started')
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start the interview.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleSaveAnswer(answerText: string) {
    if (!project || !answerText.trim()) {
      return
    }

    setBusyAction('saving_answer')
    setLoading(true)
    setError('')
    setLastMessageKey('status.savingAnswer')
    setLastRegenerationFeedback(null)

    try {
      await submitAnswer(project.id, answerText.trim())
      startTransition(() => {
        setLastMessageKey('status.answerSaved')
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save the answer.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleAutoAnswerLatest() {
    if (!project) {
      return
    }

    setBusyAction('saving_answer')
    setLoading(true)
    setError('')
    setLastMessageKey('status.savingAnswer')
    setLastRegenerationFeedback(null)

    try {
      await autoAnswerLatest(project.id)
      startTransition(() => {
        setLastMessageKey('status.answerSaved')
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to auto-answer the latest question.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleEnsureOpenCodeSession() {
    if (!project) {
      return null
    }

    setBusyAction('sending_opencode')
    setOpencodeStartedAt(Date.now())
    setOpencodeElapsedSeconds(0)
    setLoading(true)
    setError('')

    try {
      const result = await ensureOpenCodeSession(project.id)
      startTransition(() => {
        setLastMessageKey(result.created ? 'status.opencodeSessionCreated' : 'status.opencodeSessionReady')
      })
      await refreshSelected(project.id)
      return result
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to prepare the OpenCode session.')
      return null
    } finally {
      setBusyAction(null)
      setOpencodeStartedAt(null)
      setOpencodeElapsedSeconds(0)
      setLoading(false)
    }
  }

  async function handleRunOpenCodePlanStep(
    humanReview?: HumanReviewInput | null,
    questionText?: string | null,
  ) {
    if (!project) {
      return
    }

    setBusyAction('sending_opencode')
    setOpencodeStartedAt(Date.now())
    setOpencodeElapsedSeconds(0)
    setLoading(true)
    setError('')
    setLastMessageKey('status.opencodeSending')
    setLastRegenerationFeedback(null)

    try {
      const result = await runOpenCodePlanStep(project.id, {
        human_review: humanReview ?? null,
        question_text: questionText?.trim() || null,
      })
      startTransition(() => {
        setProject(result.project)
        setLastMessageKey(result.interview_finished ? 'status.finished' : 'status.opencodeAnswered')
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send the question to OpenCode.')
    } finally {
      setBusyAction(null)
      setOpencodeStartedAt(null)
      setOpencodeElapsedSeconds(0)
      setLoading(false)
    }
  }

  useEffect(() => {
    if (busyAction !== 'sending_opencode' || opencodeStartedAt == null) {
      return
    }

    const updateElapsed = () => {
      setOpencodeElapsedSeconds(Math.max(0, Math.floor((Date.now() - opencodeStartedAt) / 1000)))
    }

    updateElapsed()
    const intervalId = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(intervalId)
  }, [busyAction, opencodeStartedAt])

  async function handleGenerateNext(payload?: NextQuestionRequestPayload) {
    if (!project) {
      return
    }

    setBusyAction('generating_next')
    setLoading(true)
    setError('')
    setLastMessageKey('status.generating')
    setLastRegenerationFeedback(null)

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

      const result = await submitNext(project.id, {
        human_review: payload?.human_review ?? null,
        human_gate: payload?.human_gate ?? null,
      })
      settled = true
      await pollActiveRun
      startTransition(() => {
        setProject(result.project)
        setLastMessageKey(result.interview_finished ? 'status.finished' : 'status.generated')
      })
      await refreshSelected(project.id)
    } catch (err) {
      settled = true
      if (pollActiveRun) {
        await pollActiveRun
      }
      setError(err instanceof Error ? err.message : 'Unable to generate the next question.')
    } finally {
      settled = true
      startTransition(() => {
        setActiveRun(null)
      })
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleAutoStep(payload?: NextQuestionRequestPayload) {
    if (!project) {
      return
    }

    setBusyAction('generating_next')
    setLoading(true)
    setError('')
    setLastMessageKey('status.generating')
    setLastRegenerationFeedback(null)

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

      const result = await autoStep(project.id, {
        human_review: payload?.human_review ?? null,
        human_gate: payload?.human_gate ?? null,
      })
      settled = true
      await pollActiveRun
      startTransition(() => {
        setProject(result.project)
        setLastMessageKey(result.interview_finished ? 'status.finished' : 'status.generated')
      })
      await refreshSelected(project.id)
    } catch (err) {
      settled = true
      if (pollActiveRun) {
        await pollActiveRun
      }
      setError(err instanceof Error ? err.message : 'Unable to auto-run the next step.')
    } finally {
      settled = true
      startTransition(() => {
        setActiveRun(null)
      })
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleRegenerateCurrentQuestion(turnId: number, humanReview?: HumanReviewInput | null) {
    if (!project) {
      return
    }

    setBusyAction('regenerating')
    setLoading(true)
    setError('')
    setLastMessageKey('status.regeneratingCurrent')
    setLastRegenerationFeedback(null)

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

      const result = await regenerateCurrentQuestion(project.id, turnId, humanReview ?? null)
      settled = true
      await pollActiveRun
      startTransition(() => {
        setLastMessageKey('status.regeneratedCurrent')
        setLastRegenerationFeedback(result)
      })
      await refreshSelected(project.id)
    } catch (err) {
      settled = true
      if (pollActiveRun) {
        await pollActiveRun
      }
      setError(err instanceof Error ? err.message : 'Unable to regenerate the current question.')
    } finally {
      settled = true
      startTransition(() => {
        setActiveRun(null)
      })
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleSaveCurrentQuestion(turnId: number, questionText: string) {
    if (!project || !questionText.trim()) {
      return
    }

    setBusyAction('saving_question')
    setLoading(true)
    setError('')
    setLastMessageKey('status.savingQuestion')
    setLastRegenerationFeedback(null)

    try {
      await saveCurrentQuestion(project.id, turnId, questionText.trim())
      startTransition(() => {
        setLastMessageKey('status.currentQuestionSaved')
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save the current question.')
    } finally {
      setBusyAction(null)
      setLoading(false)
    }
  }

  async function handleUpdateProject(projectId: number, payload: UpdateProjectPayload) {
    setBusyAction('updating')
    setLoading(true)
    setError('')

    try {
      const updatedProject = await updateProject(projectId, payload)
      startTransition(() => {
        setProject(updatedProject)
        setLastMessageKey('status.updated')
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
        setLastMessageKey('status.deleted')
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

  async function handleDeleteTurnTail(turnId: number) {
    if (!project) {
      return
    }

    setBusyAction('deleting')
    setLoading(true)
    setError('')

    try {
      const result = await deleteTurnTail(project.id, turnId)
      startTransition(() => {
        setLastMessageKey(result.remaining_turn_count > 0 ? 'status.turnTailDeleted' : 'status.turnTailDeletedToStart')
        setLastRegenerationFeedback(null)
      })
      await refreshSelected(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete this turn and later history.')
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
    lastMessageKey,
    lastRegenerationFeedback,
    loading,
    project,
    projects,
    runs,
    status,
    transcript,
    turns,
    activeRun,
    opencodeElapsedSeconds,
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
    saveAnswer: handleSaveAnswer,
    ensureOpenCodeSession: handleEnsureOpenCodeSession,
    runOpenCodePlanStep: handleRunOpenCodePlanStep,
    autoAnswerLatest: handleAutoAnswerLatest,
    submitNext: handleGenerateNext,
    autoStep: handleAutoStep,
    regenerateCurrentQuestion: handleRegenerateCurrentQuestion,
    saveCurrentQuestion: handleSaveCurrentQuestion,
    deleteTurnTail: handleDeleteTurnTail,
    deleteProject: handleDeleteProject,
    updateProject: handleUpdateProject,
  }
}
