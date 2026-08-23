import { ApiError, type DocXForgeApi } from '@/api/client'
import type {
  DestroyReport,
  JobInfo,
  RenderRequest,
  RenderResponse,
  StyleEntry,
  StyleMap,
  StyleRole,
  TemplateInfo,
  TemplateStylesResponse,
} from '@/types/api'

/**
 * Offline adapter used when `VITE_USE_MOCK_API` is set or when the backend
 * probe fails. It keeps state in module memory only - nothing is persisted,
 * which matches the product's ephemeral promise.
 *
 * The blob returned by `downloadJob` is a plain-text placeholder, not a real
 * OOXML package; callers detect this via the blob MIME type.
 */

const TTL_SECONDS = 60
const LATENCY_MS = 420

export const MOCK_BLOB_TYPE = 'text/plain;charset=utf-8'

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function defaultStyleMap(): StyleMap {
  return {
    headings: {
      '1': 'Heading1',
      '2': 'Heading2',
      '3': 'Heading3',
      '4': 'Heading4',
      '5': 'Heading5',
      '6': 'Heading6',
    },
    paragraph: 'Normal',
    list_ordered: 'ListNumber',
    list_bullet: 'ListBullet',
    quote: 'Quote',
    code: 'HTMLPreformatted',
    caption: 'Caption',
    table: 'TableGrid',
    title: 'Title',
  }
}

function seedTemplates(): TemplateInfo[] {
  return [
    {
      template_id: 'builtin_gb_bid',
      name: '国标标书模板（内置示例）',
      source_path: null,
      styles: [
        { style_id: 'Heading1', name: '标题 1', type: 'paragraph', font: '黑体', size_pt: 22 },
        { style_id: 'Heading2', name: '标题 2', type: 'paragraph', font: '黑体', size_pt: 16 },
        { style_id: 'Normal', name: '正文', type: 'paragraph', font: '仿宋_GB2312', size_pt: 12 },
      ],
      style_map: defaultStyleMap(),
      has_numbering: true,
      has_theme: true,
      has_cover: true,
      cover_paragraph_count: 6,
      page_count_hint: 3,
      created_at: '2026-01-05T09:12:00Z',
      warnings: [],
    },
    {
      template_id: 'builtin_plain',
      name: '空白模板（无封皮）',
      source_path: null,
      styles: [
        { style_id: 'Normal', name: '正文', type: 'paragraph', font: 'Calibri', size_pt: 11 },
      ],
      style_map: defaultStyleMap(),
      has_numbering: false,
      has_theme: false,
      has_cover: false,
      cover_paragraph_count: 0,
      page_count_hint: 1,
      created_at: '2026-01-05T09:12:00Z',
      warnings: ['该模板没有封皮节，封皮字段将被忽略'],
    },
  ]
}

// ---------------------------------------------------------------------------
// Style mapping mock data
// ---------------------------------------------------------------------------

const STYLES_DB: (StyleEntry & { style_id: string })[] = [
  { style_id: '1', name: 'heading 1', type: 'paragraph', font: 'Times New Roman', size_pt: 16, color: null, bold: true, italic: null, line_spacing: null, alignment: null, role: 'unused' as StyleRole },
  { style_id: '2', name: 'heading 2', type: 'paragraph', font: 'Times New Roman', size_pt: 14, color: null, bold: true, italic: null, line_spacing: null, alignment: null, role: 'unused' as StyleRole },
  { style_id: 'a', name: 'Normal', type: 'paragraph', font: '宋体', size_pt: 12, color: '000000', bold: null, italic: null, line_spacing: '259', alignment: 'both', role: 'unused' as StyleRole },
  { style_id: 'af3', name: 'Table Grid', type: 'table', font: null, size_pt: null, color: null, bold: null, italic: null, line_spacing: null, alignment: null, role: 'unused' as StyleRole },
  { style_id: 'af0', name: 'Title', type: 'paragraph', font: '黑体', size_pt: 22, color: '333333', bold: true, italic: null, line_spacing: null, alignment: 'center', role: 'unused' as StyleRole },
  { style_id: 'af7', name: 'List Paragraph', type: 'paragraph', font: '宋体', size_pt: 12, color: null, bold: null, italic: null, line_spacing: '360', alignment: null, role: 'unused' as StyleRole },
]

const styleMapStore = new Map<string, StyleMap>()

const coverOverrideStore = new Map<
  string,
  Array<{ find: string; replace: string | null; mode: string }>
>()

