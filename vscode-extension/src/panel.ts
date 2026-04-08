import * as vscode from 'vscode'
import {
  autoAnswerLatest,
  autoStep,
  createProject,
  generateNext,
  getConfigSnapshot,
  getLatestProjectRun,
  getProjectStatus,
  getProjectTurns,
  listProjects,
  regenerateCurrentQuestion,
  saveAnswer,
  startProject,
  updateEnvEntries,
  updateOpencodeMindflow,
} from './api'
import { getBackendStatus, restartBundledBackend } from './extension'
import { getConfiguredOpencodePath, updateConfiguredOpencodePath } from './configManager'

export class InterviewPanelProvider implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined
  private currentProjectId: number | null = null

  constructor(private readonly context: vscode.ExtensionContext) {}

  resolveWebviewView(webviewView: vscode.WebviewView) {
    this.view = webviewView
    webviewView.webview.options = { enableScripts: true }
    webviewView.webview.html = this.renderHtml()
    webviewView.webview.onDidReceiveMessage((message) => {
      void this.handleMessage(message)
    })
    void this.pushState()
  }

  private async handleMessage(message: any) {
    try {
      switch (message.type) {
        case 'refresh':
          await this.pushState()
          break
        case 'selectProject':
          this.currentProjectId = Number(message.projectId) || null
          await this.pushState()
          break
        case 'createProject': {
          const created = await createProject({
            project_name: message.projectName,
            system_prompt: message.systemPrompt,
            answer_provider_type: message.answerProviderType || 'manual',
            answer_automation_enabled: Boolean(message.answerAutomationEnabled),
          })
          this.currentProjectId = created.id
          await this.pushState('Project created.')
          break
        }
        case 'startProject':
          this.ensureProjectSelected()
          await startProject(this.currentProjectId!)
          await this.pushState('Interview started.')
          break
        case 'saveAnswer':
          this.ensureProjectSelected()
          await saveAnswer(this.currentProjectId!, String(message.answerText || ''))
          await this.pushState('Answer saved.')
          break
        case 'generateNext':
          this.ensureProjectSelected()
          await generateNext(this.currentProjectId!, {
            human_review: this.buildHumanReview(message),
          })
          await this.pushState('Next question generated.')
          break
        case 'autoAnswerLatest':
          this.ensureProjectSelected()
          await autoAnswerLatest(this.currentProjectId!)
          await this.pushState('Latest question auto-answered.')
          break
        case 'autoStep':
          this.ensureProjectSelected()
          await autoStep(this.currentProjectId!, {
            human_review: this.buildHumanReview(message),
          })
          await this.pushState('Auto-step completed.')
          break
        case 'regenerateCurrent': {
          this.ensureProjectSelected()
          const turns = await getProjectTurns(this.currentProjectId!)
          const latestTurn = turns.length ? turns[turns.length - 1] : null
          if (!latestTurn) {
            throw new Error('No turn available to regenerate.')
          }
          await regenerateCurrentQuestion(this.currentProjectId!, latestTurn.id, this.buildHumanReview(message))
          await this.pushState('Current question regenerated.')
          break
        }
        case 'saveConfig':
          await updateConfiguredOpencodePath(String(message.opencodeConfigPath || '').trim())
          await updateOpencodeMindflow({
            base_url: String(message.mindflowBaseUrl || '').trim() || null,
            api_key: String(message.mindflowApiKey || '').trim() || null,
          })
          await updateEnvEntries(Array.isArray(message.envEntries) ? message.envEntries : [])
          await restartBundledBackend()
          await this.pushState('Configuration updated and backend restarted.')
          break
        case 'restartBackend':
          await restartBundledBackend()
          await this.pushState('Bundled backend restarted.')
          break
        default:
          break
      }
    } catch (error) {
      await this.pushState(undefined, error instanceof Error ? error.message : 'Unknown error')
    }
  }

  private buildHumanReview(message: any) {
    const verdict = message.reviewVerdict || null
    const direction = message.reviewDirection || 'continue'
    const preferredNextFocus = String(message.preferredNextFocus || '').trim() || null
    const note = String(message.reviewNote || '').trim() || null
    if (!verdict && !preferredNextFocus && !note && direction === 'continue') {
      return null
    }
    return {
      verdict,
      direction,
      preferred_next_focus: preferredNextFocus,
      note,
    }
  }

  private ensureProjectSelected() {
    if (!this.currentProjectId) {
      throw new Error('Select a project first.')
    }
  }

  private async pushState(statusMessage?: string, errorMessage?: string) {
    if (!this.view) {
      return
    }

    const projects = await listProjects().catch(() => [])
    if (!this.currentProjectId && projects.length > 0) {
      this.currentProjectId = projects[0].id
    }
    if (this.currentProjectId && !projects.some((project) => project.id === this.currentProjectId)) {
      this.currentProjectId = projects[0]?.id ?? null
    }

    let status: any = null
    let turns: any[] = []
    let latestRun: any = null
    if (this.currentProjectId) {
      ;[status, turns] = await Promise.all([
        getProjectStatus(this.currentProjectId).catch(() => null),
        getProjectTurns(this.currentProjectId).catch(() => []),
      ])
      latestRun = await getLatestProjectRun(this.currentProjectId).catch(() => null)
    }
    const config = await getConfigSnapshot().catch(() => null)

    this.view.webview.postMessage({
      type: 'state',
      payload: {
        projects,
        currentProjectId: this.currentProjectId,
        status,
        turns,
        latestRun,
        config,
        backendStatus: getBackendStatus(),
        configuredOpencodePath: getConfiguredOpencodePath(),
        statusMessage: statusMessage ?? '',
        errorMessage: errorMessage ?? '',
      },
    })
  }

  private renderHtml() {
    const nonce = String(Date.now())
    return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Stateful Interview Agent</title>
    <style>
      body { font-family: var(--vscode-font-family); padding: 10px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
      .section { margin-bottom: 12px; padding: 10px; border: 1px solid var(--vscode-panel-border); border-radius: 8px; }
      button { width: 100%; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: 0; padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-top: 8px; }
      input, textarea, select { width: 100%; margin-top: 8px; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); padding: 8px; border-radius: 6px; box-sizing: border-box; }
      pre { white-space: pre-wrap; word-break: break-word; background: rgba(127,127,127,.08); padding: 8px; border-radius: 6px; }
      .muted { opacity: .8; font-size: 12px; }
      .error { color: var(--vscode-errorForeground); }
      .turn { border-top: 1px solid var(--vscode-panel-border); padding-top: 8px; margin-top: 8px; }
      table { width: 100%; border-collapse: collapse; margin-top: 8px; }
      td, th { border-top: 1px solid var(--vscode-panel-border); padding: 6px; text-align: left; vertical-align: top; }
      .tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 12px; }
      .tab-active { outline: 1px solid var(--vscode-focusBorder); }
      .inline-status { margin-top: 6px; }
    </style>
  </head>
  <body>
    <div class="tabs">
      <button id="workflowTabBtn" class="tab-active">Workflow</button>
      <button id="configTabBtn">Config</button>
    </div>

    <div id="workflowTab">
      <div class="section">
        <h3>Project</h3>
        <select id="projectSelect"></select>
        <input id="projectName" placeholder="New project name" />
        <select id="answerProviderType">
          <option value="manual">manual</option>
          <option value="opencode">opencode</option>
        </select>
        <label class="muted"><input id="answerAutomationEnabled" type="checkbox" /> enable OpenCode automation</label>
        <textarea id="systemPrompt" rows="4" placeholder="System prompt"></textarea>
        <button id="refreshBtn">Refresh</button>
        <button id="createBtn">Create Project</button>
      </div>

      <div class="section">
        <h3>Status</h3>
        <div id="backendStatus" class="muted">Backend: unknown</div>
        <div id="statusSummary" class="muted">No project selected.</div>
        <button id="startBtn">Start Interview</button>
        <button id="autoAnswerBtn">Auto-answer Latest</button>
        <button id="autoStepBtn">Auto-step</button>
        <div id="messageBox" class="muted inline-status"></div>
        <div id="errorBox" class="error inline-status"></div>
      </div>

      <div class="section">
        <h3>Current Question</h3>
        <pre id="currentQuestion">No question yet.</pre>
      </div>

      <div class="section">
        <h3>Answer</h3>
        <textarea id="answerText" rows="8" placeholder="Answer text"></textarea>
        <button id="saveAnswerBtn">Save Answer</button>
        <button id="generateNextBtn">Generate Next</button>
      </div>

      <div class="section">
        <h3>Human Review</h3>
        <select id="reviewVerdict">
          <option value="">No verdict</option>
          <option value="sufficient">Sufficient</option>
          <option value="insufficient">Insufficient</option>
          <option value="drifted">Drifted</option>
        </select>
        <select id="reviewDirection">
          <option value="continue">Continue</option>
          <option value="redirect">Redirect</option>
        </select>
        <input id="preferredNextFocus" placeholder="Preferred next focus" />
        <textarea id="reviewNote" rows="4" placeholder="Human note"></textarea>
        <button id="regenerateBtn">Regenerate Current Question</button>
      </div>

      <div class="section">
        <h3>Run Trace</h3>
        <pre id="runTrace">No run data.</pre>
      </div>

      <div class="section">
        <h3>Recent Transcript</h3>
        <div id="turns"></div>
      </div>
    </div>

    <div id="configTab" style="display:none">
      <div class="section">
        <h3>Runtime</h3>
        <div id="configPaths" class="muted">No config loaded.</div>
        <input id="opencodeConfigPath" placeholder="Custom opencode.json path" />
        <button id="restartBackendBtn">Restart Backend</button>
      </div>
      <div class="section">
        <h3>OpenCode Mindflow → Anthropic</h3>
        <input id="mindflowBaseUrl" placeholder="Mindflow base URL" />
        <input id="mindflowApiKey" type="password" placeholder="Mindflow api key" />
        <div id="effectiveAnthropic" class="muted"></div>
        <button id="saveConfigBtn">Save Config</button>
      </div>
      <div class="section">
        <h3>.env Editor</h3>
        <table>
          <thead><tr><th>Key</th><th>Value</th></tr></thead>
          <tbody id="envTableBody"></tbody>
        </table>
      </div>
    </div>

    <script nonce="${nonce}">
      const vscode = acquireVsCodeApi()
      const els = {
        workflowTab: document.getElementById('workflowTab'),
        configTab: document.getElementById('configTab'),
        workflowTabBtn: document.getElementById('workflowTabBtn'),
        configTabBtn: document.getElementById('configTabBtn'),
        projectSelect: document.getElementById('projectSelect'),
        projectName: document.getElementById('projectName'),
        answerProviderType: document.getElementById('answerProviderType'),
        answerAutomationEnabled: document.getElementById('answerAutomationEnabled'),
        systemPrompt: document.getElementById('systemPrompt'),
        backendStatus: document.getElementById('backendStatus'),
        statusSummary: document.getElementById('statusSummary'),
        messageBox: document.getElementById('messageBox'),
        errorBox: document.getElementById('errorBox'),
        currentQuestion: document.getElementById('currentQuestion'),
        answerText: document.getElementById('answerText'),
        runTrace: document.getElementById('runTrace'),
        turns: document.getElementById('turns'),
        reviewVerdict: document.getElementById('reviewVerdict'),
        reviewDirection: document.getElementById('reviewDirection'),
        preferredNextFocus: document.getElementById('preferredNextFocus'),
        reviewNote: document.getElementById('reviewNote'),
        configPaths: document.getElementById('configPaths'),
        opencodeConfigPath: document.getElementById('opencodeConfigPath'),
        mindflowBaseUrl: document.getElementById('mindflowBaseUrl'),
        mindflowApiKey: document.getElementById('mindflowApiKey'),
        effectiveAnthropic: document.getElementById('effectiveAnthropic'),
        envTableBody: document.getElementById('envTableBody'),
      }

      function setTab(tab) {
        const showWorkflow = tab === 'workflow'
        els.workflowTab.style.display = showWorkflow ? '' : 'none'
        els.configTab.style.display = showWorkflow ? 'none' : ''
        els.workflowTabBtn.className = showWorkflow ? 'tab-active' : ''
        els.configTabBtn.className = showWorkflow ? '' : 'tab-active'
      }
      els.workflowTabBtn.onclick = () => setTab('workflow')
      els.configTabBtn.onclick = () => setTab('config')

      const reviewPayload = () => ({
        reviewVerdict: els.reviewVerdict.value,
        reviewDirection: els.reviewDirection.value,
        preferredNextFocus: els.preferredNextFocus.value,
        reviewNote: els.reviewNote.value,
      })

      function collectEnvEntries() {
        return Array.from(document.querySelectorAll('[data-env-key]')).map((row) => ({
          key: row.getAttribute('data-env-key'),
          value: row.querySelector('input').value,
        }))
      }

      document.getElementById('refreshBtn').onclick = () => vscode.postMessage({ type: 'refresh' })
      document.getElementById('createBtn').onclick = () => vscode.postMessage({
        type: 'createProject',
        projectName: els.projectName.value || 'VSCode Interview Project',
        systemPrompt: els.systemPrompt.value || 'You are a stateful interview agent. Generate exactly one next English question each time.',
        answerProviderType: els.answerProviderType.value,
        answerAutomationEnabled: els.answerAutomationEnabled.checked,
      })
      document.getElementById('startBtn').onclick = () => vscode.postMessage({ type: 'startProject' })
      document.getElementById('saveAnswerBtn').onclick = () => vscode.postMessage({ type: 'saveAnswer', answerText: els.answerText.value })
      document.getElementById('generateNextBtn').onclick = () => vscode.postMessage({ type: 'generateNext', ...reviewPayload() })
      document.getElementById('autoAnswerBtn').onclick = () => vscode.postMessage({ type: 'autoAnswerLatest' })
      document.getElementById('autoStepBtn').onclick = () => vscode.postMessage({ type: 'autoStep', ...reviewPayload() })
      document.getElementById('regenerateBtn').onclick = () => vscode.postMessage({ type: 'regenerateCurrent', ...reviewPayload() })
      document.getElementById('saveConfigBtn').onclick = () => vscode.postMessage({
        type: 'saveConfig',
        opencodeConfigPath: els.opencodeConfigPath.value,
        mindflowBaseUrl: els.mindflowBaseUrl.value,
        mindflowApiKey: els.mindflowApiKey.value,
        envEntries: collectEnvEntries(),
      })
      document.getElementById('restartBackendBtn').onclick = () => vscode.postMessage({ type: 'restartBackend' })
      els.projectSelect.onchange = () => vscode.postMessage({ type: 'selectProject', projectId: Number(els.projectSelect.value) })

      window.addEventListener('message', (event) => {
        const { type, payload } = event.data || {}
        if (type !== 'state') return

        const projects = payload.projects || []
        els.projectSelect.innerHTML = projects.map((project) =>
          '<option value="' + project.id + '" ' + (project.id === payload.currentProjectId ? 'selected' : '') + '>' + project.project_name + ' (#' + project.id + ')</option>'
        ).join('')

        const turns = payload.turns || []
        const latestTurn = turns.length ? turns[turns.length - 1] : null
        els.backendStatus.textContent = 'Backend: ' + (payload.backendStatus || 'unknown')
        els.currentQuestion.textContent = latestTurn?.question_text || 'No question yet.'
        els.answerText.value = latestTurn?.answer_text || ''
        els.statusSummary.textContent = payload.status
          ? 'Stage: ' + payload.status.current_stage + ' | Turns: ' + payload.status.turn_count + ' | Provider: ' + (payload.status.answer_provider_type || 'manual')
          : 'No project selected.'
        els.messageBox.textContent = payload.statusMessage || ''
        els.errorBox.textContent = payload.errorMessage || ''
        els.runTrace.textContent = payload.latestRun
          ? JSON.stringify({ status: payload.latestRun.status, current_step: payload.latestRun.current_step_label, steps: payload.latestRun.steps?.map((step) => ({ label: step.label, status: step.status })) }, null, 2)
          : 'No run data.'
        els.turns.innerHTML = turns.slice(-5).map((turn) => '<div class="turn"><strong>Q' + turn.turn_no + '</strong><pre>' + escapeHtml(turn.question_text || '') + '</pre><div class="muted">Answer</div><pre>' + escapeHtml(turn.answer_text || '') + '</pre></div>').join('') || '<div class="muted">No turns yet.</div>'

        const config = payload.config
        els.opencodeConfigPath.value = payload.configuredOpencodePath || ''
        if (config) {
          els.configPaths.textContent = 'OpenCode: ' + config.paths.opencode_config + ' | .env: ' + config.paths.env_file
          els.mindflowBaseUrl.value = config.opencode_mindflow.base_url || ''
          els.mindflowApiKey.placeholder = config.opencode_mindflow.api_key_masked || 'No api key configured'
          els.mindflowApiKey.value = ''
          els.effectiveAnthropic.textContent = 'Effective Anthropic source: ' + (config.effective_anthropic.source || 'unknown') + ' | base URL: ' + (config.effective_anthropic.base_url || '') + ' | API key: ' + (config.effective_anthropic.api_key_masked || '')
          els.envTableBody.innerHTML = (config.env_entries || []).map((entry) =>
            '<tr data-env-key="' + escapeHtml(entry.key) + '"><td>' + escapeHtml(entry.key) + '</td><td><input ' + (entry.is_secret ? 'type="password" ' : '') + 'value="' + escapeAttr(entry.value || '') + '" placeholder="' + escapeAttr(entry.is_secret ? (entry.has_value ? 'Stored: ' + entry.value : 'No value') : '') + '" /></td></tr>'
          ).join('')
        }
      })

      function escapeHtml(value) {
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      }
      function escapeAttr(value) {
        return escapeHtml(value).replaceAll('"', '&quot;')
      }

      setTab('workflow')
      vscode.postMessage({ type: 'refresh' })
    </script>
  </body>
</html>`
  }
}
