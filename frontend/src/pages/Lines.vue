<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  createLines,
  deleteLines,
  frameUrl,
  listLines,
  updateLines,
} from '@/api/lines'
import { extractError } from '@/api/client'
import ConfigList from '@/components/lines/ConfigList.vue'
import FrameSourcePicker from '@/components/lines/FrameSourcePicker.vue'
import LineCanvas from '@/components/lines/LineCanvas.vue'
import LineProperties from '@/components/lines/LineProperties.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import Spinner from '@/components/Spinner.vue'
import type { Line, LinesConfig } from '@/api/types'

const configs = ref<LinesConfig[]>([])
const selectedId = ref<string | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const saving = ref(false)

// рабочие данные
const editingName = ref('')
const editingLines = ref<Line[]>([])
const frameW = ref(0)
const frameH = ref(0)
const selectedLineId = ref<string | null>(null)
const drawing = ref(false)

// источник кадра
const frameSource = ref<{
  source: 'upload' | 'stream'
  id: string
  tSec: number
} | null>(null)
const frameUrlComputed = computed(() => {
  if (!frameSource.value) return null
  return frameUrl({
    source: frameSource.value.source,
    id: frameSource.value.id,
    tSec: frameSource.value.tSec,
  })
})

const selectedConfig = computed(
  () => configs.value.find((c) => c.id === selectedId.value) ?? null,
)
const selectedLine = computed(
  () => editingLines.value.find((l) => l.line_id === selectedLineId.value) ?? null,
)

const dirty = computed(() => {
  const cfg = selectedConfig.value
  if (!cfg) return false
  if (cfg.name !== editingName.value) return true
  return JSON.stringify(cfg.lines) !== JSON.stringify(editingLines.value)
})

onMounted(loadConfigs)

async function loadConfigs() {
  loading.value = true
  try {
    configs.value = await listLines()
    if (configs.value.length > 0 && !selectedId.value) {
      selectConfig(configs.value[0].id)
    } else if (selectedId.value) {
      // обновить редактируемый конфиг
      const cfg = configs.value.find((c) => c.id === selectedId.value)
      if (cfg) selectConfig(cfg.id)
    }
  } catch (e) {
    error.value = extractError(e)
  } finally {
    loading.value = false
  }
}

function selectConfig(id: string) {
  const cfg = configs.value.find((c) => c.id === id)
  if (!cfg) return
  selectedId.value = id
  editingName.value = cfg.name
  editingLines.value = JSON.parse(JSON.stringify(cfg.lines))
  frameW.value = cfg.frame_width ?? 0
  frameH.value = cfg.frame_height ?? 0
  selectedLineId.value = editingLines.value[0]?.line_id ?? null
  drawing.value = false
}

async function onCreateConfig(name: string) {
  try {
    const cfg = await createLines({ name, lines: [] })
    configs.value = [cfg, ...configs.value]
    selectConfig(cfg.id)
  } catch (e) {
    error.value = extractError(e)
  }
}

async function onDeleteConfig(id: string) {
  if (!confirm('Удалить конфиг?')) return
  try {
    await deleteLines(id)
    configs.value = configs.value.filter((c) => c.id !== id)
    if (selectedId.value === id) {
      selectedId.value = null
      editingLines.value = []
      editingName.value = ''
    }
  } catch (e) {
    error.value = extractError(e)
  }
}

async function onRenameConfig(id: string, newName: string) {
  const cfg = configs.value.find((c) => c.id === id)
  if (!cfg) return
  try {
    const updated = await updateLines(id, {
      name: newName,
      frame_width: cfg.frame_width ?? null,
      frame_height: cfg.frame_height ?? null,
      lines: cfg.lines,
    })
    configs.value = configs.value.map((c) => (c.id === id ? updated : c))
    // если это выбранный конфиг — обновить editingName
    if (selectedId.value === id) {
      editingName.value = newName
    }
  } catch (e) {
    error.value = extractError(e)
  }
}

function onFrameChange(payload: {
  source: 'upload' | 'stream'
  id: string
  tSec: number
}) {
  frameSource.value = payload
  // сбросить размеры — узнаем после загрузки изображения
  // (frame_width/height берём из конфига, если он их уже знает)
}

function onFrameLoaded(w: number, h: number) {
  // вызывается из LineCanvas после onload
  if (frameW.value === 0 || frameH.value === 0) {
    frameW.value = w
    frameH.value = h
  }
}

function onAddLine(coords: [number, number, number, number]) {
  const id = nextLineId()
  editingLines.value = [
    ...editingLines.value,
    {
      line_id: id,
      coords,
      direction_pos_to_neg: 'in',
      direction_neg_to_pos: 'out',
      use_point: 'bottom_center',
    },
  ]
  selectedLineId.value = id
  drawing.value = false
}

