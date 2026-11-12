import type { EntityId } from '@/types/api'

/**
 * Every backend path from docs/API_CONTRACT.md, relative to the API base (`/api/v1`).
 * Never write an endpoint string anywhere else. Checked against the backend's OpenAPI
 * routes on 2026-11-12 (Phase 3).
 */
const id = (value: EntityId) => encodeURIComponent(String(value))

export const endpoints = {
  auth: {
    register: '/auth/register', // POST  · public · CSRF header · sets refresh cookie
    login: '/auth/login', // POST  · public · CSRF header · sets refresh cookie
    google: '/auth/google', // POST  · public · CSRF header · { id_token } · sets refresh cookie
    refresh: '/auth/refresh', // POST  · refresh cookie + CSRF header → new access token (cookie rotated)
    logout: '/auth/logout', // POST  · refresh cookie + CSRF header → revoked, cookie cleared
    me: '/auth/me', // GET   · bearer
    forgotPassword: '/auth/forgot-password', // POST · { email }
    verifyResetCode: '/auth/forgot-password/verify', // POST · { email, otp } → { reset_token }
    resetPassword: '/auth/forgot-password/reset', // POST · { reset_token, new_password }
  },
  catalog: {
    planner: '/catalog', // GET · public · sizes, finishes, mounts, paints, layouts, rules
    frameMaterials: '/frame-materials', // GET · public · ?category&available_only
    frames: '/frames', // GET · public · ?material_id&color&min_width&max_width
  },
  templates: {
    list: '/templates', // GET · public · ?category&min_frames&max_frames
  },
  photos: {
    list: '/photos', // GET    · bearer · ?page&page_size
    upload: '/photos/upload', // POST   · bearer · multipart `file`
    thumbnail: (photoId: EntityId) => `/photos/${id(photoId)}/thumbnail`, // GET · signed URL
    preview: (photoId: EntityId) => `/photos/${id(photoId)}/preview`, // GET · signed URL
    remove: (photoId: EntityId) => `/photos/${id(photoId)}`, // DELETE · bearer → 204
  },
  geometry: {
    validateLayout: '/geometry/validate-layout', // POST · optional auth
    generateLayout: '/geometry/generate-layout', // POST · optional auth
    regenerate: '/geometry/regenerate', // POST · optional auth
    redesign: '/geometry/redesign', // POST · optional auth
  },
  designs: {
    list: '/designs', // GET    · bearer · ?page&page_size&status&search&sort
    create: '/designs', // POST   · bearer
    detail: (designId: EntityId) => `/designs/${id(designId)}`, // GET    · bearer
    update: (designId: EntityId) => `/designs/${id(designId)}`, // PATCH  · bearer
    remove: (designId: EntityId) => `/designs/${id(designId)}`, // DELETE · bearer → 204
    versions: (designId: EntityId) => `/designs/${id(designId)}/versions`, // POST · bearer
  },
  quotes: {
    prepare: '/quotes/prepare', // POST · bearer · multipart `file` + `design_data`
    detail: (quoteId: string) => `/quotes/${id(quoteId)}`, // GET · bearer · owner only
    share: (token: string) => `/quotes/share/${id(token)}`, // GET · public · HTML or JSON
    sharePreview: (token: string) => `/quotes/share/${id(token)}/preview`, // GET · public
  },
} as const