function inferRole(styleId: string, styleMap: StyleMap): StyleRole {
  for (const [key, val] of Object.entries(styleMap.headings)) {
    if (val === styleId) return `heading${key}` as StyleRole
  }
  if (styleMap.paragraph === styleId) return 'paragraph'
  if (styleMap.list_ordered === styleId) return 'list_ordered'
  if (styleMap.list_bullet === styleId) return 'list_bullet'
  if (styleMap.quote === styleId) return 'quote'
  if (styleMap.code === styleId) return 'code'
  if (styleMap.caption === styleId) return 'caption'
  if (styleMap.table === styleId) return 'table'
  if (styleMap.title === styleId) return 'title'
  return 'unused'
}

interface MockJob {
  info: JobInfo
  markdown: string
  destroyed: boolean
}

export function createMockApi(): DocXForgeApi {
  const templates = seedTemplates()
  const jobs = new Map<string, MockJob>()
  let jobSeq = 0

  function newId(prefix: string): string {
    jobSeq += 1
    return `${prefix}_${Date.now().toString(36)}${jobSeq.toString(36)}`
  }

  /** Applies TTL expiry lazily, mirroring the sandbox reaper. */
  function syncExpiry(job: MockJob): JobInfo {
    if (job.destroyed || !job.info.expires_at) {
      return job.info
    }
    if (Date.parse(job.info.expires_at) <= Date.now()) {
      job.destroyed = true
      job.info = {
        ...job.info,
        state: 'destroyed',
        destroyed_at: new Date().toISOString(),
      }
    }
    return job.info
  }

  function requireJob(jobId: string): MockJob {
    const job = jobs.get(jobId)
    if (!job) {
      throw new ApiError(
        { code: 'job_not_found', message: '任务不存在或沙箱已被销毁。', detail: jobId },
        404,
      )
    }
    return job
  }

  return {
    mode: 'mock',

    async health() {
      await delay(120)
      return {
        status: 'degraded',
        version: '0.1.0-mock',
        officecli_available: false,
        officecli_version: null,
        officecli_path: null,
        sandbox_root: '/tmp/docxforge-mock',
        sandbox_is_memory_backed: false,
        job_ttl_seconds: TTL_SECONDS,
      }
    },

    async listTemplates() {
      await delay(160)
      return templates.map((item) => ({ ...item }))
    },

    async uploadTemplate(file: File, name?: string) {
      await delay(LATENCY_MS)
      if (!file.name.toLowerCase().endsWith('.docx')) {
        throw new ApiError(
          { code: 'template_error', message: '只接受 .docx 模板文件。', detail: file.name },
          400,
        )
      }
      const info: TemplateInfo = {
        template_id: newId('tpl'),
        name: name?.trim() || file.name.replace(/\.docx$/i, ''),
        source_path: null,
        styles: [
          { style_id: 'Heading1', name: '标题 1', type: 'paragraph' },
          { style_id: 'Normal', name: '正文', type: 'paragraph' },
        ],
        style_map: defaultStyleMap(),
        has_numbering: true,
        has_theme: true,
        has_cover: true,
        cover_paragraph_count: 5,
        page_count_hint: null,
        created_at: new Date().toISOString(),
        warnings: ['演示模式：模板未真正解析，样式为占位数据'],
      }
      templates.push(info)
      return { ...info }
    },

    async deleteTemplate(templateId: string) {
      await delay(160)
      const index = templates.findIndex((item) => item.template_id === templateId)
      if (index === -1) {
        throw new ApiError(
          { code: 'template_not_found', message: '模板不存在。', detail: templateId },
          404,
        )
      }
      templates.splice(index, 1)
    },

    async getTemplateStyles(templateId: string) {
      await delay(160)
      const info = templates.find((item) => item.template_id === templateId)
      if (!info) {
        throw new ApiError(
          { code: 'template_not_found', message: '模板不存在。', detail: templateId },
          404,
        )
      }
      const styleMap = styleMapStore.get(templateId) ?? info.style_map
      const styles = STYLES_DB.map((s) => ({
        ...s,
        role: inferRole(s.style_id, styleMap),
      }))
      return { styles, style_map: styleMap } as TemplateStylesResponse
    },

    async saveStyleMap(templateId: string, styleMap: StyleMap) {
      await delay(200)
      const info = templates.find((item) => item.template_id === templateId)
      if (!info) {
        throw new ApiError(
          { code: 'template_not_found', message: '模板不存在。', detail: templateId },
          404,
        )
      }
      styleMapStore.set(templateId, styleMap)
    },

    async getTemplatePreview(templateId: string) {
      await delay(200)
      const info = templates.find((item) => item.template_id === templateId)
      if (!info) {
        throw new ApiError(
          { code: 'template_not_found', message: '模板不存在。', detail: templateId },
          404,
        )
      }
      const overrides = coverOverrideStore.get(templateId) ?? []
      return {
        cover: [
          { type: 'paragraph', text: '可行性分析报告', style: 'First Paragraph' },
          ...(overrides.length > 0 ? [] : []),
          {
            type: 'table',
            rows: [
              ['项目名称', '便携心电图系统', '项目编号', 'YLHX001'],
              ['项目来源', '开发任务', '版本', 'V1'],
            ],
          },
          { type: 'paragraph', text: '结论：', style: 'Body Text' },
        ],
        headings: STYLES_DB.filter((s) => /^heading/.test(s.style_id)).map((s, i) => ({
          level: i + 1,
          name: s.name,
          font: s.font,
          size_pt: s.size_pt,
          color: s.color,
          bold: s.bold,
          italic: s.italic,
          sample: `${'一二三四五六'[i]}、标题示例`,
        })),
        header_text: '示例页眉：项目名称',
        footer_text: null,
        overrides,
      }
    },

    async saveCoverOverrides(templateId: string, overrides: Array<{ find: string; replace: string | null; mode: string }>) {
      await delay(200)
      const info = templates.find((item) => item.template_id === templateId)
      if (!info) {
        throw new ApiError(
          { code: 'template_not_found', message: '模板不存在。', detail: templateId },
          404,
        )
      }
      coverOverrideStore.set(templateId, overrides)
    },

    async render(request: RenderRequest) {
      await delay(LATENCY_MS + Math.min(900, request.markdown.length / 12))
      if (!request.markdown.trim()) {
        throw new ApiError(
          { code: 'markdown_parse_error', message: 'Markdown 内容为空，无法渲染。', detail: null },
          400,
        )
      }
      const now = Date.now()
      const jobId = newId('job')
      const stem = request.filename?.trim() || request.doc_title?.trim() || 'docxforge'
      const filename = `${stem.replace(/\.docx$/i, '')}.docx`
      const warnings = ['演示模式：文档由前端 mock 生成，未经过 OfficeCLI 渲染']
      if (request.options.fast_markdown) {
        warnings.push('快速模式为有损渲染：链接与图片会降级为纯文本')
      }
      const info: JobInfo = {
        job_id: jobId,
        state: 'ready',
        filename,
        created_at: new Date(now).toISOString(),
        expires_at: new Date(now + TTL_SECONDS * 1000).toISOString(),
        destroyed_at: null,
        ttl_seconds: TTL_SECONDS,
        elapsed_ms: 480 + Math.round(request.markdown.length / 8),
        warnings,
        error: null,
      }
      jobs.set(jobId, { info, markdown: request.markdown, destroyed: false })
      return {
        job_id: jobId,
        filename,
        download_url: `/api/jobs/${jobId}/download`,
        elapsed_ms: info.elapsed_ms ?? 0,
        expires_at: info.expires_at,
        ttl_seconds: TTL_SECONDS,
        warnings,
      } satisfies RenderResponse
    },

    async getJob(jobId: string) {
      await delay(80)
      return { ...syncExpiry(requireJob(jobId)) }
    },

    async downloadJob(jobId: string) {
      await delay(200)
      const job = requireJob(jobId)
      const info = syncExpiry(job)
      if (info.state === 'destroyed') {
        throw new ApiError(
          { code: 'job_expired', message: '沙箱已销毁，文件不可再下载。', detail: jobId },
          410,
        )
      }
      const banner = [
        'DocXForge 演示模式输出（非真实 .docx）',
        `任务 ID: ${jobId}`,
        `文件名: ${info.filename ?? ''}`,
        '',
        '--- Markdown 源文 ---',
        '',
      ].join('\n')
      return new Blob([banner, job.markdown], { type: MOCK_BLOB_TYPE })
    },

    async destroyJob(jobId: string) {
      await delay(200)
      const job = requireJob(jobId)
      const bytes = new TextEncoder().encode(job.markdown).length
      const alreadyGone = job.destroyed
      job.destroyed = true
      job.info = {
        ...job.info,
        state: 'destroyed',
        destroyed_at: job.info.destroyed_at ?? new Date().toISOString(),
      }
      return {
        job_id: jobId,
        destroyed: true,
        files_shredded: alreadyGone ? 0 : 1,
        bytes_shredded: alreadyGone ? 0 : bytes,
        sandbox_path: `/tmp/docxforge-mock/${jobId}`,
        sandbox_exists_after: false,
        destroyed_at: job.info.destroyed_at ?? null,
      } satisfies DestroyReport
    },
  }
}
