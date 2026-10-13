import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

interface WorkspaceState {
  targetFolder: string | null
  currentProject: string | null
  shortcutAvailable: boolean
}

interface WorkspaceActionResult {
  status: 'success' | 'cancelled' | 'busy'
  state: WorkspaceState
  message?: string
  path?: string
}

interface WorkspaceEvent {
  type: 'state' | 'capture' | 'error'
  state: WorkspaceState
  message?: string
  path?: string
}

interface ReviewFile {
  path: string
  name: string
  kind: 'image' | 'text' | 'unsupported'
  size: number
}

interface ReviewProject {
  name: string
  path: string
  files: ReviewFile[]
}

type ReviewFileContent =
  | { kind: 'image'; dataUrl: string }
  | {
      kind: 'text'
      content: string
      truncated: boolean
    }

const api = {
  getWorkspaceState: (): Promise<WorkspaceState> =>
    ipcRenderer.invoke('stubuddy:get-workspace-state'),
  createWorkspace: (): Promise<WorkspaceActionResult> =>
    ipcRenderer.invoke('stubuddy:create-workspace'),
  createProject: (): Promise<WorkspaceActionResult> =>
    ipcRenderer.invoke('stubuddy:create-project'),
  capture: (): Promise<WorkspaceActionResult> => ipcRenderer.invoke('stubuddy:capture'),
  openCurrentProject: (): Promise<WorkspaceActionResult> =>
    ipcRenderer.invoke('stubuddy:open-current-project'),
  openReviewDesk: (): Promise<WorkspaceActionResult> =>
    ipcRenderer.invoke('stubuddy:open-review-desk'),
  getReviewFiles: (): Promise<ReviewProject> => ipcRenderer.invoke('stubuddy:get-review-files'),
  readReviewFile: (path: string): Promise<ReviewFileContent> =>
    ipcRenderer.invoke('stubuddy:read-review-file', path),
  onWorkspaceEvent: (callback: (event: WorkspaceEvent) => void): (() => void) => {
    const listener = (_event: Electron.IpcRendererEvent, event: WorkspaceEvent): void =>
      callback(event)
    ipcRenderer.on('stubuddy:workspace-event', listener)
    return () => ipcRenderer.removeListener('stubuddy:workspace-event', listener)
  }
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
