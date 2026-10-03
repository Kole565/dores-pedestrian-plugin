<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { LinesConfig } from '@/api/types'

const props = defineProps<{
  configs: LinesConfig[]
  selectedId: string | null
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'create', name: string): void
  (e: 'rename', id: string, newName: string): void
  (e: 'delete', id: string): void
}>()

const editingId = ref<string | null>(null)
const editingName = ref('')

const inputRef = ref<HTMLInputElement | null>(null)

function startRename(c: LinesConfig) {
  editingId.value = c.id
  editingName.value = c.name
  nextTick(() => inputRef.value?.focus())
}

function commitRename() {
  if (!editingId.value) return
  const name = editingName.value.trim()
  if (name) {
    emit('rename', editingId.value, name)
  }
  editingId.value = null
  editingName.value = ''
}

function cancelRename() {
  editingId.value = null
  editingName.value = ''
}

const newName = ref('')

function onCreate() {
  const name = newName.value.trim()
  if (!name) return
  emit('create', name)
  newName.value = ''
}

function fmtDate(s: string): string {
  try {
    return new Date(s).toLocaleString('ru-RU')
  } catch {
    return s
  }
}
</script>

<template>
  <div class="card">
    <h3 style="margin-top: 0">Конфиги линий</h3>

    <div class="row" style="margin-bottom: 12px; gap: 8px">
      <input
        v-model="newName"
        placeholder="Новый конфиг…"
        @keyup.enter="onCreate"
        style="flex: 1"
      />
      <button :disabled="!newName.trim()" @click="onCreate">+</button>
    </div>

    <div v-if="configs.length === 0" class="muted" style="padding: 12px 0">
      Пока нет конфигов
    </div>

    <ul class="config-list">

      <li
        v-for="c in configs"
        :key="c.id"
        :class="{ active: c.id === selectedId }"
        @click="emit('select', c.id)"
      >
        <div style="flex: 1; min-width: 0">
          <template v-if="editingId === c.id">
            <input
              v-model="editingName"
              @keyup.enter="commitRename"
              @keyup.escape="cancelRename"
              @blur="commitRename"
              style="padding: 2px 6px; font-size: 13px"
            />
          </template>
          <template v-else>
            <div style="font-weight: 500; overflow: hidden; text-overflow: ellipsis">
              {{ c.name }}
            </div>
            <div class="muted" style="font-size: 11px">
              {{ c.lines.length }} лин. · {{ fmtDate(c.updated_at) }}
            </div>
          </template>
        </div>

        <div class="row" style="gap: 4px; flex-shrink: 0">
          <button
            v-if="editingId !== c.id"
            style="padding: 2px 6px; font-size: 11px"
            title="Переименовать"
            @click.stop="startRename(c)"
          >✎</button>
          <button
            class="danger"
            style="padding: 2px 6px; font-size: 11px"
            title="Удалить"
            @click.stop="emit('delete', c.id)"
          >✕</button>
        </div>
      </li>

    </ul>
  </div>
</template>

<style scoped>
.config-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.config-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.1s;
}
.config-list li:hover {
  background: rgba(255, 255, 255, 0.05);
}
.config-list li.active {
  background: rgba(59, 130, 246, 0.15);
  border-left: 3px solid var(--accent);
  padding-left: 7px;
}
</style>
