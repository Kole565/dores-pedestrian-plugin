<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createJob } from '@/api/jobs'
import { listLines } from '@/api/lines'
import { extractError } from '@/api/client'
import { useLimitsStore } from '@/stores/limits'
import { storeToRefs } from 'pinia'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Spinner from '@/components/Spinner.vue'
import type { LinesConfig } from '@/api/types'

const router = useRouter()
const limitsStore = useLimitsStore()
const { limits } = storeToRefs(limitsStore)

const file = ref<File | null>(null)
const dragover = ref(false)
const configs = ref<LinesConfig[]>([])
const configId = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const uploadPct = ref(0)

const accept = computed(() =>
  (limits.value?.allowed_video_ext ?? ['.mp4', '.avi', '.mov', '.mkv', '.webm']).join(',')
)

onMounted(async () => {
  await limitsStore.load()
  try {
    configs.value = await listLines()
    if (configs.value.length > 0) configId.value = configs.value[0].id
  } catch (e) {
    error.value = extractError(e)
  }
})

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(2)} GB`
}

function validateFile(f: File): string | null {
  const ext = '.' + (f.name.split('.').pop() ?? '').toLowerCase()
  const allowed = limits.value?.allowed_video_ext ?? ['.mp4', '.avi', '.mov', '.mkv', '.webm']
  if (!allowed.includes(ext)) {
    return `Недопустимое расширение '${ext}'. Разрешены: ${allowed.join(', ')}`
  }
  if (limits.value && f.size > limits.value.max_upload_bytes) {
    return `Файл слишком большой: ${humanBytes(f.size)} > ${humanBytes(limits.value.max_upload_bytes)}`
  }
  return null
}

function onPickFile(f: File | undefined) {
  if (!f) return
  const err = validateFile(f)
  if (err) {
    error.value = err
    file.value = null
    return
  }
  error.value = null
  file.value = f
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragover.value = false
  onPickFile(e.dataTransfer?.files?.[0])
}

async function onSubmit() {
  if (!file.value) return
  error.value = null
  busy.value = true
  uploadPct.value = 0
  try {
    const job = await createJob({
      file: file.value,
      linesConfigId: configId.value || null,
      onUploadProgress: (loaded, total) => {
        uploadPct.value = Math.round((100 * loaded) / total)
      },
    })
    router.push(`/jobs/${job.id}`)
  } catch (e) {
    error.value = extractError(e)
    busy.value = false
  }
}
</script>

<template>
  <div>
    <h1>Загрузить видео</h1>

    <ErrorBanner v-if="error" :message="error" />

    <div class="card">
      <div
        class="dropzone"
        :class="{ dragover }"
        @click="!busy && ($refs.fileInput as HTMLInputElement).click()"
        @dragover.prevent="dragover = true"
        @dragleave="dragover = false"
        @drop="onDrop"
      >
        <input
          ref="fileInput"
          type="file"
          :accept="accept"
          style="display: none"
          @change="onPickFile(($event.target as HTMLInputElement).files?.[0])"
        />
        <template v-if="file">
          <div style="font-size: 16px; font-weight: 600">{{ file.name }}</div>
          <div class="hint">{{ humanBytes(file.size) }}</div>
          <div v-if="!busy" class="hint" style="margin-top: 12px">
            Кликните, чтобы выбрать другой файл
          </div>
        </template>
        <template v-else>
          <div style="font-size: 16px">Перетащите видео сюда</div>
          <div class="hint">или кликните для выбора файла</div>
          <div class="hint" style="margin-top: 8px">
            <template v-if="limits">
              До {{ humanBytes(limits.max_upload_bytes) }} · {{ limits.allowed_video_ext.join(', ') }}
            </template>
            <template v-else>Загрузка лимитов…</template>
          </div>
        </template>
      </div>
    </div>

    <div class="card">
      <div class="form-row">
        <label for="lines-config">Конфиг линий</label>
        <select
          id="lines-config"
          v-model="configId"
          :disabled="busy || configs.length === 0"
        >
          <option v-if="configs.length === 0" value="">— нет конфигов —</option>
          <option v-for="c in configs" :key="c.id" :value="c.id">
            {{ c.name }} ({{ c.lines.length }} лин.)
          </option>
        </select>
        <div class="hint muted" style="margin-top: 4px">
          Если конфигов нет — создайте его в
          <RouterLink to="/lines">редакторе линий</RouterLink>.
          Пока используется дефолтный конфиг с сервера.
        </div>
      </div>

      <template v-if="busy">
        <div class="progress">
          <div class="bar" :style="{ width: `${uploadPct}%` }"></div>
        </div>
        <div class="progress-meta">
          <span>Загрузка файла…</span>
          <span>{{ uploadPct }}%</span>
        </div>
      </template>

      <div class="row" style="margin-top: 8px">
        <button
          class="primary"
          :disabled="!file || busy"
          @click="onSubmit"
        >
          <template v-if="busy"><Spinner /> Загрузка…</template>
          <template v-else>Запустить обработку</template>
        </button>
        <button v-if="file && !busy" @click="file = null">Сбросить</button>
      </div>
    </div>
  </div>
</template>
