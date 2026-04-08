import { ChildProcess, spawn } from 'node:child_process'
import { accessSync, constants, existsSync } from 'node:fs'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import * as vscode from 'vscode'

function existsAndExecutable(path: string) {
  try {
    accessSync(path, constants.X_OK)
    return true
  } catch {
    return false
  }
}

function getPythonCandidates() {
  return ['python3', 'python']
}

function getUvCandidates() {
  return ['uv']
}

async function runCommand(command: string, args: string[], cwd: string, output: vscode.OutputChannel, env?: NodeJS.ProcessEnv) {
  return await new Promise<void>((resolve, reject) => {
    const child = spawn(command, args, { cwd, env: { ...process.env, ...env } })
    child.stdout.on('data', (data) => output.append(data.toString()))
    child.stderr.on('data', (data) => output.append(data.toString()))
    child.on('error', reject)
    child.on('exit', (code) => {
      if (code === 0) resolve()
      else reject(new Error(`${command} ${args.join(' ')} failed with code ${code}`))
    })
  })
}

async function findCommand(candidates: string[], cwd: string, output: vscode.OutputChannel) {
  for (const candidate of candidates) {
    try {
      await runCommand(candidate, ['--version'], cwd, output)
      return candidate
    } catch {
      continue
    }
  }
  return null
}

export class BackendManager implements vscode.Disposable {
  private process: ChildProcess | null = null
  private backendUrl: string | null = null
  private backendStatus: 'stopped' | 'starting' | 'running' | 'error' = 'stopped'
  private readonly output = vscode.window.createOutputChannel('Stateful Interview Backend')

  constructor(private readonly context: vscode.ExtensionContext) {}

  getStatus() {
    return this.backendStatus
  }

  getBackendUrl() {
    return this.backendUrl
  }

  async ensureStarted(opencodeConfigPath?: string) {
    if (this.backendStatus === 'running' && this.backendUrl) {
      return this.backendUrl
    }

    this.backendStatus = 'starting'
    const extensionRoot = this.context.extensionPath
    const bundledBackendRoot = join(extensionRoot, 'bundled', 'backend')
    const storageRoot = this.context.globalStorageUri.fsPath
    mkdirSync(storageRoot, { recursive: true })
    const venvDir = join(storageRoot, 'backend-venv')
    const python = await findCommand(getPythonCandidates(), extensionRoot, this.output)
    if (!python) {
      this.backendStatus = 'error'
      throw new Error('Python 3 is required to run the bundled backend.')
    }

    if (!existsSync(join(venvDir, 'bin', 'python')) && !existsSync(join(venvDir, 'Scripts', 'python.exe'))) {
      await runCommand(python, ['-m', 'venv', venvDir], extensionRoot, this.output)
    }

    const venvPython = existsSync(join(venvDir, 'bin', 'python')) ? join(venvDir, 'bin', 'python') : join(venvDir, 'Scripts', 'python.exe')
    const uv = await findCommand(getUvCandidates(), extensionRoot, this.output)
    if (uv) {
      await runCommand(uv, ['pip', 'install', '-e', '.'], bundledBackendRoot, this.output, { VIRTUAL_ENV: venvDir, PATH: `${join(venvDir, 'bin')}:${process.env.PATH || ''}` })
    } else {
      await runCommand(venvPython, ['-m', 'pip', 'install', '-e', '.'], bundledBackendRoot, this.output)
    }

    const port = await this.findAvailablePort(8000, 8010)
    const cliPath = join(bundledBackendRoot, 'app', 'cli.py')
    if (!existsSync(cliPath)) {
      this.backendStatus = 'error'
      throw new Error(`Bundled backend entrypoint not found: ${cliPath}`)
    }

    const child = spawn(venvPython, [cliPath, '--port', String(port), ...(opencodeConfigPath ? ['--opencode-config', opencodeConfigPath] : [])], {
      cwd: bundledBackendRoot,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    })
    this.process = child
    child.stdout.on('data', (data) => this.output.append(data.toString()))
    child.stderr.on('data', (data) => this.output.append(data.toString()))
    child.on('exit', () => {
      this.backendStatus = 'stopped'
      this.backendUrl = null
      this.process = null
    })

    const url = `http://127.0.0.1:${port}`
    await this.waitForHealth(url)
    this.backendUrl = url
    this.backendStatus = 'running'
    return url
  }

  async restart(opencodeConfigPath?: string) {
    await this.stop()
    return await this.ensureStarted(opencodeConfigPath)
  }

  async stop() {
    if (this.process) {
      this.process.kill()
      this.process = null
    }
    this.backendStatus = 'stopped'
    this.backendUrl = null
  }

  dispose() {
    void this.stop()
    this.output.dispose()
  }

  private async waitForHealth(url: string) {
    const startedAt = Date.now()
    while (Date.now() - startedAt < 30000) {
      try {
        const response = await fetch(`${url}/health`)
        if (response.ok) {
          return
        }
      } catch {
        // keep waiting
      }
      await new Promise((resolve) => setTimeout(resolve, 500))
    }
    this.backendStatus = 'error'
    throw new Error('Bundled backend failed to become healthy in time.')
  }

  private async findAvailablePort(start: number, end: number) {
    for (let port = start; port <= end; port += 1) {
      try {
        const response = await fetch(`http://127.0.0.1:${port}/health`)
        if (!response.ok) {
          return port
        }
      } catch {
        return port
      }
    }
    throw new Error('No available port found for bundled backend.')
  }
}
