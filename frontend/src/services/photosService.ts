import type { EntityId, Photo, PhotosListResponse, PhotoSummary } from '@/types/api'
import { api, uploadFile, type UploadOptions } from './apiClient'
import { endpoints } from './endpoints'

/** Largest page the API serves; the library is read page by page. */
const PAGE_SIZE = 100
/** A user's library is bounded by the upload rate limit; this is only a runaway guard. */
const MAX_PAGES = 10

export const photosService = {
  /** Every photo of the signed-in user (newest first), with fresh signed thumbnail/preview URLs. */
  async listAll(signal?: AbortSignal): Promise<PhotoSummary[]> {
    const all: PhotoSummary[] = []
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      const res = await api.get<PhotosListResponse>(endpoints.photos.list, {
        query: { page, page_size: PAGE_SIZE },
        signal,
      })
      all.push(...res.items)
      if (all.length >= res.total || res.items.length === 0) break
    }
    return all
  },

  upload: (file: File, options?: UploadOptions) =>
    uploadFile<Photo>(endpoints.photos.upload, file, file.name, options),

  /** 409 `PHOTO_IN_USE` while a saved design still uses the photo. */
  remove: (photoId: EntityId) => api.delete(endpoints.photos.remove(photoId)),
}
