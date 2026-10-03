<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getJob, jobFileUrl, jobResultUrl } from '@/api/jobs'
import { extractError } from '@/api/client'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Spinner from '@/components/Spinner.vue'
import type { JobInfo } from '@/api/types'

const props = defineProps<{ id: string }>()

const job = ref<JobInfo | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

let timer: number | null = null

const STATUS_LABEL: Record<string, string> = {
  pending: 'в очереди',
  running: 'выполняется',
  done: 'готово',
  failed: 'ошибка',
  cancelled: 'отменено',
}

const isTerminal = computed(() =>
  job.value?.status === 'done' ||
  job.value?.status === 'failed' ||
  job.value?.status === 'cancelled'
)

const progressPct = computed(() =>
  job.value && job.value.progress.frames_total > 0
    ? Math.round((100 * job.value.progress.frames_done) / job.value.progress.frames_total)
    : 0
)

async function tick() {
  try {
    job.value = await getJob(props.id)
    error.value = null
    loading.value = false
    if (!isTerminal.value) {
      timer = window.setTimeout(tick, 1500)
    }
  } catch (e) {
    error.value = extractError(e)
    loading.value = false
  }
}

onMounted(tick)
onUnmounted(() => {
  if (timer) window.clearTimeout(timer)
})
</script>

<template>
  <div>
    <div class="row between" style="margin-bottom: 16px">
      <h1 style="margin: 0">
        Задача <span class="mono">{{ id }}</span>
      </h1>
      <RouterLink to="/"><button>← К обзору</button></RouterLink>
    </div>

    <div v-if="loading" class="row">
      <Spinner /> <span class="muted">Загрузка…</span>
    </div>

    <ErrorBanner v-else-if="error" :message="error" />

    <template v-else-if="job">
      <div class="card">
        <div class="row between">
          <div>
            <div class="muted">Файл</div>
            <div>{{ job.input_filename }}</div>
          </div>
          <span class="badge" :class="job.status">
            {{ STATUS_LABEL[job.status] ?? job.status }}
          </span>
        </div>

        <template v-if="job.status === 'running'">
          <div class="progress" style="margin-top: 16px">
            <div class="bar" :style="{ width: `${progressPct}%` }"></div>
          </div>
          <div class="progress-meta">
            <span>
              Кадр {{ job.progress.frames_done }}
              <template v-if="job.progress.frames_total">/ {{ job.progress.frames_total }}</template>
            </span>
            <span>{{ job.progress.fps_avg }} FPS · {{ progressPct }}%</span>
          </div>
        </template>

        <div v-if="job.error_message" class="error-banner" style="margin-top: 16px; white-space: pre-wrap">
          {{ job.error_message }}
        </div>
      </div>

      <div v-if="job.status === 'done'" class="card">
        <h2>Результаты</h2>
        <div class="row" style="flex-wrap: wrap; gap: 12px">
          <a :href="jobResultUrl(job.id)">
            <button class="primary">Скачать ZIP</button>
          </a>
          <a :href="jobFileUrl(job.id, 'annotated.mp4')" target="_blank" rel="noreferrer">
            <button>Открыть видео</button>
          </a>
          <a :href="jobFileUrl(job.id, 'report.json')" target="_blank" rel="noreferrer">
            <button>report.json</button>
          </a>
          <a :href="jobFileUrl(job.id, 'events.csv')" target="_blank" rel="noreferrer">
            <button>events.csv</button>
          </a>
          <a :href="jobFileUrl(job.id, 'intensity.png')" target="_blank" rel="noreferrer">
            <button>intensity.png</button>
          </a>
        </div>

        <h3 style="margin-top: 24px">Предпросмотр</h3>
        <video
          controls
          style="width: 100%; max-height: 480px; background: #000; border-radius: 8px"
          :src="jobFileUrl(job.id, 'annotated.mp4')"
        />
        <div style="margin-top: 16px">
          <img
            alt="intensity"
            style="max-width: 100%; border-radius: 8px"
            :src="jobFileUrl(job.id, 'intensity.png')"
          />
        </div>
      </div>
    </template>
  </div>
</template>
