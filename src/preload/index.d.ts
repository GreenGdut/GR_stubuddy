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

  interface ReviewFileWriteResult {
    path: string
  }

  interface StubuddyAPI {
    getWorkspaceState: () => Promise<WorkspaceState>
    createWorkspace: () => Promise<WorkspaceActionResult>
    createProject: () => Promise<WorkspaceActionResult>
    capture: () => Promise<WorkspaceActionResult>
    openCurrentProject: () => Promise<WorkspaceActionResult>
    openReviewDesk: () => Promise<WorkspaceActionResult>
    getReviewFiles: () => Promise<ReviewProject>
    readReviewFile: (path: string) => Promise<ReviewFileContent>
    writeReviewImage: (path: string, dataUrl: string) => Promise<ReviewFileWriteResult>
    renameReviewFile: (path: string, nextName: string) => Promise<ReviewFileWriteResult>
    onWorkspaceEvent: (callback: (event: WorkspaceEvent) => void) => () => void
  }

  interface Window {
    electron: ElectronAPI
    api: StubuddyAPI
  }
}
