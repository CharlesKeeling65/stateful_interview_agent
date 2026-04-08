import * as vscode from 'vscode'

export function getConfiguredOpencodePath() {
  return vscode.workspace
    .getConfiguration('statefulInterview')
    .get<string>('opencodeConfigPath', '')
    .trim()
}

export async function updateConfiguredOpencodePath(path: string) {
  await vscode.workspace
    .getConfiguration('statefulInterview')
    .update('opencodeConfigPath', path, vscode.ConfigurationTarget.Global)
}
