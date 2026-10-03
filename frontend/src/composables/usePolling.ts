import { onUnmounted, watch, type Ref } from 'vue'

export function usePolling(
  condition: Ref<boolean>,
  callback: () => void | Promise<void>,
  intervalMs = 2000,
) {
  let timer: number | null = null

  function start() {
    stop()
    timer = window.setInterval(callback, intervalMs)
  }

  function stop() {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  }

  watch(
    condition,
    (active) => {
      if (active) start()
      else stop()
    },
    { immediate: true },
  )

  onUnmounted(stop)

  return { start, stop }
}
