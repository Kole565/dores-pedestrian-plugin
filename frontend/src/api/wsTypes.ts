export type WsMessage =
  | { type: 'frame'; jpeg_b64: string; ts: number }
  | {
      type: 'stats'
      total: number
      per_line: Record<string, Record<string, number>>
      fps: number
      active: number
    }
  | { type: 'status'; status: string }
  | { type: 'error'; message: string }
  | { type: 'ping' }
