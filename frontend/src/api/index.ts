import type { DocXForgeApi } from '@/api/client'
import { createHttpApi } from '@/api/http'
import { createMockApi } from '@/api/mock'
import type { HealthResponse } from '@/types/api'

export { ApiError } from '@/api/client'
export type { ApiMode, DocXForgeApi } from '@/api/client'
export { MOCK_BLOB_TYPE } from '@/api/mock'

const PROBE_TIMEOUT_MS = 2500

function envFlag(value: string | undefined): boolean {
  if (!value) {
    return false
  }
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())
}

export function isMockForced(): boolean {
  return envFlag(import.meta.env.VITE_USE_MOCK_API)
}

export function apiBase(): string {
  return import.meta.env.VITE_API_BASE?.trim() || '/api'
}

export interface ResolvedApi {
  api: DocXForgeApi
  health: HealthResponse | null
  /** Why the mock adapter was selected, if it was. */
  fallbackReason: string | null
}

/**
 * Picks the adapter for this session: forced mock, live backend, or mock as an
 * automatic fallback when `GET /api/health` is unreachable.
 */
export async function resolveApi(): Promise<ResolvedApi> {
  if (isMockForced()) {
    const api = createMockApi()
    return { api, health: await api.health(), fallbackReason: '已通过 VITE_USE_MOCK_API 强制启用演示数据' }
  }

  const live = createHttpApi(apiBase())
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)
  try {
    const health = await live.health(controller.signal)
    return { api: live, health, fallbackReason: null }
  } catch (error) {
    const mock = createMockApi()
    return {
      api: mock,
      health: await mock.health(),
      fallbackReason: `后端 ${apiBase()}/health 不可达，已自动切换到演示数据（${
        error instanceof Error ? error.message : String(error)
      }）`,
    }
  } finally {
    clearTimeout(timer)
  }
}

export function createLiveApi(): DocXForgeApi {
  return createHttpApi(apiBase())
}
