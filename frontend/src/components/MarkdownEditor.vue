<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useId } from 'vue'

const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

const editorId = useId()
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const gutterRef = ref<HTMLDivElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)

onMounted(() => {
  if (folderInputRef.value) {
    folderInputRef.value.setAttribute('webkitdirectory', '')
    folderInputRef.value.setAttribute('directory', '')
  }
})

const lines = computed(() => model.value.split('\n').length)
const characters = computed(() => model.value.length)

/** Keeps the gutter glued to the textarea's scroll position. */
function syncScroll(): void {
  if (gutterRef.value && textareaRef.value) {
    gutterRef.value.scrollTop = textareaRef.value.scrollTop
  }
}

/** Tab inserts two spaces instead of moving focus out of the editor. */
async function handleTab(event: KeyboardEvent): Promise<void> {
  const el = textareaRef.value
  if (!el || props.disabled) {
    return
  }
  event.preventDefault()
  const { selectionStart, selectionEnd } = el
  const indent = '  '
  model.value = `${model.value.slice(0, selectionStart)}${indent}${model.value.slice(selectionEnd)}`
  await nextTick()
  el.selectionStart = el.selectionEnd = selectionStart + indent.length
}

function triggerFileImport(): void {
  fileInputRef.value?.click()
}

function triggerFolderImport(): void {
  folderInputRef.value?.click()
}

function handleFileImport(event: Event): void {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    const text = e.target?.result
    if (typeof text === 'string') {
      model.value = text
    }
  }
  reader.readAsText(file, 'utf-8')
  target.value = ''
}

/** Process uploaded folder containing markdown & local image files */
async function handleFolderImport(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files ?? [])
  if (files.length === 0) return

  await processFileList(files)
  target.value = ''
}

interface MarkdownFileInfo {
  name: string
  path: string
  content: string
}

const mdFiles = ref<MarkdownFileInfo[]>([])
const selectedMdKey = ref<string>('__ALL__')

async function processFileList(files: File[]): Promise<void> {
  const mdFileList: File[] = []
  const imageFiles: File[] = []

  for (const file of files) {
    const lowerName = file.name.toLowerCase()
    if (lowerName.endsWith('.md') || lowerName.endsWith('.markdown')) {
      mdFileList.push(file)
    } else if (/\.(png|jpe?g|gif|webp|svg)$/i.test(file.name)) {
      imageFiles.push(file)
    }
  }

  if (mdFileList.length === 0) {
    return
  }

  // 1. Natural sort for Markdown files
  mdFileList.sort((a, b) => {
    const pathA = a.webkitRelativePath || a.name
    const pathB = b.webkitRelativePath || b.name
    return pathA.localeCompare(pathB, undefined, { numeric: true, sensitivity: 'base' })
  })

  // 2. Read images as Base64 Data URIs
  const imageMap = new Map<string, string>()
  for (const imgFile of imageFiles) {
    const dataUri = await fileToDataUri(imgFile)
    const relPath = imgFile.webkitRelativePath
      ? imgFile.webkitRelativePath.split('/').slice(1).join('/')
      : imgFile.name
    imageMap.set(relPath.toLowerCase(), dataUri)
    imageMap.set(imgFile.name.toLowerCase(), dataUri)
  }

  // Helper to replace images in a Markdown text
  const replaceImages = (rawText: string) => {
    return rawText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src: string) => {
      if (src.startsWith('data:') || src.startsWith('http://') || src.startsWith('https://')) {
        return match
      }
      const cleanSrc = src.trim().replace(/^\.\//, '').toLowerCase()
      const foundDataUri = imageMap.get(cleanSrc) || imageMap.get(cleanSrc.split('/').pop() ?? '')
      if (foundDataUri) {
        return `![${alt}](${foundDataUri})`
      }
      return match
    })
  }

  // 3. Store parsed markdown file list
  const parsedFiles: MarkdownFileInfo[] = []
  for (const file of mdFileList) {
    const text = await file.text()
    const path = file.webkitRelativePath || file.name
    parsedFiles.push({
      name: file.name,
      path,
      content: replaceImages(text),
    })
  }

  mdFiles.value = parsedFiles
  selectedMdKey.value = '__ALL__'

  applyMdSelection()
}

function applyMdSelection(): void {
  if (mdFiles.value.length === 0) return

  if (selectedMdKey.value === '__ALL__') {
    model.value = mdFiles.value.map((f) => f.content).join('\n\n')
  } else {
    const target = mdFiles.value.find((f) => f.path === selectedMdKey.value)
    if (target) {
      model.value = target.content
    }
  }
}

/** Handle Cmd+V / Ctrl+V image paste */
function handlePaste(event: ClipboardEvent): void {
  const items = Array.from(event.clipboardData?.items ?? [])
  const imageItem = items.find((item) => item.type.startsWith('image/'))
  if (!imageItem) return

  const file = imageItem.getAsFile()
  if (!file) return

  event.preventDefault()
  const reader = new FileReader()
  reader.onload = async (e) => {
    const dataUri = e.target?.result as string
    if (!dataUri) return

    const el = textareaRef.value
    const altText = `粘贴图片_${new Date().toLocaleTimeString()}`
    const mdSnippet = `\n![${altText}](${dataUri})\n`

    if (el) {
      const { selectionStart, selectionEnd } = el
      model.value = `${model.value.slice(0, selectionStart)}${mdSnippet}${model.value.slice(selectionEnd)}`
      await nextTick()
      el.selectionStart = el.selectionEnd = selectionStart + mdSnippet.length
    } else {
      model.value += mdSnippet
    }
  }
  reader.readAsDataURL(file)
}

