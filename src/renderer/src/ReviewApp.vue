<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

type ReviewProjectState = Awaited<ReturnType<Window['api']['getReviewFiles']>>
type ReviewContent = Awaited<ReturnType<Window['api']['readReviewFile']>>
type ReviewFileItem = ReviewProjectState['files'][number]

const EDITABLE_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']

const project = ref<ReviewProjectState | null>(null)
const currentIndex = ref(-1)
const content = ref<ReviewContent | null>(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const saving = ref(false)
const confirmingOverwrite = ref(false)
const renaming = ref(false)
const renameValue = ref('')
const cropMode = ref(false)
const cropRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const workingDataUrl = ref('')

const previewRef = ref<HTMLDivElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const renameInputRef = ref<HTMLInputElement | null>(null)
let editCanvas: HTMLCanvasElement | null = null
let dragStart: { x: number; y: number } | null = null
let requestId = 0

const currentFile = computed(() =>
  project.value && currentIndex.value >= 0 ? project.value.files[currentIndex.value] : null
)

const canEditImage = computed(
  () =>
    content.value?.kind === 'image' &&
    !!currentFile.value &&
    EDITABLE_IMAGE_EXTENSIONS.includes(fileExtension(currentFile.value.name))
)

const imageMime = computed(() => {
  const extension = currentFile.value ? fileExtension(currentFile.value.name) : ''
  if (extension === 'jpg' || extension === 'jpeg') return 'image/jpeg'
  if (extension === 'webp') return 'image/webp'
  return 'image/png'
})

const previewSrc = computed(() => {
  if (workingDataUrl.value) return workingDataUrl.value
  return content.value?.kind === 'image' ? content.value.dataUrl : ''
})

const hasEdits = computed(() => workingDataUrl.value !== '')

const cropStyle = computed(() => {
  const rect = cropRect.value
  if (!rect) return {}
  return {
    left: `${rect.x}px`,
    top: `${rect.y}px`,
    width: `${rect.w}px`,
    height: `${rect.h}px`
  }
})

function fileExtension(name: string): string {
  const index = name.lastIndexOf('.')
  return index === -1 ? '' : name.slice(index + 1).toLowerCase()
}

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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function resetEdits(): void {
  editCanvas = null
  workingDataUrl.value = ''
  cropMode.value = false
  cropRect.value = null
  dragStart = null
  confirmingOverwrite.value = false
  removeDragListeners()
}

async function selectPage(index: number): Promise<void> {
  if (!project.value || index < 0 || index >= project.value.files.length) return

  currentIndex.value = index
  content.value = null
  error.value = ''
  notice.value = ''
  renaming.value = false
  resetEdits()
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

async function reloadAndSelect(relativePath: string): Promise<void> {
  project.value = await window.api.getReviewFiles()
  const index = project.value.files.findIndex((file) => file.path === relativePath)
  await selectPage(index >= 0 ? index : 0)
}

function turnPage(offset: number): void {
  void selectPage(currentIndex.value + offset)
}

function handleKeydown(event: KeyboardEvent): void {
  if (renaming.value) return
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
    event.preventDefault()
    turnPage(-1)
  } else if (event.key === 'ArrowRight' || event.key === 'PageDown') {
    event.preventDefault()
    turnPage(1)
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('无法加载图片'))
    image.src = src
  })
}

async function ensureCanvas(): Promise<HTMLCanvasElement> {
  if (editCanvas) return editCanvas
  if (content.value?.kind !== 'image') throw new Error('当前文件不是图片')
  const image = await loadImage(content.value.dataUrl)
  const canvas = document.createElement('canvas')
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  canvas.getContext('2d')?.drawImage(image, 0, 0)
  editCanvas = canvas
  return canvas
}

function refreshWorking(): void {
  if (!editCanvas) return
  workingDataUrl.value = editCanvas.toDataURL(imageMime.value)
}

function rotate(direction: number): void {
  void rotateAsync(direction)
}

async function rotateAsync(direction: number): Promise<void> {
  if (!canEditImage.value) return
  notice.value = ''
  try {
    const source = await ensureCanvas()
    const output = document.createElement('canvas')
    output.width = source.height
    output.height = source.width
    const context = output.getContext('2d')
    if (!context) return
    context.translate(output.width / 2, output.height / 2)
    context.rotate((direction * Math.PI) / 2)
    context.drawImage(source, -source.width / 2, -source.height / 2)
    editCanvas = output
    refreshWorking()
  } catch (rotateError) {
    notice.value = rotateError instanceof Error ? rotateError.message : '旋转失败'
  }
}

