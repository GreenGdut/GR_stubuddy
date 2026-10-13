<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

type ReviewProjectState = Awaited<ReturnType<Window['api']['getReviewFiles']>>
type ReviewContent = Awaited<ReturnType<Window['api']['readReviewFile']>>
type ReviewFileItem = ReviewProjectState['files'][number]

const project = ref<ReviewProjectState | null>(null)
const currentIndex = ref(-1)
const content = ref<ReviewContent | null>(null)
const loading = ref(true)
const error = ref('')
let requestId = 0

const currentFile = computed(() =>
  project.value && currentIndex.value >= 0 ? project.value.files[currentIndex.value] : null
)

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function kindLabel(kind: ReviewFileItem['kind']): string {
  if (kind === 'image') return 'IMAGE'
  if (kind === 'text') return 'TEXT'
  return 'FILE'
}

async function selectPage(index: number): Promise<void> {
  if (!project.value || index < 0 || index >= project.value.files.length) return

  currentIndex.value = index
  content.value = null
  error.value = ''
  const file = project.value.files[index]
  const activeRequest = ++requestId
  if (file.kind === 'unsupported') {
    loading.value = false
    return
  }

  loading.value = true
  try {
    const nextContent = await window.api.readReviewFile(file.path)
    if (activeRequest === requestId) content.value = nextContent
  } catch (readError) {
    if (activeRequest === requestId) {
      error.value = readError instanceof Error ? readError.message : '无法读取文件'
    }
  } finally {
    if (activeRequest === requestId) loading.value = false
  }
}

function turnPage(offset: number): void {
  void selectPage(currentIndex.value + offset)
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
    event.preventDefault()
    turnPage(-1)
  } else if (event.key === 'ArrowRight' || event.key === 'PageDown') {
    event.preventDefault()
    turnPage(1)
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  try {
    project.value = await window.api.getReviewFiles()
    if (project.value.files.length > 0) {
      await selectPage(0)
    } else {
      loading.value = false
    }
  } catch (loadError) {
    loading.value = false
    error.value = loadError instanceof Error ? loadError.message : '无法读取当前工程'
  }
})

onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div class="review-shell">
    <header class="review-header">
      <div class="review-brand">
        <span class="review-brand__index">03</span>
        <div>
          <strong>审阅台</strong>
          <small>REVIEW DESK</small>
        </div>
      </div>
      <div v-if="project" class="review-project" :title="project.path">
        <strong>{{ project.name }}</strong>
        <span>{{ project.files.length }} FILES</span>
      </div>
    </header>

    <main class="review-workspace">
      <aside class="review-file-rail" aria-label="工程文件">
        <div class="review-file-rail__heading">
          <span>PROJECT FILES</span>
          <span>{{ String(project?.files.length ?? 0).padStart(2, '0') }}</span>
        </div>
        <ol v-if="project?.files.length" class="review-file-list">
          <li v-for="(file, index) in project.files" :key="file.path">
            <button
              type="button"
              :class="{ 'is-active': index === currentIndex }"
              :title="file.path"
              @click="selectPage(index)"
            >
              <span class="review-file-number">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="review-file-name">{{ file.path }}</span>
              <span class="review-file-kind">{{ kindLabel(file.kind) }}</span>
            </button>
          </li>
        </ol>
        <p v-else-if="!loading" class="review-file-empty">当前工程没有文件</p>
      </aside>

      <section class="review-page" aria-live="polite">
        <header class="review-page__meta">
          <div v-if="currentFile">
            <span>{{ kindLabel(currentFile.kind) }}</span>
            <strong :title="currentFile.path">{{ currentFile.name }}</strong>
          </div>
          <span v-if="currentFile">{{ formatSize(currentFile.size) }}</span>
          <span v-else>NO FILE SELECTED</span>
        </header>

        <div class="review-preview" :class="{ 'is-image': content?.kind === 'image' }">
          <p v-if="loading" class="review-preview__state">正在读取...</p>
          <div v-else-if="error" class="review-preview__state is-error">
            <strong>无法预览</strong>
            <span>{{ error }}</span>
          </div>
          <img
            v-else-if="content?.kind === 'image'"
            :src="content.dataUrl"
            :alt="currentFile?.name ?? '图片预览'"
          />
          <div v-else-if="content?.kind === 'text'" class="review-text-preview">
            <pre>{{ content.content }}</pre>
            <p v-if="content.truncated">文件较大，仅显示前 2 MB</p>
          </div>
          <div v-else-if="currentFile" class="review-preview__state">
            <strong>暂不支持预览</strong>
            <span>可使用下方按钮继续审阅其他文件</span>
          </div>
          <div v-else-if="!error" class="review-preview__state">
            <strong>没有可审阅的文件</strong>
            <span>文件加入当前 Project 后会显示在这里</span>
          </div>
        </div>

        <footer class="review-pagination">
          <button
            type="button"
            :disabled="currentIndex <= 0"
            aria-label="上一页"
            @click="turnPage(-1)"
          >
            ← <span>上一页</span>
          </button>
          <p>
            <strong>
              {{ currentIndex >= 0 ? String(currentIndex + 1).padStart(2, '0') : '00' }}
            </strong>
            <span>/ {{ String(project?.files.length ?? 0).padStart(2, '0') }}</span>
          </p>
          <button
            type="button"
            :disabled="!project || currentIndex >= project.files.length - 1"
            aria-label="下一页"
            @click="turnPage(1)"
          >
            <span>下一页</span> →
          </button>
        </footer>
      </section>
    </main>
  </div>
</template>
