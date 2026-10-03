<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useJobsStore } from '@/stores/jobs'
import { usePolling } from '@/composables/usePolling'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Spinner from '@/components/Spinner.vue'

const store = useJobsStore()
const { jobs, loading, error, hasActive } = storeToRefs(store)

usePolling(hasActive, () => store.refresh(), 2000)

onMounted(() => store.refresh())

const STATUS_LABEL: Record<string, string> = {
  pending: 'в очереди',
  running: 'выполняется',
  done: 'готово',
  failed: 'ошибка',
  cancelled: 'отменено',
}

function fmtDate(s: string): string {
  try {
    return new Date(s).toLocaleString('ru-RU')
  } catch {
    return s
  }
}

function progressPct(job: { progress: { frames_done: number; frames_total: number } }): number {
  return job.progress.frames_total > 0
    ? Math.round((100 * job.progress.frames_done) / job.progress.frames_total)
    : 0
}
</script>

<template>
  <div>
    <div class="row between" style="margin-bottom: 16px">
      <h1 style="margin: 0">Обзор</h1>
      <RouterLink to="/upload">
        <button class="primary">+ Загрузить видео</button>
      </RouterLink>
    </div>

    <ErrorBanner v-if="error" :message="error" />

    <div class="card">
      <h2>Offline-задачи</h2>

      <div v-if="loading" class="row">
        <Spinner /> <span class="muted">Загрузка…</span>
      </div>

      <div v-else-if="jobs.length === 0" class="empty">
        Пока нет ни одной задачи.
        <RouterLink to="/upload">Загрузите видео</RouterLink>.
      </div>

      <table v-else>
        <thead>
          <tr>
            <th>ID</th>
            <th>Файл</th>
            <th>Статус</th>
            <th>Прогресс</th>
            <th>Создано</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td class="mono">{{ job.id }}</td>
            <td>{{ job.input_filename }}</td>
            <td>
              <span class="badge" :class="job.status">
                {{ STATUS_LABEL[job.status] ?? job.status }}
              </span>
            </td>
            <td>
              <template v-if="job.status === 'running'">
                {{ progressPct(job) }}% ({{ job.progress.frames_done }}/{{ job.progress.frames_total }},
                {{ job.progress.fps_avg }} FPS)
              </template>
              <template v-else>—</template>
            </td>
            <td class="muted">{{ fmtDate(job.created_at) }}</td>
            <td>
              <RouterLink :to="`/jobs/${job.id}`">Открыть</RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
