import * as vscode from 'vscode'
import { InterviewPanelProvider } from './panel'

export function activate(context: vscode.ExtensionContext) {
  const provider = new InterviewPanelProvider(context)
  context.subscriptions.push(
    vscode.commands.registerCommand('statefulInterview.openPanel', () => {
      provider.show()
    }),
  )
}

export function deactivate() {}
