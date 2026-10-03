import { api } from './client'
import type { JobInfo, JobListResponse } from './types'

export interface CreateJobParams {
  file: File
  linesConfigId?: string | null
  onUploadProgress?: (loaded: number, total: number) => void
}

export async function createJob(params: CreateJobParams): Promise<JobInfo> {
  const fd = new FormData()
  fd.append('file', params.file)
  if (params.linesConfigId) fd.append('lines_config_id', params.linesConfigId)

  const { data } = await api.post<JobInfo>('/jobs', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (params.onUploadProgress && e.total) {
        params.onUploadProgress(e.loaded, e.total)
      }
    },
    timeout: 0,
  })
  return data
}

export async function listJobs(): Promise<JobInfo[]> {
  const { data } = await api.get<JobListResponse>('/jobs')
  return data.jobs
}

export async function getJob(id: string): Promise<JobInfo> {
  const { data } = await api.get<JobInfo>(`/jobs/${id}`)
  return data
}

export function jobResultUrl(id: string): string {
  return `/api/jobs/${id}/result`
}

export function jobFileUrl(id: string, name: string): string {
  return `/api/jobs/${id}/files/${name}`
}
