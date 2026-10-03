import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { listJobs } from '@/api/jobs'
import { extractError } from '@/api/client'
import type { JobInfo } from '@/api/types'

export const useJobsStore = defineStore('jobs', () => {
  const jobs = ref<JobInfo[]>([])
  const loading = ref(true)
  const error = ref<string | null>(null)

  const hasActive = computed(() =>
    jobs.value.some((j) => j.status === 'running' || j.status === 'pending')
  )

  async function refresh() {
    try {
      jobs.value = await listJobs()
      error.value = null
    } catch (e) {
      error.value = extractError(e)
    } finally {
      loading.value = false
    }
  }

  return { jobs, loading, error, hasActive, refresh }
})
