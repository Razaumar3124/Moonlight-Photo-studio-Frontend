/**
 * TypeScript mirror of docs/API_CONTRACT.md (backend v1).
 * Import from here: `import type { User, LayoutTemplate } from '@/types/api'`.
 * When the contract changes, update these files in the same PR as docs/API_CONTRACT.md.
 */
export type * from './common'
export type * from './auth'
export type * from './catalog'
export type * from './photos'
export type * from './templates'
export type * from './geometry'
export type * from './pricing'
export type * from './designs'
export type * from './quotes'

export { PHOTO_UPLOAD_MIME_TYPES } from './photos'
