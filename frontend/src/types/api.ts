/**
 * TypeScript mirrors of `backend/docxforge/models.py`.
 *
 * Field names are part of the cross-module contract (docs/CONTRACTS.md section
 * 3) and must stay byte-identical to the pydantic models. Optional pydantic
 * fields (`X | None`) are modelled as `X | null` and marked optional, because
 * most request models declare defaults. Request payloads use
 * `extra="forbid"` server-side, so never add fields that do not exist here.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type JobState = 'pending' | 'running' | 'ready' | 'destroyed' | 'failed'

export type HealthStatus = 'ok' | 'degraded'

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

export interface StyleMap {
  /** Heading level (1-6) -> Word style id. Serialized with numeric-string keys. */
  headings: Record<string, string>
  paragraph: string
  list_ordered: string
  list_bullet: string
  quote: string
  code: string
  caption: string
  table: string
  title: string
}

/** `StyleInfo` allows extra keys server-side (`extra="allow"`). */
export interface StyleInfo {
  style_id: string
  name?: string | null
  type?: string | null
  based_on?: string | null
  font?: string | null
  size_pt?: number | null
  [key: string]: unknown
}

export interface TemplateInfo {
  template_id: string
  name: string
  source_path?: string | null
  styles: StyleInfo[]
  style_map: StyleMap
  has_numbering: boolean
  has_theme: boolean
  has_cover: boolean
  cover_paragraph_count: number
  page_count_hint?: number | null
  created_at?: string | null
  warnings: string[]
}

export interface TemplateListResponse {
  templates: TemplateInfo[]
}

// ---------------------------------------------------------------------------
// Style mapping
// ---------------------------------------------------------------------------

export type StyleRole =
  | 'unused'
  | 'heading1' | 'heading2' | 'heading3'
  | 'heading4' | 'heading5' | 'heading6'
  | 'paragraph' | 'list_ordered' | 'list_bullet'
  | 'quote' | 'code' | 'caption' | 'table' | 'title'

export const ROLE_LABELS: Record<StyleRole, string> = {
  unused: '不映射',
  heading1: '标题 1',
  heading2: '标题 2',
  heading3: '标题 3',
  heading4: '标题 4',
  heading5: '标题 5',
  heading6: '标题 6',
  paragraph: '正文',
  list_ordered: '有序列表',
  list_bullet: '无序列表',
  quote: '引用',
  code: '代码',
  caption: '题注',
  table: '表格',
  title: '标题页',
}

export const ROLE_ORDER: StyleRole[] = [
  'heading1', 'heading2', 'heading3', 'heading4', 'heading5', 'heading6',
  'paragraph', 'list_ordered', 'list_bullet', 'quote', 'code',
  'caption', 'table', 'title', 'unused',
]

export interface StyleEntry {
  style_id: string
  name: string | null
  type: string | null
  font: string | null
  size_pt: number | null
  color: string | null
  bold: boolean | null
  italic: boolean | null
  line_spacing: string | null
  alignment: string | null
  role: StyleRole
}

export interface TemplateStylesResponse {
  styles: StyleEntry[]
  style_map: StyleMap
}

// ---------------------------------------------------------------------------
// Render request / response
// ---------------------------------------------------------------------------

export interface TocOptions {
  enabled: boolean
  levels: string
  title: string | null
  hyperlinks: boolean
  page_numbers: boolean
  page_break_after: boolean
}

export interface CoverOptions {
  enabled: boolean
  /** `find -> replace` pairs applied to the template cover section. */
  replacements: Record<string, string>
  page_break_after: boolean
}

export interface HeaderFooterOptions {
  header_text: string | null
  footer_text: string | null
  page_numbers: boolean
  different_first_page: boolean
}

export interface RenderOptions {
  fast_markdown: boolean
  update_fields: boolean
  validate_output: boolean
  use_resident: boolean
}

export interface RenderRequest {
  markdown: string
  doc_title?: string | null
  template_id?: string | null
  toc: TocOptions
  cover: CoverOptions
  header_footer: HeaderFooterOptions
  options: RenderOptions
  /** Output filename stem; the pipeline always writes `.docx`. */
  filename?: string | null
  base_dir?: string | null
}

export interface RenderResponse {
  job_id: string
  filename: string
  download_url: string
  elapsed_ms: number
  expires_at?: string | null
  ttl_seconds: number
  warnings: string[]
}

// ---------------------------------------------------------------------------
// Jobs / sandbox
// ---------------------------------------------------------------------------

export interface JobInfo {
  job_id: string
  state: JobState
  filename?: string | null
  created_at: string
  expires_at?: string | null
  destroyed_at?: string | null
  ttl_seconds: number
  elapsed_ms?: number | null
  warnings: string[]
  error?: string | null
}

/** Evidence for DoD #3 - zero data remnants. */
export interface DestroyReport {
  job_id: string
  destroyed: boolean
  files_shredded: number
  bytes_shredded: number
  sandbox_path?: string | null
  sandbox_exists_after: boolean
  destroyed_at?: string | null
}

// ---------------------------------------------------------------------------
// Envelopes
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: HealthStatus
  version: string
  officecli_available: boolean
  officecli_version?: string | null
  officecli_path?: string | null
  sandbox_root: string
  sandbox_is_memory_backed: boolean
  job_ttl_seconds: number
}

export interface ErrorResponse {
  code: string
  message: string
  detail?: string | null
}

// ---------------------------------------------------------------------------
// Defaults mirroring the pydantic field defaults
// ---------------------------------------------------------------------------

export function defaultTocOptions(): TocOptions {
  return {
    enabled: true,
    levels: '1-3',
    title: '目录',
    hyperlinks: true,
    page_numbers: true,
    page_break_after: true,
  }
}

export function defaultCoverOptions(): CoverOptions {
  return { enabled: true, replacements: {}, page_break_after: true }
}

export function defaultHeaderFooterOptions(): HeaderFooterOptions {
  return {
    header_text: null,
    footer_text: null,
    page_numbers: true,
    different_first_page: true,
  }
}

export function defaultRenderOptions(): RenderOptions {
  return {
    fast_markdown: false,
    update_fields: true,
    validate_output: false,
    use_resident: true,
  }
}
