import type {
  DestroyReport,
  ErrorResponse,
  HealthResponse,
  JobInfo,
  RenderRequest,
  RenderResponse,
  StyleMap,
  TemplateInfo,
  TemplateStylesResponse,
} from '@/types/api'

export type ApiMode = 'live' | 'mock'

/**
 * Normalized failure carrying the backend `ErrorResponse` envelope.
 * Network/parse failures are wrapped with a synthetic code so callers always
 * have a stable `code` + human-readable Chinese `message`.
 */
export class ApiError extends Error {
  readonly code: string
  readonly detail: string | null
  readonly status: number | null

  constructor(payload: ErrorResponse, status: number | null = null) {
    super(payload.message)
    this.name = 'ApiError'
    this.code = payload.code
    this.detail = payload.detail ?? null
    this.status = status
  }

  static network(message: string, detail?: string): ApiError {
    return new ApiError({ code: 'network_error', message, detail: detail ?? null })
  }
}

/**
 * The single surface every screen talks to. Two implementations exist:
 * `createHttpApi` (real backend) and `createMockApi` (offline demo data).
 */
export interface DocXForgeApi {
  readonly mode: ApiMode
  health(signal?: AbortSignal): Promise<HealthResponse>
  listTemplates(): Promise<TemplateInfo[]>
  uploadTemplate(file: File, name?: string): Promise<TemplateInfo>
  deleteTemplate(templateId: string): Promise<void>
  getTemplateStyles(templateId: string): Promise<TemplateStylesResponse>
  saveStyleMap(templateId: string, styleMap: StyleMap): Promise<void>
  getTemplatePreview(templateId: string): Promise<Record<string, unknown>>
  saveCoverOverrides(
    templateId: string,
    overrides: Array<{ find: string; replace: string | null; mode: string }>,
  ): Promise<void>
  render(request: RenderRequest): Promise<RenderResponse>
  getJob(jobId: string): Promise<JobInfo>
  /** Fetches the generated docx as a blob so failures surface as `ApiError`. */
  downloadJob(jobId: string): Promise<Blob>
  destroyJob(jobId: string): Promise<DestroyReport>
}
