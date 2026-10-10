import { ElectronAPI } from '@electron-toolkit/preload'

declare global {
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

  interface StubuddyAPI {
    getWorkspaceState: () => Promise<WorkspaceState>
    createWorkspace: () => Promise<WorkspaceActionResult>
    createProject: () => Promise<WorkspaceActionResult>
    capture: () => Promise<WorkspaceActionResult>
    openCurrentProject: () => Promise<WorkspaceActionResult>
    onWorkspaceEvent: (callback: (event: WorkspaceEvent) => void) => () => void
  }

  interface Window {
    electron: ElectronAPI
    api: StubuddyAPI
  }
}
