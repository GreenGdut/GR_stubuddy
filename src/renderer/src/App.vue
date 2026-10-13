<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

type AppWorkspaceState = Awaited<ReturnType<Window['api']['getWorkspaceState']>>
type AppWorkspaceActionResult = Awaited<ReturnType<Window['api']['capture']>>

const workspace = ref<AppWorkspaceState>({
  targetFolder: null,
  currentProject: null,
  shortcutAvailable: false
})
const busy = ref(false)
const notice = ref('')
const noticeIsError = ref(false)
let removeWorkspaceListener: (() => void) | undefined

function showNotice(message?: string, isError = false): void {
  if (!message) return
  notice.value = message
  noticeIsError.value = isError
}

async function runAction(action: () => Promise<AppWorkspaceActionResult>): Promise<void> {
  if (busy.value) return
  busy.value = true
  try {
    const result = await action()
    workspace.value = result.state
    if (result.message) showNotice(result.message, result.status !== 'success')
  } catch (error) {
    showNotice(error instanceof Error ? error.message : '操作失败', true)
  } finally {
    busy.value = false
  }
}

function useCaptureCard(): void {
  const action = workspace.value.currentProject
    ? window.api.capture
    : workspace.value.targetFolder
      ? window.api.createProject
      : window.api.createWorkspace
  void runAction(action)
}

function createProject(): void {
  void runAction(window.api.createProject)
}

function openCurrentProject(): void {
  void runAction(window.api.openCurrentProject)
}

function openReviewDesk(): void {
  void runAction(window.api.openReviewDesk)
}

onMounted(async () => {
  removeWorkspaceListener = window.api.onWorkspaceEvent((event) => {
    workspace.value = event.state
    showNotice(event.message, event.type === 'error')
  })
  try {
    workspace.value = await window.api.getWorkspaceState()
    if (!workspace.value.shortcutAvailable) {
      showNotice('快捷键 Ctrl+Alt+A 不可用，请点击卡片截图', true)
    }
  } catch (error) {
    showNotice(error instanceof Error ? error.message : '无法读取工程状态', true)
  }
})

onBeforeUnmount(() => removeWorkspaceListener?.())
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <nav class="navigation" aria-label="主导航">
        <button class="nav-item" type="button">设置</button>
        <button class="nav-item" type="button">API</button>
        <button class="nav-item" type="button">教程</button>
      </nav>

      <div class="product-mark" aria-label="Stubuddy desktop">
        <span class="product-mark__dot"></span>
        <span>STUBUDDY / DESKTOP</span>
      </div>
    </header>

    <main class="workspace" aria-label="工作台">
      <section class="workspace-card workspace-card--capture" :class="{ 'is-busy': busy }">
        <button class="card-primary" type="button" :disabled="busy" @click="useCaptureCard">
          <span class="card-index">01</span>
          <span class="card-content">
            <strong>截图</strong>
            <span class="capture-details">
              <small
                v-if="workspace.currentProject"
                class="project-path"
                :title="workspace.currentProject"
              >
                {{ workspace.currentProject }}
              </small>
              <small v-else class="create-prompt">请点我创建工程</small>
              <small>截图快捷键 Ctrl+Alt+A</small>
            </span>
          </span>
          <span class="card-arrow" aria-hidden="true">↗</span>
        </button>

        <button
          v-if="workspace.currentProject"
          class="new-project-button"
          type="button"
          :disabled="busy"
          @click="createProject"
        >
          ＋ 新建工程
        </button>
      </section>

      <button
        class="workspace-card workspace-card--folder"
        type="button"
        :disabled="busy"
        @click="openCurrentProject"
      >
        <span class="card-index">02</span>
        <span class="card-content">
          <strong>查看文件夹</strong>
          <small>{{ workspace.currentProject ? 'OPEN PROJECT' : 'NO PROJECT' }}</small>
        </span>
        <span class="card-arrow" aria-hidden="true">↗</span>
      </button>

      <button
        class="workspace-card workspace-card--review"
        type="button"
        :disabled="busy"
        @click="openReviewDesk"
      >
        <span class="card-index">03</span>
        <span class="review-rule" aria-hidden="true"></span>
        <span class="card-content">
          <strong>审阅台</strong>
          <small>REVIEW DESK</small>
        </span>
        <span class="card-arrow" aria-hidden="true">↗</span>
      </button>
    </main>

    <p v-if="notice" class="status-toast" :class="{ 'is-error': noticeIsError }" role="status">
      {{ notice }}
    </p>
  </div>
</template>
