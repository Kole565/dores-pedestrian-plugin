import { api } from './client'
import type { LimitsResponse, LinesConfig, LinesConfigListResponse } from './types'

export async function listLines(): Promise<LinesConfig[]> {
  const { data } = await api.get<LinesConfigListResponse>('/lines')
  return data.configs
}

export async function getLimits(): Promise<LimitsResponse> {
  const { data } = await api.get<LimitsResponse>('/config/limits')
  return data
}
