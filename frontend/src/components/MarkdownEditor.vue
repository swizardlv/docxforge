<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'

const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

const editorId = useId()
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const gutterRef = ref<HTMLDivElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)

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
    // Single markdown file: read directly. Multi-file folder: delegate to store.
    const mdFiles = files.filter((f) => f.name.toLowerCase().endsWith('.md'))
    const nonMd = files.filter((f) => !f.name.toLowerCase().endsWith('.md'))
    if (nonMd.length > 0 || mdFiles.length > 1) {
      // Folder with images or multiple files → use the project workbench
      const { useForgeStore } = await import('@/stores/forge')
      await useForgeStore().importFolderFiles(files)
    } else if (mdFiles.length === 1 && mdFiles[0]) {
      const text = await mdFiles[0].text()
      model.value = text
    }
  }
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
        <button
          type="button"
          :disabled="disabled"
          class="rounded bg-accent/10 px-2 py-1 text-xs font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
          @click="triggerFileImport"
        >
          📄 导入 Markdown 文件
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
      <span>支持拖拽 Markdown/文件夹到左侧面板、自动嵌入本地图片、截图粘贴 (`Cmd+V`)。</span>
      <span class="font-mono tabular-nums">{{ lines }} 行 · {{ characters }} 字符</span>
    </p>
  </div>
</template>
