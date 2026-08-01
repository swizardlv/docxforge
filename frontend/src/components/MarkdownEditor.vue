<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'

const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })

const editorId = useId()
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const gutterRef = ref<HTMLDivElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const folderInputRef = ref<HTMLInputElement | null>(null)

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

  let mdFile: File | null = null
  const imageFiles: File[] = []

  for (const file of files) {
    const lowerName = file.name.toLowerCase()
    if (lowerName.endsWith('.md') || lowerName.endsWith('.markdown')) {
      if (!mdFile || lowerName === 'readme.md' || lowerName === 'index.md') {
        mdFile = file
      }
    } else if (/\.(png|jpe?g|gif|webp|svg)$/i.test(file.name)) {
      imageFiles.push(file)
    }
  }

  if (!mdFile) {
    target.value = ''
    return
  }

  const mdText = await mdFile.text()
  const imageMap = new Map<string, string>()

  // Read images as Base64 Data URIs
  for (const imgFile of imageFiles) {
    const dataUri = await fileToDataUri(imgFile)
    const relPath = imgFile.webkitRelativePath
      ? imgFile.webkitRelativePath.split('/').slice(1).join('/')
      : imgFile.name
    imageMap.set(relPath.toLowerCase(), dataUri)
    imageMap.set(imgFile.name.toLowerCase(), dataUri)
  }

  // Replace relative image references with inline Data URIs
  const processedMd = mdText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src: string) => {
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

  model.value = processedMd
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

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve((e.target?.result as string) ?? '')
    reader.readAsDataURL(file)
  })
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="flex flex-wrap items-center justify-between gap-2 pb-1.5">
      <label
        :for="editorId"
        class="df-label !pb-0"
      >Markdown 正文</label>
      <div class="flex items-center gap-3">
        <button
          type="button"
          :disabled="disabled"
          class="text-xs text-accent hover:text-accent-hover disabled:opacity-50"
          @click="triggerFileImport"
        >
          📄 导入单文件
        </button>
        <button
          type="button"
          :disabled="disabled"
          class="text-xs text-accent hover:text-accent-hover disabled:opacity-50"
          @click="triggerFolderImport"
        >
          📂 导入项目文件夹 (含图片)
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
      class="flex min-h-0 flex-1 overflow-hidden rounded-md border border-line bg-surface focus-within:border-accent"
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
    </div>
    <p
      :id="`${editorId}-hint`"
      class="df-hint flex items-center justify-between"
    >
      <span>支持项目文件夹导入、直接粘贴截图图片 (`Cmd+V`)、表格与代码块。</span>
      <span class="font-mono tabular-nums">{{ lines }} 行 · {{ characters }} 字符</span>
    </p>
  </div>
</template>
