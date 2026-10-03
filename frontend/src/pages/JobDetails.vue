<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { getJob, deleteJob, jobFileUrl, jobResultUrl } from '@/api/jobs'
import { extractError } from '@/api/client'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Spinner from '@/components/Spinner.vue'
import type { JobInfo } from '@/api/types'

const props = defineProps<{ id: string }>()
const router = useRouter()

const job = ref<JobInfo | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const deleting = ref(false)

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
  job.value?.status === 'cancelled',
)

const progressPct = computed(() =>
  job.value && job.value.progress.frames_total > 0
    ? Math.round(
        (100 * job.value.progress.frames_done) / job.value.progress.frames_total,
      )
    : 0,
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

async function onDelete() {
  if (!job.value) return
  if (!confirm(`Удалить задачу ${job.value.id}? Файлы будут стёрты с диска.`)) return
  deleting.value = true
  try {
    await deleteJob(job.value.id)
    router.push('/')
  } catch (e) {
    error.value = extractError(e)
    deleting.value = false
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
      <div class="row">
        <button
          v-if="job"
          class="danger"
          :disabled="deleting || job.status === 'running'"
          @click="onDelete"
        >
          <template v-if="deleting"><Spinner /> Удаление…</template>
          <template v-else>Удалить</template>
        </button>
        <RouterLink to="/" class="btn">← К обзору</RouterLink>
      </div>
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

        <div
          v-if="job.error_message"
          class="error-banner"
          style="margin-top: 16px; white-space: pre-wrap"
        >
          {{ job.error_message }}
        </div>
      </div>

      <div v-if="job.status === 'done'" class="card">
        <h2>Результаты</h2>
        <div class="row" style="flex-wrap: wrap; gap: 12px">
          <a class="btn primary" :href="jobResultUrl(job.id)">Скачать ZIP</a>
          <a
            class="btn"
            :href="jobFileUrl(job.id, 'annotated.mp4')"
            target="_blank"
            rel="noreferrer"
          >Открыть видео</a>
          <a
            class="btn"
            :href="jobFileUrl(job.id, 'report.json')"
            target="_blank"
            rel="noreferrer"
          >report.json</a>
          <a
            class="btn"
            :href="jobFileUrl(job.id, 'events.csv')"
            target="_blank"
            rel="noreferrer"
          >events.csv</a>
          <a
            class="btn"
            :href="jobFileUrl(job.id, 'intensity.png')"
            target="_blank"
            rel="noreferrer"
          >intensity.png</a>
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
