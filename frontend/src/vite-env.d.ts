/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base incl. version prefix. Relative (`/api/v1`, uses dev proxy) or absolute (`https://api.example.com/api/v1`). */
  readonly VITE_API_BASE_URL?: string
  readonly VITE_GOOGLE_CLIENT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/* ---------- vite-imagetools query imports (see src/assets/index.ts) ---------- */

/** `?…&as=srcset` → a ready-to-use srcset string ("a.webp 480w, b.webp 960w"). */
declare module '*as=srcset' {
  const srcset: string
  export default srcset
}

/** `?w=…&format=webp` (single output) → URL of the generated file. */
declare module '*format=webp' {
  const src: string
  export default src
}
