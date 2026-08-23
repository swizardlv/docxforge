import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'

import { ApiError, MOCK_BLOB_TYPE, resolveApi, type ApiMode, type DocXForgeApi } from '@/api'
import {
  defaultHeaderFooterOptions,
  defaultRenderOptions,
  defaultTocOptions,
  type HealthResponse,
  type JobInfo,
  type RenderRequest,
  type RenderResponse,
  type StyleMap,
  type TemplateInfo,
  type TemplateStylesResponse,
  type DestroyReport,
} from '@/types/api'
import { parseOutline } from '@/utils/outline'
import { SAMPLE_MARKDOWN } from '@/utils/sample'

/** One editable `find -> replace` pair of `CoverOptions.replacements`. */
export interface CoverField {
  id: number
  find: string
  replace: string
}

/** A Markdown file imported from a folder (project workbench). */
export interface MarkdownFileInfo {
  name: string
  path: string
  content: string
}

const COUNTDOWN_TICK_MS = 250

function toApiError(error: unknown, fallbackMessage: string): ApiError {
  if (error instanceof ApiError) {
    return error
  }
  return ApiError.network(fallbackMessage, error instanceof Error ? error.message : String(error))
}

function defaultCoverFields(): CoverField[] {
  return [
    { id: 1, find: '项目名称', replace: '' },
    { id: 2, find: '投标单位', replace: '' },
    { id: 3, find: '投标日期', replace: '' },
  ]
}