function startCrop(): void {
  cropMode.value = true
  cropRect.value = null
  notice.value = ''
}

function cancelCrop(): void {
  cropMode.value = false
  cropRect.value = null
  dragStart = null
  removeDragListeners()
}

function removeDragListeners(): void {
  window.removeEventListener('pointermove', onCropPointerMove)
  window.removeEventListener('pointerup', onCropPointerUp)
}

function stagePoint(event: PointerEvent): { x: number; y: number } {
  const bounds = previewRef.value?.getBoundingClientRect()
  if (!bounds) return { x: 0, y: 0 }
  return {
    x: clamp(event.clientX - bounds.left, 0, bounds.width),
    y: clamp(event.clientY - bounds.top, 0, bounds.height)
  }
}

function imageBox(): { left: number; top: number; width: number; height: number } | null {
  const preview = previewRef.value
  const image = imageRef.value
  if (!preview || !image) return null
  const previewBounds = preview.getBoundingClientRect()
  const imageBounds = image.getBoundingClientRect()
  return {
    left: imageBounds.left - previewBounds.left,
    top: imageBounds.top - previewBounds.top,
    width: imageBounds.width,
    height: imageBounds.height
  }
}

function onCropPointerDown(event: PointerEvent): void {
  if (!cropMode.value) return
  event.preventDefault()
  dragStart = stagePoint(event)
  cropRect.value = { x: dragStart.x, y: dragStart.y, w: 0, h: 0 }
  window.addEventListener('pointermove', onCropPointerMove)
  window.addEventListener('pointerup', onCropPointerUp)
}

function onCropPointerMove(event: PointerEvent): void {
  if (!dragStart) return
  const point = stagePoint(event)
  cropRect.value = {
    x: Math.min(dragStart.x, point.x),
    y: Math.min(dragStart.y, point.y),
    w: Math.abs(point.x - dragStart.x),
    h: Math.abs(point.y - dragStart.y)
  }
}

function onCropPointerUp(): void {
  dragStart = null
  removeDragListeners()
  if (cropRect.value && (cropRect.value.w < 4 || cropRect.value.h < 4)) cropRect.value = null
}

function applyCrop(): void {
  void applyCropAsync()
}

async function applyCropAsync(): Promise<void> {
  const rect = cropRect.value
  const box = imageBox()
  if (!rect || !box || box.width === 0 || box.height === 0) return
  try {
    const source = await ensureCanvas()
    const scaleX = source.width / box.width
    const scaleY = source.height / box.height
    const sourceX = clamp(Math.round((rect.x - box.left) * scaleX), 0, source.width - 1)
    const sourceY = clamp(Math.round((rect.y - box.top) * scaleY), 0, source.height - 1)
    const width = clamp(Math.round(rect.w * scaleX), 1, source.width - sourceX)
    const height = clamp(Math.round(rect.h * scaleY), 1, source.height - sourceY)
    const output = document.createElement('canvas')
    output.width = width
    output.height = height
    output.getContext('2d')?.drawImage(source, sourceX, sourceY, width, height, 0, 0, width, height)
    editCanvas = output
    refreshWorking()
    cropMode.value = false
    cropRect.value = null
  } catch (cropError) {
    notice.value = cropError instanceof Error ? cropError.message : '裁剪失败'
  }
}

function saveEdits(mode: 'copy' | 'overwrite'): void {
  void saveEditsAsync(mode)
}

async function saveEditsAsync(mode: 'copy' | 'overwrite'): Promise<void> {
  const file = currentFile.value
  if (!file || !editCanvas) return
  saving.value = true
  notice.value = ''
  try {
    const dataUrl = editCanvas.toDataURL(imageMime.value)
    const result = await window.api.writeReviewImage(file.path, dataUrl, mode)
    await reloadAndSelect(result.path)
    notice.value = mode === 'overwrite' ? `已覆盖保存 ${result.path}` : `已另存为 ${result.path}`
  } catch (saveError) {
    notice.value = saveError instanceof Error ? saveError.message : '保存失败'
  } finally {
    saving.value = false
    confirmingOverwrite.value = false
  }
}

function startRename(): void {
  if (!currentFile.value) return
  renameValue.value = currentFile.value.name
  renaming.value = true
  void nextTick(() => renameInputRef.value?.focus())
}

