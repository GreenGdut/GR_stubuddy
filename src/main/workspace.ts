import { spawn } from 'child_process'
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'fs'
import { app, BrowserWindow, dialog, globalShortcut, ipcMain, shell } from 'electron'
import { homedir } from 'os'
import { dirname, join } from 'path'

export interface WorkspaceState {
  targetFolder: string | null
  currentProject: string | null
  shortcutAvailable: boolean
}

interface BackendResult {
  ok: boolean
  status?: 'captured' | 'cancelled'
  state?: Omit<WorkspaceState, 'shortcutAvailable'>
  path?: string
  code?: string
  message?: string
}

export interface WorkspaceActionResult {
  status: 'success' | 'cancelled' | 'busy'
  state: WorkspaceState
  message?: string
  path?: string
}

export interface WorkspaceEvent {
  type: 'state' | 'capture' | 'error'
  state: WorkspaceState
  message?: string
  path?: string
}

const SHORTCUT = 'Control+Alt+A'
const SHORTCUT_PROBE = 'Control+Alt+Shift+F11'
const CONFIG_FILE = 'workspace.json'
const DEBUG_LOG_FILE = '/tmp/stubuddy/log'
const AGENT_CONTEXT_FILE = join(homedir(), '.stubuddy', 'agent-context.json')

let mainWindow: BrowserWindow | null = null
let state: WorkspaceState = {
  targetFolder: null,
  currentProject: null,
  shortcutAvailable: false
}
let captureInProgress = false
let handlersRegistered = false

function writeDebugError(context: string, error: unknown, details?: string): void {
  try {
    const message = error instanceof Error ? (error.stack ?? error.message) : String(error)
    const entry = [`[${new Date().toISOString()}] [electron] ${context}`, message, details, '']
      .filter((line) => line !== undefined)
      .join('\n')
    mkdirSync(dirname(DEBUG_LOG_FILE), { recursive: true })
    appendFileSync(DEBUG_LOG_FILE, entry, 'utf8')
  } catch {
    // Temporary diagnostics must never break the user-facing action.
  }
}

function configPath(): string {
  return join(app.getPath('userData'), CONFIG_FILE)
}

function loadConfiguredTarget(): string | null {
  try {
    const config = JSON.parse(readFileSync(configPath(), 'utf8')) as { targetFolder?: unknown }
    return typeof config.targetFolder === 'string' ? config.targetFolder : null
  } catch {
    return null
  }
}

function saveConfiguredTarget(targetFolder: string | null): void {
  const path = configPath()
  const temporaryPath = `${path}.tmp`
  writeFileSync(temporaryPath, JSON.stringify({ targetFolder }, null, 2), 'utf8')
  renameSync(temporaryPath, path)
}

function saveAgentContext(): void {
  try {
    mkdirSync(dirname(AGENT_CONTEXT_FILE), { recursive: true, mode: 0o700 })
    const temporaryPath = `${AGENT_CONTEXT_FILE}.tmp`
    const context = {
      schemaVersion: 1,
      targetFolder: state.targetFolder,
      currentProject: state.currentProject,
      updatedAt: new Date().toISOString()
    }
    writeFileSync(temporaryPath, `${JSON.stringify(context, null, 2)}\n`, {
      encoding: 'utf8',
      mode: 0o600
    })
    renameSync(temporaryPath, AGENT_CONTEXT_FILE)
  } catch (error) {
    writeDebugError('无法更新 Agent 上下文', error, `目标文件: ${AGENT_CONTEXT_FILE}`)
  }
}

function backendCommand(args: string[]): { command: string; args: string[] } {
  if (app.isPackaged) {
    const executable = process.platform === 'win32' ? 'stubuddy-backend.exe' : 'stubuddy-backend'
    return { command: join(process.resourcesPath, 'backend', executable), args }
  }

  const root = app.getAppPath()
  const virtualEnvironmentPython =
    process.platform === 'win32'
      ? join(root, '.venv', 'Scripts', 'python.exe')
      : join(root, '.venv', 'bin', 'python')
  const python = existsSync(virtualEnvironmentPython)
    ? virtualEnvironmentPython
    : process.platform === 'win32'
      ? 'python'
      : 'python3'
  return { command: python, args: ['-m', 'backend.cli', ...args] }
}

