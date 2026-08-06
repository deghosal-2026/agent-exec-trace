/**
 * Vite environment type declarations.
 *
 * Extends the global `ImportMeta` interface to provide type-safe access
 * to environment variables defined in `.env` files.
 *
 * ## Reference
 * The triple-slash directive includes Vite's built-in client types,
 * which add types for `import.meta.hot`, `import.meta.env.MODE`, etc.
 *
 * @see https://vitejs.dev/guide/env-and-mode
 */

/// <reference types="vite/client" />

/**
 * Custom environment variables available via `import.meta.env`.
 *
 * All variables must be prefixed with `VITE_` to be exposed to the client.
 */
interface ImportMetaEnv {
  /** Optional override for the API base URL (defaults to relative path). */
  readonly VITE_API_URL?: string;
}

/**
 * Augments the global `ImportMeta` interface with our custom env types.
 */
interface ImportMeta {
  readonly env: ImportMetaEnv;
}