function cancelRename(): void {
  renaming.value = false
}

function confirmRename(): void {
  void confirmRenameAsync()
}

async function confirmRenameAsync(): Promise<void> {
  const file = currentFile.value
  if (!file) return
  const nextName = renameValue.value.trim()
  if (!nextName) {
    notice.value = '文件名不能为空'
    return
  }
  if (nextName === file.name) {
    renaming.value = false
    return
  }
  try {
    const result = await window.api.renameReviewFile(file.path, nextName)
    await reloadAndSelect(result.path)
    notice.value = `已重命名为 ${result.path}`
  } catch (renameError) {
    notice.value = renameError instanceof Error ? renameError.message : '重命名失败'
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

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  removeDragListeners()
})
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
          <div v-if="currentFile" class="review-page__identity">
            <span>{{ kindLabel(currentFile.kind) }}</span>
            <template v-if="renaming">
              <input
                ref="renameInputRef"
                v-model="renameValue"
                class="review-rename-input"
                type="text"
                spellcheck="false"
                @keydown.enter.prevent="confirmRename"
                @keydown.esc.prevent="cancelRename"
              />
              <button type="button" class="review-action is-primary" @click="confirmRename">
                确定
              </button>
              <button type="button" class="review-action" @click="cancelRename">取消</button>
            </template>
            <template v-else>
              <strong :title="currentFile.path">{{ currentFile.name }}</strong>
              <button type="button" class="review-action" @click="startRename">重命名</button>
            </template>
          </div>
          <span v-else>NO FILE SELECTED</span>

          <div class="review-toolbar">
            <template v-if="canEditImage && !renaming">
              <button
                type="button"
                class="review-action"
                :disabled="saving"
                title="逆时针旋转 90°"
                @click="rotate(-1)"
              >
                ↺ 左旋
              </button>
              <button
                type="button"
                class="review-action"
                :disabled="saving"
                title="顺时针旋转 90°"
                @click="rotate(1)"
              >
                ↻ 右旋
              </button>
              <template v-if="cropMode">
                <button
                  type="button"
                  class="review-action is-primary"
                  :disabled="!cropRect"
                  @click="applyCrop"
                >
                  应用裁剪
                </button>
                <button type="button" class="review-action" @click="cancelCrop">取消裁剪</button>
              </template>
              <button
                v-else
                type="button"
                class="review-action"
                :disabled="saving"
                @click="startCrop"
              >
                裁剪
              </button>
              <template v-if="hasEdits">
                <template v-if="confirmingOverwrite">
                  <span class="review-confirm-text">覆盖原文件？</span>
                  <button
                    type="button"
                    class="review-action is-danger"
                    :disabled="saving"
                    @click="saveEdits('overwrite')"
                  >
                    确认覆盖
                  </button>
                  <button
                    type="button"
                    class="review-action"
                    :disabled="saving"
                    @click="confirmingOverwrite = false"
                  >
                    取消
                  </button>
                </template>
                <template v-else>
                  <button
                    type="button"
                    class="review-action"
                    :disabled="saving"
                    @click="confirmingOverwrite = true"
                  >
                    覆盖保存
                  </button>
                  <button
                    type="button"
                    class="review-action is-primary"
                    :disabled="saving"
                    @click="saveEdits('copy')"
                  >
                    {{ saving ? '保存中…' : '另存副本' }}
                  </button>
                  <button
                    type="button"
                    class="review-action"
                    :disabled="saving"
                    @click="resetEdits"
                  >
                    放弃编辑
                  </button>
                </template>
              </template>
            </template>
            <span v-if="currentFile" class="review-size">{{ formatSize(currentFile.size) }}</span>
          </div>
          <p v-if="notice" class="review-edit-notice">{{ notice }}</p>
        </header>

        <div
          ref="previewRef"
          class="review-preview"
          :class="{ 'is-image': content?.kind === 'image', 'is-cropping': cropMode }"
          @pointerdown="onCropPointerDown"
        >
          <p v-if="loading" class="review-preview__state">正在读取...</p>
          <div v-else-if="error" class="review-preview__state is-error">
            <strong>无法预览</strong>
            <span>{{ error }}</span>
          </div>
          <img
            v-else-if="content?.kind === 'image'"
            ref="imageRef"
            :src="previewSrc"
            :alt="currentFile?.name ?? '图片预览'"
            draggable="false"
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
          <div v-if="cropMode" class="review-crop-box" :style="cropStyle"></div>
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
