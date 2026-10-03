<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { listLines } from '@/api/lines'
import { createStream, stopStream } from '@/api/streams'
import { extractError } from '@/api/client'
import { useStreamWs } from '@/composables/useStreamWs'
import { useLimitsStore } from '@/stores/limits'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Spinner from '@/components/Spinner.vue'
import type { LinesConfig, StreamInfo } from '@/api/types'

const limitsStore = useLimitsStore()
const { limits } = storeToRefs(limitsStore)

const rtspUrl = ref('')
const configId = ref('')
const configs = ref<LinesConfig[]>([])
const submitting = ref(false)
const submitError = ref<string | null>(null)

const activeStream = ref<StreamInfo | null>(null)
const streamId = computed(() => activeStream.value?.id ?? null)

const { connected, lastFrame, stats, error: wsError } = useStreamWs(streamId, {
  frameFps: 10,
})

const displayError = computed(() => submitError.value || wsError.value)

onMounted(async () => {
  await limitsStore.load()
  try {
    configs.value = await listLines()
    if (configs.value.length > 0) configId.value = configs.value[0].id
  } catch (e) {
    submitError.value = extractError(e)
  }
})

async function onConnect() {
  if (!rtspUrl.value.trim()) return
  submitError.value = null
  submitting.value = true
  try {
    const stream = await createStream({
      rtsp_url: rtspUrl.value.trim(),
      lines_config_id: configId.value || null,
    })
    activeStream.value = stream
  } catch (e) {
    submitError.value = extractError(e)
  } finally {
    submitting.value = false
  }
}

async function onStop() {
  if (!activeStream.value) return
  try {
    await stopStream(activeStream.value.id)
  } catch {
    // поток мог уже умереть — не блокируем UI
  }
  activeStream.value = null
}

function statusLabel(s: string): string {
  return (
    {
      starting: 'запускается',
      running: 'работает',
      stopped: 'остановлен',
      error: 'ошибка',
    }[s] ?? s
  )
}
</script>

<template>
  <div>
    <h1>RTSP-поток</h1>

    <ErrorBanner v-if="displayError" :message="displayError" />

    <!-- Форма подключения -->
    <div v-if="!activeStream" class="card">
      <div class="form-row">
        <label for="rtsp-url">RTSP URL</label>
        <input
          id="rtsp-url"
          v-model="rtspUrl"
          placeholder="rtsp://user:pass@host:554/stream"
          :disabled="submitting"
          @keyup.enter="onConnect"
        />
        <div class="hint muted" style="margin-top: 4px">
          Поддерживается rtsp:// и rtsps://. Пароль маскируется в логах и API.
        </div>
      </div>

      <div class="form-row">
        <label for="lines-config">Конфиг линий</label>
        <select
          id="lines-config"
          v-model="configId"
          :disabled="submitting || configs.length === 0"
        >
          <option v-if="configs.length === 0" value="">— нет конфигов —</option>
          <option v-for="c in configs" :key="c.id" :value="c.id">
            {{ c.name }} ({{ c.lines.length }} лин.)
          </option>
        </select>
      </div>

      <button
        class="primary"
        :disabled="!rtspUrl.trim() || submitting"
        @click="onConnect"
      >
        <template v-if="submitting"><Spinner /> Подключение…</template>
        <template v-else>Подключиться</template>
      </button>
    </div>

    <!-- Live-вид -->
    <div v-else class="card">
      <div class="row between" style="margin-bottom: 12px">
        <div class="row">
          <span class="badge" :class="activeStream.status">
            {{ statusLabel(activeStream.status) }}
          </span>
          <span class="muted mono">{{ activeStream.rtsp_url_masked }}</span>
        </div>
        <div class="row">
          <span class="muted" style="font-size: 12px">
            <template v-if="connected">WS ✓</template>
            <template v-else>WS …</template>
          </span>
          <button class="danger" @click="onStop">Остановить</button>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 16px">
        <!-- Видео -->
        <div>
          <div
            style="
              background: #000;
              border-radius: 8px;
              overflow: hidden;
              min-height: 240px;
              display: flex;
              align-items: center;
              justify-content: center;
            "
          >
            <img
              v-if="lastFrame"
              :src="lastFrame"
              alt="live"
              style="width: 100%; display: block"
            />
            <div v-else class="muted" style="padding: 48px">
              <Spinner />
              <span style="margin-left: 8px">Ожидание кадра…</span>
            </div>
          </div>
          <div
            v-if="activeStream.last_frame_at"
            class="hint muted"
            style="margin-top: 8px"
          >
            Последний кадр:
            {{ new Date(activeStream.last_frame_at).toLocaleTimeString('ru-RU') }}
          </div>
        </div>

        <!-- Панель статистики -->
        <div>
          <div class="card" style="margin-bottom: 12px">
            <h3 style="margin-top: 0">Статистика</h3>
            <template v-if="stats">
              <div class="row between" style="margin-bottom: 8px">
                <span class="muted">Всего</span>
                <strong style="font-size: 24px">{{ stats.total }}</strong>
              </div>
              <div class="row between" style="margin-bottom: 8px">
                <span class="muted">FPS</span>
                <span>{{ stats.fps.toFixed(1) }}</span>
              </div>
              <div class="row between">
                <span class="muted">Активных треков</span>
                <span>{{ stats.active }}</span>
              </div>
            </template>
            <div v-else class="muted">Ожидание данных…</div>
          </div>

          <div v-if="stats && Object.keys(stats.per_line).length" class="card">
            <h3 style="margin-top: 0">По линиям</h3>
            <div
              v-for="(dirs, lineId) in stats.per_line"
              :key="lineId"
              style="margin-bottom: 8px"
            >
              <div
                class="mono"
                style="font-size: 12px; color: var(--text-dim)"
              >
                {{ lineId }}
              </div>
              <div class="row" style="gap: 16px">
                <span
                  v-for="(count, dir) in dirs"
                  :key="dir"
                  class="row"
                  style="gap: 4px"
                >
                  <span class="muted">{{ dir }}:</span>
                  <strong>{{ count }}</strong>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