export const useForgeStore = defineStore('forge', () => {
  // --- connection -----------------------------------------------------------
  const api = shallowRef<DocXForgeApi | null>(null)
  const apiMode = ref<ApiMode | 'unknown'>('unknown')
  const health = ref<HealthResponse | null>(null)
  const fallbackReason = ref<string | null>(null)
  const connecting = ref(false)

  // --- templates ------------------------------------------------------------
  const templates = ref<TemplateInfo[]>([])
  const templatesLoading = ref(false)
  const templateError = ref<ApiError | null>(null)
  const uploading = ref(false)

  // --- project workbench (session-scoped multi-file editing) ---------------
  const projectFiles = ref<MarkdownFileInfo[]>([])
  const selectedFileKey = ref<string | null>(null)

  // --- style mapping panel -------------------------------------------------
  const stylePanelOpen = ref(false)
  const templateStyles = ref<TemplateStylesResponse | null>(null)
  const stylesLoading = ref(false)
  const stylesSaving = ref(false)
  const stylesError = ref<ApiError | null>(null)

  // --- document form --------------------------------------------------------
  const markdown = ref(SAMPLE_MARKDOWN)
  const docTitle = ref('XX市智能化项目投标书')
  const filename = ref('')
  const baseDir = ref('')
  const templateId = ref<string | null>(null)
  const toc = ref(defaultTocOptions())
  const headerFooter = ref(defaultHeaderFooterOptions())
  const options = ref(defaultRenderOptions())
  const coverEnabled = ref(true)
  const coverPageBreakAfter = ref(true)
  const coverFields = ref<CoverField[]>(defaultCoverFields())
  let coverFieldSeq = coverFields.value.length

  // --- export / job ---------------------------------------------------------
  const exporting = ref(false)
  const exportError = ref<ApiError | null>(null)
  const lastRender = ref<RenderResponse | null>(null)
  const job = ref<JobInfo | null>(null)
  const downloading = ref(false)
  const downloadError = ref<ApiError | null>(null)
  const destroying = ref(false)
  const destroyError = ref<ApiError | null>(null)
  const destroyReport = ref<DestroyReport | null>(null)
  const secondsRemaining = ref(0)

  let countdownTimer: ReturnType<typeof setInterval> | null = null

  // --- derived --------------------------------------------------------------
  const outline = computed(() => parseOutline(markdown.value))
  const isMock = computed(() => apiMode.value === 'mock')
  const isDestroyed = computed(() => job.value?.state === 'destroyed')
  const canDownload = computed(() => job.value?.state === 'ready' && secondsRemaining.value > 0)
  const ttlSeconds = computed(() => job.value?.ttl_seconds ?? health.value?.job_ttl_seconds ?? 60)
  const selectedTemplate = computed(
    () => templates.value.find((item) => item.template_id === templateId.value) ?? null,
  )
  const coverReplacements = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const field of coverFields.value) {
      const key = field.find.trim()
      if (key) {
        map[key] = field.replace
      }
    }
    return map
  })

  function requireApi(): DocXForgeApi {
    if (!api.value) {
      throw ApiError.network('API 尚未初始化，请稍候重试。')
    }
    return api.value
  }

  // --- connection actions ---------------------------------------------------
  async function connect(): Promise<void> {
    connecting.value = true
    try {
      const resolved = await resolveApi()
      api.value = resolved.api
      apiMode.value = resolved.api.mode
      health.value = resolved.health
      fallbackReason.value = resolved.fallbackReason
    } finally {
      connecting.value = false
    }
    await loadTemplates()
  }

  async function loadTemplates(): Promise<void> {
    templatesLoading.value = true
    templateError.value = null
    try {
      templates.value = await requireApi().listTemplates()
      if (templateId.value && !templates.value.some((t) => t.template_id === templateId.value)) {
        templateId.value = null
      }
    } catch (error) {
      templateError.value = toApiError(error, '模板列表加载失败。')
      templates.value = []
    } finally {
      templatesLoading.value = false
    }
  }

  async function uploadTemplate(file: File, name?: string): Promise<boolean> {
    uploading.value = true
    templateError.value = null
    try {
      const info = await requireApi().uploadTemplate(file, name)
      templates.value = [...templates.value, info]
      templateId.value = info.template_id
      return true
    } catch (error) {
      templateError.value = toApiError(error, '模板上传失败。')
      return false
    } finally {
      uploading.value = false
    }
  }

  async function removeTemplate(id: string): Promise<void> {
    templateError.value = null
    try {
      await requireApi().deleteTemplate(id)
      templates.value = templates.value.filter((item) => item.template_id !== id)
      if (templateId.value === id) {
        templateId.value = null
      }
    } catch (error) {
      templateError.value = toApiError(error, '模板删除失败。')
    }
  }

  // --- project files --------------------------------------------------------
  function fileToDataUri(file: File): Promise<string> {
    return new Promise((resolve) => {
      const reader = new FileReader()
      reader.onload = (e) => resolve((e.target?.result as string) ?? '')
      reader.readAsDataURL(file)
    })
  }

  async function importFolderFiles(files: File[]): Promise<void> {
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

    if (mdFileList.length === 0) return

    // Natural sort
    mdFileList.sort((a, b) => {
      const pathA = a.webkitRelativePath || a.name
      const pathB = b.webkitRelativePath || b.name
      return pathA.localeCompare(pathB, undefined, { numeric: true, sensitivity: 'base' })
    })

    // Read images as Base64 data URIs
    const imageMap = new Map<string, string>()
    for (const imgFile of imageFiles) {
      const dataUri = await fileToDataUri(imgFile)
      const relPath = imgFile.webkitRelativePath
        ? imgFile.webkitRelativePath.split('/').slice(1).join('/')
        : imgFile.name
      imageMap.set(relPath.toLowerCase(), dataUri)
      imageMap.set(imgFile.name.toLowerCase(), dataUri)
    }

    const replaceImages = (rawText: string) =>
      rawText.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src: string) => {
        if (src.startsWith('data:') || src.startsWith('http://') || src.startsWith('https://')) {
          return match
        }
        const cleanSrc = src.trim().replace(/^\.\//, '').toLowerCase()
        const foundDataUri = imageMap.get(cleanSrc) || imageMap.get(cleanSrc.split('/').pop() ?? '')
        return foundDataUri ? `![${alt}](${foundDataUri})` : match
      })

    const parsedFiles: MarkdownFileInfo[] = []
    for (const file of mdFileList) {
      const text = await file.text()
      const path = file.webkitRelativePath || file.name
      parsedFiles.push({ name: file.name, path, content: replaceImages(text) })
    }

    projectFiles.value = parsedFiles
    selectedFileKey.value = '__ALL__'
    applyProjectFileSelection()
  }

  function selectProjectFile(key: string | null): void {
    selectedFileKey.value = key
    applyProjectFileSelection()
  }

  function applyProjectFileSelection(): void {
    if (projectFiles.value.length === 0) return
    if (selectedFileKey.value === '__ALL__') {
      markdown.value = projectFiles.value.map((f) => f.content).join('\n\n')
    } else {
      const target = projectFiles.value.find((f) => f.path === selectedFileKey.value)
      if (target) markdown.value = target.content
    }
  }

  // --- style mapping --------------------------------------------------------
  async function loadTemplateStyles(templateId: string): Promise<void> {
    stylesLoading.value = true
    stylesError.value = null
    try {
      templateStyles.value = await requireApi().getTemplateStyles(templateId)
    } catch (error) {
      stylesError.value = toApiError(error, '样式加载失败。')
      templateStyles.value = null
    } finally {
      stylesLoading.value = false
    }
  }

  async function saveStyleMap(templateId: string, styleMap: StyleMap): Promise<boolean> {
    stylesSaving.value = true
    stylesError.value = null
    try {
      await requireApi().saveStyleMap(templateId, styleMap)
      if (templateStyles.value) {
        templateStyles.value = { ...templateStyles.value, style_map: styleMap }
      }
      return true
    } catch (error) {
      stylesError.value = toApiError(error, '样式映射保存失败。')
      return false
    } finally {
      stylesSaving.value = false
    }
  }

  function openStylePanel(): void {
    stylePanelOpen.value = true
    // Always (re)load: the style list is per-template and the user may have
    // switched templates or freshly uploaded one since the panel last opened.
    if (templateId.value) {
      void loadTemplateStyles(templateId.value)
    }
  }

  function closeStylePanel(): void {
    stylePanelOpen.value = false
  }

  // --- cover fields ---------------------------------------------------------
  function addCoverField(): void {
    coverFieldSeq += 1
    coverFields.value = [...coverFields.value, { id: coverFieldSeq, find: '', replace: '' }]
  }

  function removeCoverField(id: number): void {
    coverFields.value = coverFields.value.filter((field) => field.id !== id)
  }

  // --- countdown ------------------------------------------------------------
  function stopCountdown(): void {
    if (countdownTimer !== null) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }

  function computeRemaining(): number {
    const current = job.value
    if (!current || current.state === 'destroyed') {
      return 0
    }
    const deadline = current.expires_at
      ? Date.parse(current.expires_at)
      : Date.parse(current.created_at) + current.ttl_seconds * 1000
    if (Number.isNaN(deadline)) {
      return current.ttl_seconds
    }
    return Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
  }

  /** Local-only transition once the TTL elapses; the sandbox reaper does the real work. */
  function markExpired(): void {
    stopCountdown()
    secondsRemaining.value = 0
    if (job.value && job.value.state !== 'destroyed') {
      job.value = {
        ...job.value,
        state: 'destroyed',
        destroyed_at: new Date().toISOString(),
      }
    }
    // Best-effort reconciliation; a 404/410 here is the expected outcome.
    const current = job.value
    if (current && api.value) {
      api.value
        .getJob(current.job_id)
        .then((info) => {
          job.value = info
        })
        .catch(() => undefined)
    }
  }

  function startCountdown(): void {
    stopCountdown()
    secondsRemaining.value = computeRemaining()
    countdownTimer = setInterval(() => {
      const remaining = computeRemaining()
      secondsRemaining.value = remaining
      if (remaining <= 0) {
        markExpired()
      }
    }, COUNTDOWN_TICK_MS)
  }

  // --- export ---------------------------------------------------------------
  function buildRequest(): RenderRequest {
    const stem = filename.value.trim() || docTitle.value.trim() || null
    return {
      markdown: markdown.value,
      doc_title: docTitle.value.trim() || null,
      template_id: templateId.value,
      toc: { ...toc.value, title: toc.value.title?.trim() || null },
      cover: {
        enabled: coverEnabled.value,
        replacements: coverReplacements.value,
        page_break_after: coverPageBreakAfter.value,
      },
      header_footer: {
        ...headerFooter.value,
        header_text: headerFooter.value.header_text?.trim() || null,
        footer_text: headerFooter.value.footer_text?.trim() || null,
      },
      options: { ...options.value },
      filename: stem,
      base_dir: baseDir.value.trim() || null,
    }
  }

  async function exportDocument(): Promise<boolean> {
    if (exporting.value) {
      return false
    }
    exportError.value = null
    downloadError.value = null
    destroyError.value = null
    destroyReport.value = null
    if (!markdown.value.trim()) {
      exportError.value = new ApiError({
        code: 'markdown_parse_error',
        message: 'Markdown 内容为空，请先输入正文。',
        detail: null,
      })
      return false
    }
    exporting.value = true
    stopCountdown()
    try {
      const response = await requireApi().render(buildRequest())
      lastRender.value = response
      job.value = {
        job_id: response.job_id,
        state: 'ready',
        filename: response.filename,
        created_at: new Date().toISOString(),
        expires_at: response.expires_at ?? null,
        destroyed_at: null,
        ttl_seconds: response.ttl_seconds,
        elapsed_ms: response.elapsed_ms,
        warnings: response.warnings,
        error: null,
      }
      startCountdown()
      return true
    } catch (error) {
      exportError.value = toApiError(error, '导出失败。')
      job.value = null
      lastRender.value = null
      return false
    } finally {
      exporting.value = false
    }
  }

  async function downloadDocument(): Promise<void> {
    const current = job.value
    if (!current || downloading.value) {
      return
    }
    downloading.value = true
    downloadError.value = null
    try {
      const blob = await requireApi().downloadJob(current.job_id)
      const base = current.filename ?? 'docxforge.docx'
      // The mock adapter returns a text placeholder rather than an OOXML package.
      const name = blob.type === MOCK_BLOB_TYPE ? `${base}.txt` : base
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = name
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      downloadError.value = toApiError(error, '下载失败。')
    } finally {
      downloading.value = false
    }
  }

  async function destroyNow(): Promise<void> {
    const current = job.value
    if (!current || destroying.value) {
      return
    }
    destroying.value = true
    destroyError.value = null
    try {
      const report = await requireApi().destroyJob(current.job_id)
      destroyReport.value = report
      job.value = {
        ...current,
        state: 'destroyed',
        destroyed_at: report.destroyed_at ?? new Date().toISOString(),
      }
    } catch (error) {
      const apiError = toApiError(error, '销毁请求失败。')
      // 404/410 means the sandbox is already gone - that is still a success.
      if (apiError.code === 'job_not_found' || apiError.code === 'job_expired') {
        job.value = { ...current, state: 'destroyed', destroyed_at: new Date().toISOString() }
      } else {
        destroyError.value = apiError
      }
    } finally {
      destroying.value = false
      stopCountdown()
      secondsRemaining.value = 0
    }
  }

  function dismissExportError(): void {
    exportError.value = null
  }

  return {
    // connection
    api,
    apiMode,
    health,
    fallbackReason,
    connecting,
    isMock,
    connect,
    // templates
    templates,
    templatesLoading,
    templateError,
    uploading,
    templateId,
    selectedTemplate,
    loadTemplates,
    uploadTemplate,
    removeTemplate,
    // project files
    projectFiles,
    selectedFileKey,
    importFolderFiles,
    selectProjectFile,
    // style mapping
    stylePanelOpen,
    templateStyles,
    stylesLoading,
    stylesSaving,
    stylesError,
    loadTemplateStyles,
    saveStyleMap,
    openStylePanel,
    closeStylePanel,
    // form
    markdown,
    docTitle,
    filename,
    baseDir,
    toc,
    headerFooter,
    options,
    coverEnabled,
    coverPageBreakAfter,
    coverFields,
    coverReplacements,
    addCoverField,
    removeCoverField,
    outline,
    // export
    exporting,
    exportError,
    lastRender,
    job,
    downloading,
    downloadError,
    destroying,
    destroyError,
    destroyReport,
    secondsRemaining,
    ttlSeconds,
    isDestroyed,
    canDownload,
    exportDocument,
    downloadDocument,
    destroyNow,
    stopCountdown,
    dismissExportError,
  }
})
