<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { listJobs } from '@/api/jobs'
import { listStreams } from '@/api/streams'
import { createUpload } from '@/api/uploads'
import { extractError } from '@/api/client'
import type { JobInfo, StreamInfo } from '@/api/types'

const emit = defineEmits<{
  (e: 'change', payload: { source: 'upload' | 'stream'; id: string; tSec: number }): void
}>()

type Kind = 'job' | 'stream' | 'inline'

const kind = ref<Kind>('job')
const jobs = ref<JobInfo[]>([])
const streams = ref<StreamInfo[]>([])
const selectedJob = ref('')
const selectedStream = ref('')
const tSec = ref(0)
const loading = ref(true)
const error = ref<string | null>(null)

// inline-загрузка
const inlineFile = ref<File | null>(null)
const inlineUploading = ref(false)
const inlineProgress = ref(0)

onMounted(async () => {
  try {
    const [js, ss] = await Promise.all([listJobs(), listStreams()])
    jobs.value = js.filter((j) => j.status === 'done')
    streams.value = ss
    if (jobs.value.length > 0) selectedJob.value = jobs.value[0].id
    if (streams.value.length > 0) selectedStream.value = streams.value[0].id
  } catch (e) {
    error.value = extractError(e)
  } finally {
    loading.value = false
  }
})

watch(kind, () => {
  error.value = null
})

function emitChange() {
  if (kind.value === 'job' && selectedJob.value) {
    emit('change', { source: 'upload', id: selectedJob.value, tSec: tSec.value })
  } else if (kind.value === 'stream' && selectedStream.value) {
    emit('change', { source: 'stream', id: selectedStream.value, tSec: 0 })
  }
  // inline эмитит в onInlineSubmit после успешной загрузки
}

function onPickInlineFile(f: File | undefined) {
  if (!f) return
  error.value = null
  inlineFile.value = f
}

async function onInlineSubmit() {
  if (!inlineFile.value) return
  inlineUploading.value = true
  inlineProgress.value = 0
  error.value = null
  try {
    const info = await createUpload(inlineFile.value, (loaded, total) => {
      inlineProgress.value = Math.round((100 * loaded) / total)
    })
    // эмитим сразу после загрузки: файл на сервере, кадр можно запросить
    emit('change', { source: 'upload', id: info.id, tSec: 0 })
  } catch (e) {
    error.value = extractError(e)
  } finally {
    inlineUploading.value = false
  }
}
</script>

<template>
  <div class="card">
    <h3 style="margin-top: 0">Подложка</h3>

    <div class="form-row">
      <label>Источник</label>
      <select v-model="kind">
        <option value="job">Из обработанного видео</option>
        <option value="stream">Из RTSP-потока</option>
        <option value="inline">Загрузить своё видео</option>
      </select>
    </div>

    <!-- вариант 1: job -->
    <template v-if="kind === 'job'">
      <div class="form-row">
        <label>Видео</label>
        <select v-model="selectedJob" @change="emitChange">
          <option v-if="jobs.length === 0" value="">— нет готовых задач —</option>
          <option v-for="j in jobs" :key="j.id" :value="j.id">
            {{ j.input_filename }}
          </option>
        </select>
      </div>
      <div class="form-row">
        <label>Секунда</label>
        <input
          v-model.number="tSec"
          type="number"
          min="0"
          step="0.5"
          @change="emitChange"
        />
      </div>
      <button
        class="primary"
        style="width: 100%"
        :disabled="!selectedJob"
        @click="emitChange"
      >
        Загрузить кадр
      </button>
    </template>

    <!-- вариант 2: stream -->
    <template v-else-if="kind === 'stream'">
      <div class="form-row">
        <label>Поток</label>
        <select v-model="selectedStream" @change="emitChange">
          <option v-if="streams.length === 0" value="">— нет активных —</option>
          <option v-for="s in streams" :key="s.id" :value="s.id">
            {{ s.rtsp_url_masked }} ({{ s.status }})
          </option>
        </select>
      </div>
      <button
        class="primary"
        style="width: 100%"
        :disabled="!selectedStream"
        @click="emitChange"
      >
        Загрузить кадр
      </button>
    </template>

    <!-- вариант 3: inline upload -->
    <template v-else>
      <div class="form-row">
        <label>Файл</label>
        <input
          type="file"
          accept="video/*"
          @change="onPickInlineFile(($event.target as HTMLInputElement).files?.[0])"
        />
      </div>

      <div v-if="inlineUploading" class="progress">
        <div class="bar" :style="{ width: `${inlineProgress}%` }" />
      </div>

      <button
        class="primary"
        style="width: 100%"
        :disabled="!inlineFile || inlineUploading"
        @click="onInlineSubmit"
      >
        <template v-if="inlineUploading">Загрузка… {{ inlineProgress }}%</template>
        <template v-else>Загрузить и взять кадр</template>
      </button>
    </template>

    <div v-if="loading" class="muted" style="font-size: 12px; margin-top: 8px">
      Загрузка списков…
    </div>
    <div v-else-if="error" class="muted" style="font-size: 12px; color: #fca5a5; margin-top: 8px">
      {{ error }}
    </div>
  </div>
</template>
