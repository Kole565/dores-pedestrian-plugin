import { api } from './client'
import type { StreamCreate, StreamInfo, StreamListResponse } from './types'

export async function createStream(payload: StreamCreate): Promise<StreamInfo> {
  const { data } = await api.post<StreamInfo>('/streams', payload)
  return data
}

export async function listStreams(): Promise<StreamInfo[]> {
  const { data } = await api.get<StreamListResponse>('/streams')
  return data.streams
}

export async function getStream(id: string): Promise<StreamInfo> {
  const { data } = await api.get<StreamInfo>(`/streams/${id}`)
  return data
}

export async function stopStream(id: string): Promise<void> {
  await api.delete(`/streams/${id}`)
}

export function snapshotUrl(id: string): string {
  return `/api/streams/${id}/snapshot.jpg`
}