function nextLineId(): string {
  const used = new Set(editingLines.value.map((l) => l.line_id))
  let i = 1
  while (used.has(`line_${i}`)) i++
  return `line_${i}`
}

function onUpdateLineCoords(
  lineId: string,
  coords: [number, number, number, number],
) {
  editingLines.value = editingLines.value.map((l) =>
    l.line_id === lineId ? { ...l, coords } : l,
  )
}

function onUpdateLineProps(patch: Partial<Line>) {
  if (!selectedLineId.value) return
  const oldId = selectedLineId.value
  editingLines.value = editingLines.value.map((l) =>
    l.line_id === oldId ? { ...l, ...patch } : l,
  )
  if (patch.line_id && patch.line_id !== oldId) {
    selectedLineId.value = patch.line_id
  }
}

function onDeleteSelected() {
  if (!selectedLineId.value) return
  editingLines.value = editingLines.value.filter(
    (l) => l.line_id !== selectedLineId.value,
  )
  selectedLineId.value = null
}

async function onSave() {
  if (!selectedId.value) return
  saving.value = true
  try {
    const updated = await updateLines(selectedId.value, {
      name: editingName.value,
      frame_width: frameW.value || null,
      frame_height: frameH.value || null,
      lines: editingLines.value,
    })
    configs.value = configs.value.map((c) =>
      c.id === updated.id ? updated : c,
    )
  } catch (e) {
    error.value = extractError(e)
  } finally {
    saving.value = false
  }
}

function onExport() {
  const data = {
    name: editingName.value,
    frame_width: frameW.value || null,
    frame_height: frameH.value || null,
    lines: editingLines.value,
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${editingName.value || 'lines'}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function onImport() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      if (typeof data.name === 'string') editingName.value = data.name
      if (typeof data.frame_width === 'number') frameW.value = data.frame_width
      if (typeof data.frame_height === 'number') frameH.value = data.frame_height
      if (Array.isArray(data.lines)) editingLines.value = data.lines
    } catch (e) {
      error.value = `Импорт не удался: ${extractError(e)}`
    }
  }
  input.click()
}

function onAddClick() {
  drawing.value = true
  selectedLineId.value = null
}
</script>

<template>
  <div>
    <h1>Редактор линий</h1>

    <ErrorBanner v-if="error" :message="error" />

    <div v-if="loading" class="row">
      <Spinner /> <span class="muted">Загрузка конфигов…</span>
    </div>

    <div v-else class="lines-layout">
      <!-- Левая колонка: конфиги + подложка -->
      <aside class="lines-sidebar">
        <ConfigList
          :configs="configs"
          :selected-id="selectedId"
          @select="selectConfig"
          @create="onCreateConfig"
          @rename="onRenameConfig"
          @delete="onDeleteConfig"
        />

        <FrameSourcePicker
          v-if="selectedId"
          @change="onFrameChange"
        />
      </aside>

      <!-- Центр: canvas -->
      <section class="lines-canvas-wrap">
        <div class="row between" style="margin-bottom: 8px">
          <div class="row">
            <span class="mono muted">{{ editingName }}</span>

            <button
              :class="{ primary: !drawing }"
              :disabled="!selectedId"
              @click="onAddClick"
            >
              + Добавить линию
            </button>
          </div>
          <div class="row">
            <button :disabled="!selectedId" @click="onImport">Импорт</button>
            <button :disabled="!selectedId" @click="onExport">Экспорт</button>
            <button
              class="primary"
              :disabled="!selectedId || !dirty || saving"
              @click="onSave"
            >
              <template v-if="saving"><Spinner /> Сохранение…</template>
              <template v-else-if="dirty">Сохранить *</template>
              <template v-else>Сохранено</template>
            </button>
          </div>
        </div>

        <div class="lines-canvas-container">
          <LineCanvas
            v-if="selectedId"
            :image-url="frameUrlComputed"
            :image-width="frameW"
            :image-height="frameH"
            :lines="editingLines"
            :selected-id="selectedLineId"
            :drawing="drawing"
            @select="(id) => (selectedLineId = id)"
            @update-line="onUpdateLineCoords"
            @add-line="onAddLine"
            @drawing-done="drawing = false"
            @image-loaded="onFrameLoaded"
          />
          <div v-else class="empty">
            Выберите конфиг или создайте новый
          </div>
        </div>
      </section>

      <!-- Правая колонка: свойства -->
      <aside class="lines-props">
        <LineProperties
          :line="selectedLine"
          @update="onUpdateLineProps"
          @delete="onDeleteSelected"
        />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.lines-layout {
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  gap: 16px;
  align-items: start;
}
@media (max-width: 1100px) {
  .lines-layout {
    grid-template-columns: 1fr;
  }
}
.lines-sidebar,
.lines-props {
  position: sticky;
  top: 16px;
}
.lines-canvas-container {
  height: 600px;
  border-radius: 8px;
  overflow: hidden;
}
.lines-canvas-container .empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