function handleDragOver(event: DragEvent): void {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave(event: DragEvent): void {
  event.preventDefault()
  isDragging.value = false
}

async function handleDrop(event: DragEvent): Promise<void> {
  event.preventDefault()
  isDragging.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (files.length > 0) {
    await processFileList(files)
  }
}

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve((e.target?.result as string) ?? '')
    reader.readAsDataURL(file)
  })
}

function scrollToLine(targetLine: number): void {
  const el = textareaRef.value
  if (!el || targetLine <= 0) return

  const linesList = model.value.split('\n')
  let charPos = 0
  for (let i = 0; i < Math.min(targetLine - 1, linesList.length); i++) {
    charPos += (linesList[i]?.length ?? 0) + 1
  }

  el.focus()
  el.setSelectionRange(charPos, charPos)
  const lineHeight = 24
  el.scrollTop = Math.max(0, (targetLine - 3) * lineHeight)
}

defineExpose({
  scrollToLine,
})
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex flex-wrap items-center justify-between gap-2 pb-1.5">
      <label
        :for="editorId"
        class="df-label !pb-0"
      >Markdown 正文</label>
      <div class="flex items-center gap-2">
        <!-- Multi-markdown selector -->
        <div
          v-if="mdFiles.length > 1"
          class="flex items-center gap-1.5 rounded bg-surface-muted px-2 py-0.5 border border-line text-xs"
        >
          <span class="text-ink-muted">📚 已检测到 {{ mdFiles.length }} 个 Markdown 文件:</span>
          <select
            v-model="selectedMdKey"
            class="bg-transparent font-medium text-accent outline-none cursor-pointer"
            @change="applyMdSelection"
          >
            <option value="__ALL__">
              ✨ 自动按顺序合并所有文件 (共 {{ mdFiles.length }} 个)
            </option>
            <option
              v-for="file in mdFiles"
              :key="file.path"
              :value="file.path"
            >
              📄 {{ file.path }}
            </option>
          </select>
        </div>

        <button
          type="button"
          :disabled="disabled"
          class="rounded bg-accent/10 px-2 py-1 text-xs font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
          @click="triggerFolderImport"
        >
          📂 导入项目文件夹 (推荐：含自动绑定图片)
        </button>
        <button
          type="button"
          :disabled="disabled"
          class="text-xs text-ink-muted hover:text-ink disabled:opacity-50"
          @click="triggerFileImport"
        >
          📄 单文件
        </button>
      </div>

      <!-- Single file input -->
      <input
        ref="fileInputRef"
        type="file"
        accept=".md,.markdown,.txt"
        class="hidden"
        @change="handleFileImport"
      >

      <!-- Directory folder input -->
      <input
        ref="folderInputRef"
        type="file"
        webkitdirectory
        multiple
        class="hidden"
        @change="handleFolderImport"
      >
    </div>
    <div
      class="relative flex min-h-0 flex-1 overflow-hidden rounded-md border bg-surface transition-colors focus-within:border-accent"
      :class="[isDragging ? 'border-accent ring-2 ring-accent/20' : 'border-line']"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <!-- Line numbers are decorative; screen readers read the textarea only. -->
      <div
        ref="gutterRef"
        aria-hidden="true"
        class="w-12 shrink-0 overflow-hidden border-r border-line-soft bg-surface-muted py-3 text-right font-mono text-[13px]/6 text-ink-muted select-none"
      >
        <div
          v-for="n in lines"
          :key="n"
        >
          {{ n }}
        </div>
        <div class="h-16" />
      </div>
      <textarea
        :id="editorId"
        ref="textareaRef"
        v-model="model"
        :disabled="disabled"
        spellcheck="false"
        autocomplete="off"
        autocapitalize="off"
        wrap="off"
        :aria-describedby="`${editorId}-hint`"
        class="min-h-[18rem] flex-1 resize-none overflow-auto bg-surface px-3 py-3 font-mono text-[13px]/6 text-ink outline-none disabled:bg-surface-muted disabled:text-ink-muted"
        @scroll="syncScroll"
        @keydown.tab="handleTab"
        @paste="handlePaste"
      />

      <div
        v-if="isDragging"
        class="pointer-events-none absolute inset-0 flex items-center justify-center bg-accent/5 backdrop-blur-[1px]"
      >
        <p class="rounded-lg bg-surface px-4 py-2 text-sm font-medium text-accent shadow-md">
          📥 释放鼠标以导入 Markdown 文件与图片文件夹
        </p>
      </div>
    </div>
    <p
      :id="`${editorId}-hint`"
      class="df-hint flex items-center justify-between"
    >
      <span>支持拖拽项目文件夹一键导入、自动嵌入本地图片、截图粘贴 (`Cmd+V`)。</span>
      <span class="font-mono tabular-nums">{{ lines }} 行 · {{ characters }} 字符</span>
    </p>
  </div>
</template>
