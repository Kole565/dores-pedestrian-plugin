import { api } from './client'
import type {
  FrameSourceKind,
  LinesConfig,
  LinesConfigCreate,
  LinesConfigListResponse,
} from './types'

export async function listLines(): Promise<LinesConfig[]> {
  const { data } = await api.get<LinesConfigListResponse>('/lines')
  return data.configs
}

export async function getLines(id: string): Promise<LinesConfig> {
  const { data } = await api.get<LinesConfig>(`/lines/${id}`)
  return data
}

export async function createLines(
  payload: LinesConfigCreate,
): Promise<LinesConfig> {
  const { data } = await api.post<LinesConfig>('/lines', payload)
  return data
}

export async function updateLines(
  id: string,
  payload: LinesConfigCreate,
): Promise<LinesConfig> {
  const { data } = await api.put<LinesConfig>(`/lines/${id}`, payload)
  return data
}

export async function deleteLines(id: string): Promise<void> {
  await api.delete(`/lines/${id}`)
}

export function frameUrl(params: {
  source: FrameSourceKind
  id: string
  tSec?: number
}): string {
  const q = new URLSearchParams({
    source: params.source,
    id: params.id,
  })
  if (params.tSec != null) q.set('t_sec', String(params.tSec))
  return `/api/lines/frame?${q.toString()}`
}