function runBackend(args: string[]): Promise<BackendResult> {
  const backend = backendCommand(args)
  return new Promise((resolve, reject) => {
    const child = spawn(backend.command, backend.args, {
      cwd: app.getAppPath(),
      windowsHide: true
    })
    let stdout = ''
    let stderr = ''

    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (chunk: string) => {
      stdout += chunk
    })
    child.stderr.on('data', (chunk: string) => {
      stderr += chunk
    })
    child.on('error', (error) => {
      writeDebugError('无法启动 Python 后端', error, `命令参数: ${args.join(' ')}`)
      reject(error)
    })
    child.on('close', (exitCode) => {
      try {
        const result = JSON.parse(stdout.trim()) as BackendResult
        if (!result.ok) {
          writeDebugError(
            'Python 后端返回错误',
            result.message || result.code || '未知错误',
            `退出码: ${exitCode}\n命令参数: ${args.join(' ')}\nstderr: ${stderr.trim()}`
          )
        }
        resolve(result)
      } catch (error) {
        writeDebugError(
          '无法解析 Python 后端输出',
          error,
          `退出码: ${exitCode}\n命令参数: ${args.join(' ')}\nstdout: ${stdout.trim()}\nstderr: ${stderr.trim()}`
        )
        reject(new Error(stderr.trim() || 'Python 后端没有返回有效结果'))
      }
    })
  })
}

function currentState(): WorkspaceState {
  return { ...state }
}

function applyBackendState(nextState: Omit<WorkspaceState, 'shortcutAvailable'>): void {
  state = { ...nextState, shortcutAvailable: state.shortcutAvailable }
  saveConfiguredTarget(state.targetFolder)
  saveAgentContext()
}

function backendError(result: BackendResult): Error {
  return new Error(result.message || 'Python 后端操作失败')
}

function publish(event: WorkspaceEvent): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('stubuddy:workspace-event', event)
  }
}

async function refreshState(): Promise<WorkspaceState> {
  const targetFolder = loadConfiguredTarget()
  const args = targetFolder ? ['state', '--target', targetFolder] : ['state']
  const result = await runBackend(args)
  if (!result.ok || !result.state) throw backendError(result)
  applyBackendState(result.state)
  return currentState()
}

async function createWorkspace(): Promise<WorkspaceActionResult> {
  if (!mainWindow) throw new Error('应用窗口尚未就绪')
  const selection = await dialog.showOpenDialog(mainWindow, {
    title: '选择 Target_Stubuddy 的存储位置',
    buttonLabel: '在这里创建或恢复工程',
    properties: ['openDirectory', 'createDirectory']
  })
  if (selection.canceled || selection.filePaths.length === 0) {
    return { status: 'cancelled', state: currentState() }
  }

  const result = await runBackend(['create-workspace', '--parent', selection.filePaths[0]])
  if (!result.ok || !result.state) throw backendError(result)
  applyBackendState(result.state)
  publish({ type: 'state', state: currentState(), message: '工程已就绪' })
  return { status: 'success', state: currentState(), message: '工程已就绪' }
}

async function createProject(): Promise<WorkspaceActionResult> {
  if (!state.targetFolder) return createWorkspace()
  const result = await runBackend(['create-project', '--target', state.targetFolder])
  if (!result.ok || !result.state) throw backendError(result)
  applyBackendState(result.state)
  publish({ type: 'state', state: currentState(), message: '新工程已创建' })
  return { status: 'success', state: currentState(), message: '新工程已创建' }
}

