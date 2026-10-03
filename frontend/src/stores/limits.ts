import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getLimits } from '@/api/lines'
import { extractError } from '@/api/client'
import type { LimitsResponse } from '@/api/types'

export const useLimitsStore = defineStore('limits', () => {
  const limits = ref<LimitsResponse | null>(null)
  const error = ref<string | null>(null)
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      limits.value = await getLimits()
      loaded.value = true
    } catch (e) {
      error.value = extractError(e)
    }
  }

  return { limits, error, loaded, load }
})
