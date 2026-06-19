/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the WaitCost API. Empty = same-origin (single-service deploy);
   *  "/api" = Vite dev proxy. Defaults are handled in api/client.ts. */
  readonly VITE_API_BASE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
