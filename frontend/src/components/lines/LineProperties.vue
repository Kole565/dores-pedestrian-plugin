<script setup lang="ts">
import { computed } from 'vue'
import type { Direction, Line, UsePoint } from '@/api/types'

const props = defineProps<{
  line: Line | null
}>()

const emit = defineEmits<{
  (e: 'update', patch: Partial<Line>): void
  (e: 'delete'): void
}>()

const DIRECTIONS: Direction[] = ['in', 'out', 'left', 'right', 'unknown']
const USE_POINTS: UsePoint[] = ['bottom_center', 'center']

const coordsText = computed(() => {
  if (!props.line) return ''
  return props.line.coords.map((v) => v.toFixed(0)).join(', ')
})

function update<K extends keyof Line>(key: K, value: Line[K]) {
  emit('update', { [key]: value } as Partial<Line>)
}
</script>

<template>
  <div v-if="line" class="card">
    <h3 style="margin-top: 0">Свойства линии</h3>

    <div class="form-row">
      <label>line_id</label>
      <input
        :value="line.line_id"
        @input="update('line_id', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="form-row">
      <label>Координаты (x1, y1, x2, y2)</label>
      <input :value="coordsText" readonly class="mono" />
    </div>

    <div class="form-row">
      <label>+ → − направление</label>
      <select
        :value="line.direction_pos_to_neg"
        @change="update('direction_pos_to_neg', ($event.target as HTMLSelectElement).value as Direction)"
      >
        <option v-for="d in DIRECTIONS" :key="d" :value="d">{{ d }}</option>
      </select>
    </div>

    <div class="form-row">
      <label>− → + направление</label>
      <select
        :value="line.direction_neg_to_pos"
        @change="update('direction_neg_to_pos', ($event.target as HTMLSelectElement).value as Direction)"
      >
        <option v-for="d in DIRECTIONS" :key="d" :value="d">{{ d }}</option>
      </select>
    </div>

    <div class="form-row">
      <label>Точка трека</label>
      <select
        :value="line.use_point"
        @change="update('use_point', ($event.target as HTMLSelectElement).value as UsePoint)"
      >
        <option v-for="p in USE_POINTS" :key="p" :value="p">{{ p }}</option>
      </select>
      <div class="hint muted" style="margin-top: 4px">
        bottom_center — «под ногами», стабильнее на уличных камерах
      </div>
    </div>

    <button class="danger" style="margin-top: 8px" @click="emit('delete')">
      Удалить линию
    </button>
  </div>

  <div v-else class="card">
    <div class="muted">
      Кликните линию для редактирования или нажмите «+ Добавить линию».
    </div>
  </div>
</template>
