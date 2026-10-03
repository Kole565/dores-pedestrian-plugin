import { api } from './client'
import type { LimitsResponse } from './types'

export async function getLimits(): Promise<LimitsResponse> {
  const { data } = await api.get<LimitsResponse>('/config/limits')
  return data
}
