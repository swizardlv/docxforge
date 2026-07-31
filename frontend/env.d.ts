/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Force the mock API adapter, skipping backend probing. Set to "1"/"true". */
  readonly VITE_USE_MOCK_API?: string
  /** Base path of the HTTP API. Defaults to "/api" (proxied to :8000 in dev). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
