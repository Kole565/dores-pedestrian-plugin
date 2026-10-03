export type JobStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'cancelled'

export interface JobProgress {
  frames_done: number
  frames_total: number
  fps_avg: number
}

export interface JobResult {
  output_video?: string | null
  report_json?: string | null
  events_csv?: string | null
  intensity_png?: string | null
}

export interface JobInfo {
  id: string
  status: JobStatus
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  input_filename: string
  lines_config_id?: string | null
  progress: JobProgress
  result?: JobResult | null
  error_message?: string | null
}

export interface JobListResponse {
  jobs: JobInfo[]
}

export interface LimitsResponse {
  max_upload_bytes: number
  allowed_video_ext: string[]
}

export interface LinesConfig {
  id: string
  name: string
  lines: Array<{
    line_id: string
    coords: [number, number, number, number]
    direction_pos_to_neg: string
    direction_neg_to_pos: string
    use_point: string
  }>
  created_at: string
  updated_at: string
}

export interface LinesConfigListResponse {
  configs: LinesConfig[]
}

// ---------------------------------------------------------------------------
// Streams
// ---------------------------------------------------------------------------

export type StreamStatus = 'starting' | 'running' | 'stopped' | 'error'

export interface StreamStats {
  total: number
  per_line: Record<string, Record<string, number>>
  fps: number
  active_tracks: number
  frames_processed: number
}

export interface StreamInfo {
  id: string
  status: StreamStatus
  rtsp_url_masked: string
  lines_config_id?: string | null
  created_at: string
  started_at?: string | null
  stopped_at?: string | null
  last_frame_at?: string | null
  stats: StreamStats
  error_message?: string | null
}

export interface StreamListResponse {
  streams: StreamInfo[]
}

export interface StreamCreate {
  rtsp_url: string
  lines_config_id?: string | null
  lines_config?: Record<string, unknown> | null
}
