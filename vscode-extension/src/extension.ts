import * as vscode from 'vscode'
import { BackendManager } from './backendManager'
import { getConfiguredOpencodePath } from './configManager'
import { InterviewPanelProvider } from './panel'

let backendManager: BackendManager | null = null

export function getRuntimeApiBaseUrl() {
  return backendManager?.getBackendUrl() || ''
}

export function getBackendStatus() {
  return backendManager?.getStatus() || 'stopped'
}

export async function restartBundledBackend() {
  if (!backendManager) {
    return ''
  }
  return await backendManager.restart(getConfiguredOpencodePath())
}

export function activate(context: vscode.ExtensionContext) {
  backendManager = new BackendManager(context)
  const provider = new InterviewPanelProvider(context)

  context.subscriptions.push(backendManager)
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('statefulInterview.sidebarView', provider),
  )

  void backendManager.ensureStarted(getConfiguredOpencodePath()).catch((error) => {
    vscode.window.showErrorMessage(error instanceof Error ? error.message : 'Failed to start bundled backend.')
  })
}

export function deactivate() {
  backendManager?.dispose()
  backendManager = null
}
