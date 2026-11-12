import type {
  CreateDesignRequest,
  Design,
  DesignDetail,
  DesignListResponse,
  DesignVersionSummary,
  EntityId,
  SaveDesignVersionRequest,
  UpdateDesignRequest,
} from '@/types/api'
import { api } from './apiClient'
import { endpoints } from './endpoints'

export interface ListDesignsQuery {
  page?: number
  page_size?: number
  search?: string
  sort?: string
}

export const designsService = {
  list: (query: ListDesignsQuery = {}, signal?: AbortSignal) =>
    api.get<DesignListResponse>(endpoints.designs.list, { query: { ...query }, signal }),

  detail: (designId: EntityId, signal?: AbortSignal) =>
    api.get<DesignDetail>(endpoints.designs.detail(designId), { signal }),

  create: (body: CreateDesignRequest, signal?: AbortSignal) =>
    api.post<Design>(endpoints.designs.create, body, { signal }),

  update: (designId: EntityId, body: UpdateDesignRequest, signal?: AbortSignal) =>
    api.patch<Design>(endpoints.designs.update(designId), body, { signal }),

  remove: (designId: EntityId) => api.delete(endpoints.designs.remove(designId)),

  /** An identical layout returns the current version instead of creating a new number. */
  saveVersion: (designId: EntityId, body: SaveDesignVersionRequest, signal?: AbortSignal) =>
    api.post<DesignVersionSummary>(endpoints.designs.versions(designId), body, { signal }),
}
