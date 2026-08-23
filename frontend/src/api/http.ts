import { ApiError, type DocXForgeApi } from '@/api/client'
import type {
  DestroyReport,
  ErrorResponse,
  HealthResponse,
  JobInfo,
  RenderRequest,
  RenderResponse,
  StyleMap,
  TemplateInfo,
  TemplateListResponse,
  TemplateStylesResponse,
} from '@/types/api'

const DEFAULT_BASE = '/api'

function isErrorResponse(value: unknown): value is ErrorResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ErrorResponse).code === 'string' &&
    typeof (value as ErrorResponse).message === 'string'
  )
}

/** Turns any non-2xx response into an `ApiError` carrying the server envelope. */
async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (isErrorResponse(body)) {
    return new ApiError(body, response.status)
  }
  // FastAPI's own validation errors use {"detail": ...}.
  const detail =
    typeof body === 'object' && body !== null && 'detail' in body
      ? JSON.stringify((body as Record<string, unknown>).detail)
      : null
  return new ApiError(
    {
      code: `http_${response.status}`,
      message: `请求失败（HTTP ${response.status}）`,
      detail,
    },
    response.status,
  )
}

export function createHttpApi(base: string = DEFAULT_BASE): DocXForgeApi {
  const root = base.replace(/\/+$/, '')

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response
    try {
      response = await fetch(`${root}${path}`, init)
    } catch (error) {
      throw ApiError.network(
        '无法连接后端服务，请确认服务已在 8000 端口启动。',
        error instanceof Error ? error.message : String(error),
      )
    }
    if (!response.ok) {
      throw await toApiError(response)
    }
    if (response.status === 204) {
      return undefined as T
    }
    try {
      return (await response.json()) as T
    } catch (error) {
      throw ApiError.network(
        '后端返回了无法解析的响应。',
        error instanceof Error ? error.message : String(error),
      )
    }
  }

  return {
    mode: 'live',

    async health(signal?: AbortSignal) {
      return request<HealthResponse>('/health', { signal })
    },

    async listTemplates() {
      const payload = await request<TemplateListResponse>('/templates')
      return payload.templates ?? []
    },

    async uploadTemplate(file: File, name?: string) {
      const form = new FormData()
      form.append('file', file)
      if (name) {
        form.append('name', name)
      }
      return request<TemplateInfo>('/templates', { method: 'POST', body: form })
    },

    async deleteTemplate(templateId: string) {
      await request<void>(`/templates/${encodeURIComponent(templateId)}`, {
        method: 'DELETE',
      })
    },

    async getTemplateStyles(templateId: string) {
      return request<TemplateStylesResponse>(
        `/templates/${encodeURIComponent(templateId)}/styles`,
      )
    },

    async saveStyleMap(templateId: string, styleMap: StyleMap) {
      await request<void>(
        `/templates/${encodeURIComponent(templateId)}/style-map`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(styleMap),
        },
      )
    },

    async getTemplatePreview(templateId: string) {
      return request<Record<string, unknown>>(
        `/templates/${encodeURIComponent(templateId)}/preview`,
      )
    },

    async saveCoverOverrides(templateId: string, overrides: Array<{ find: string; replace: string | null; mode: string }>) {
      await request<void>(
        `/templates/${encodeURIComponent(templateId)}/cover-overrides`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(overrides),
        },
      )
    },

    async render(payload: RenderRequest) {
      return request<RenderResponse>('/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    },

    async getJob(jobId: string) {
      return request<JobInfo>(`/jobs/${encodeURIComponent(jobId)}`)
    },

    async downloadJob(jobId: string) {
      const url = `${root}/jobs/${encodeURIComponent(jobId)}/download`
      let response: Response
      try {
        response = await fetch(url)
      } catch (error) {
        throw ApiError.network(
          '下载失败：无法连接后端服务。',
          error instanceof Error ? error.message : String(error),
        )
      }
      if (!response.ok) {
        throw await toApiError(response)
      }
      return response.blob()
    },

    async destroyJob(jobId: string) {
      return request<DestroyReport>(`/jobs/${encodeURIComponent(jobId)}`, {
        method: 'DELETE',
      })
    },
  }
}
