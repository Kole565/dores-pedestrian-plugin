import { api } from './client'
import type { UploadInfo } from './types'

export async function createUpload(
  file: File,
  onProgress?: (loaded: number, total: number) => void,
): Promise<UploadInfo> {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post<UploadInfo>('/uploads', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(e.loaded, e.total)
    },
  })
  return data
}

export async function deleteUpload(id: string): Promise<void> {
  await api.delete(`/uploads/${id}`)
}
