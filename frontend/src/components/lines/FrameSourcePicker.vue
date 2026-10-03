<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listJobs } from '@/api/jobs'
import { listStreams } from '@/api/streams'
import type { JobInfo, StreamInfo } from '@/api/types'

const emit = defineEmits<{
  (e: 'change', payload: { source: 'upload' | 'stream'; id: string; tSec: number }): void
}>()

const kind = ref<'upload' | 'stream'>('upload')
const jobs = ref<JobInfo[]>([])
const streams = ref<StreamInfo[]>([])
const selectedJob = ref('')
const selectedStream = ref('')
const tSec = ref(0)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const [js, ss] = await Promise.all([listJobs(), listStreams()])
    jobs.value = js.filter((j) => j.status === 'done')
    streams.value = ss
    if (jobs.value.length > 0) selectedJob.value = jobs.value[0].id
    if (streams.value.length > 0) selectedStream.value = streams.value[0].id
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
})

function emitChange() {
  if (kind.value === 'upload' && selectedJob.value) {
    emit('change', { source: 'upload', id: selectedJob.value, tSec: tSec.value })
  } else if (kind.value === 'stream' && selectedStream.value) {
    emit('change', { source: 'stream', id: selectedStream.value, tSec: 0 })
  }
}
</script>

<template>
  <div class="card">
    <h3 style="margin-top: 0">Подложка</h3>

    <div class="form-row">
      <label>Источник</label>
      <select v-model="kind" @change="emitChange">
        <option value="upload">Из загруженного видео</option>
        <option value="stream">Из RTSP-потока</option>
      </select>
    </div>

    <template v-if="kind === 'upload'">
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
    </template>

    <template v-else>
      <div class="form-row">
        <label>Поток</label>
        <select v-model="selectedStream" @change="emitChange">
          <option v-if="streams.length === 0" value="">— нет активных —</option>
          <option v-for="s in streams" :key="s.id" :value="s.id">
            {{ s.rtsp_url_masked }} ({{ s.status }})
          </option>
        </select>
      </div>
    </template>

    <div v-if="loading" class="muted" style="font-size: 12px">Загрузка…</div>
    <div v-else-if="error" class="muted" style="font-size: 12px; color: #fca5a5">
      {{ error }}
    </div>

    <button
      class="primary"
      style="width: 100%; margin-top: 8px"
      :disabled="(kind === 'upload' && !selectedJob) || (kind === 'stream' && !selectedStream)"
      @click="emitChange"
    >
      Загрузить кадр
    </button>
  </div>
</template>
