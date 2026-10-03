import { onUnmounted, ref, watch, type Ref } from 'vue'
import type { WsMessage } from '@/api/wsTypes'

export interface StreamWsState {
  connected: Ref<boolean>
  lastFrame: Ref<string | null>
  stats: Ref<{
    total: number
    per_line: Record<string, Record<string, number>>
    fps: number
    active: number
  } | null>
  error: Ref<string | null>
}

export function useStreamWs(
  streamId: Ref<string | null>,
  options?: { frameFps?: number },
): StreamWsState {
  const connected = ref(false)
  const lastFrame = ref<string | null>(null)
  const stats = ref<StreamWsState['stats']['value']>(null)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null
  let frameTimer: number | null = null
  const frameInterval = 1000 / (options?.frameFps ?? 10)

  function connect(id: string) {
    disconnect()
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${location.host}/ws/streams/${id}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      error.value = null
    }

    ws.onmessage = (ev) => {
      let msg: WsMessage
      try {
        msg = JSON.parse(ev.data)
      } catch {
        return
      }

      if (msg.type === 'frame') {
        // передний throttle: не чаще frameFps, чтобы не копить буфер
        if (frameTimer === null) {
          lastFrame.value = `data:image/jpeg;base64,${msg.jpeg_b64}`
          frameTimer = window.setTimeout(() => {
            frameTimer = null
          }, frameInterval)
        }
      } else if (msg.type === 'stats') {
        stats.value = {
          total: msg.total,
          per_line: msg.per_line,
          fps: msg.fps,
          active: msg.active,
        }
      } else if (msg.type === 'status') {
        if (msg.status === 'stopped' || msg.status === 'error') {
          connected.value = false
        }
      } else if (msg.type === 'error') {
        error.value = msg.message
      }
      // ping — игнорируем, соединение живое
    }

    ws.onclose = () => {
      connected.value = false
      // авто-reconnect, только если id не сменился
      if (streamId.value === id) {
        reconnectTimer = window.setTimeout(() => connect(id), 3000)
      }
    }

    ws.onerror = () => {
      error.value = 'Ошибка WebSocket-соединения'
    }
  }

  function disconnect() {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (frameTimer !== null) {
      window.clearTimeout(frameTimer)
      frameTimer = null
    }
    if (ws) {
      ws.onclose = null // не запускать реконнект вручную
      ws.close()
      ws = null
    }
    connected.value = false
  }

  watch(
    streamId,
    (id) => {
      if (id) connect(id)
      else disconnect()
    },
    { immediate: true },
  )

  onUnmounted(disconnect)

  return { connected, lastFrame, stats, error }
}