async function capture(): Promise<WorkspaceActionResult> {
  if (captureInProgress) {
    return { status: 'busy', state: currentState(), message: '截图工具正在运行' }
  }
  if (!state.currentProject) {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
    publish({ type: 'error', state: currentState(), message: '请先创建工程' })
    return { status: 'cancelled', state: currentState(), message: '请先创建工程' }
  }

  captureInProgress = true
  const windowWasVisible = mainWindow?.isVisible() ?? false
  try {
    mainWindow?.hide()
    await new Promise((resolve) => setTimeout(resolve, 180))
    const result = await runBackend(['capture', '--project', state.currentProject])
    if (!result.ok) throw backendError(result)
    if (result.status === 'cancelled') {
      return { status: 'cancelled', state: currentState(), message: '已取消截图' }
    }
    const response: WorkspaceActionResult = {
      status: 'success',
      state: currentState(),
      message: '截图已保存',
      path: result.path
    }
    publish({ type: 'capture', ...response })
    return response
  } finally {
    captureInProgress = false
    if (mainWindow && !mainWindow.isDestroyed() && windowWasVisible) {
      mainWindow.show()
      mainWindow.focus()
    }
  }
}

async function openCurrentProject(): Promise<WorkspaceActionResult> {
  if (!state.currentProject) {
    return { status: 'cancelled', state: currentState(), message: '请先创建工程' }
  }
  const error = await shell.openPath(state.currentProject)
  if (error) throw new Error(error)
  return { status: 'success', state: currentState() }
}

function wrapAction(
  action: () => Promise<WorkspaceActionResult>
): () => Promise<WorkspaceActionResult> {
  return async () => {
    try {
      return await action()
    } catch (error) {
      const message = error instanceof Error ? error.message : '操作失败'
      writeDebugError('工作区操作失败', error)
      publish({ type: 'error', state: currentState(), message })
      return { status: 'cancelled', state: currentState(), message }
    }
  }
}

export async function initializeWorkspace(window: BrowserWindow): Promise<void> {
  mainWindow = window
  saveAgentContext()
  if (!handlersRegistered) {
    ipcMain.handle('stubuddy:get-workspace-state', refreshState)
    ipcMain.handle('stubuddy:create-workspace', wrapAction(createWorkspace))
    ipcMain.handle('stubuddy:create-project', wrapAction(createProject))
    ipcMain.handle('stubuddy:capture', wrapAction(capture))
    ipcMain.handle('stubuddy:open-current-project', wrapAction(openCurrentProject))
    handlersRegistered = true
  }

  try {
    await refreshState()
  } catch (error) {
    const message = error instanceof Error ? error.message : '无法读取工程状态'
    writeDebugError('初始化工作区失败', error)
    publish({ type: 'error', state: currentState(), message })
  }

  state.shortcutAvailable = globalShortcut.register(SHORTCUT, () => {
    void wrapAction(capture)()
  })
  if (!state.shortcutAvailable) {
    const probeAvailable = globalShortcut.register(SHORTCUT_PROBE, () => undefined)
    if (probeAvailable) globalShortcut.unregister(SHORTCUT_PROBE)
    writeDebugError(
      '全局快捷键注册失败',
      `快捷键 ${SHORTCUT} 可能已被占用或后端拒绝`,
      `诊断快捷键 ${SHORTCUT_PROBE}: ${probeAvailable ? '注册成功' : '注册失败'}\n` +
        `会话类型: ${process.env.XDG_SESSION_TYPE || '未知'}\n` +
        `Wayland: ${process.env.WAYLAND_DISPLAY || '无'}\n` +
        `X11: ${process.env.DISPLAY || '无'}`
    )
  }
  publish({
    type: 'state',
    state: currentState(),
    message: state.shortcutAvailable ? undefined : '快捷键 Ctrl+Alt+A 注册失败，请点击卡片截图'
  })
}

export function setWorkspaceWindow(window: BrowserWindow): void {
  mainWindow = window
  publish({ type: 'state', state: currentState() })
}

export function disposeWorkspace(): void {
  globalShortcut.unregister(SHORTCUT)
}
