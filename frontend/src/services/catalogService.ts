import type { LayoutTemplate, ListResponse, PlannerCatalog } from '@/types/api'
import { api } from './apiClient'
import { endpoints } from './endpoints'

export const catalogService = {
  planner: (signal?: AbortSignal) =>
    api.get<PlannerCatalog>(endpoints.catalog.planner, { auth: false, signal }),
  templates: (signal?: AbortSignal) =>
    api.get<ListResponse<LayoutTemplate>>(endpoints.templates.list, { auth: false, signal }),
}
