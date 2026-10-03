<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Line, UsePoint } from '@/api/types'
import {
  distToSegment,
  fitView,
  IDENTITY_VIEW,
  imageToScreen,
  screenToImage,
  zoomAt,
  type ViewTransform,
} from '@/utils/viewTransform'

const props = defineProps<{
  imageUrl: string | null
  imageWidth: number
  imageHeight: number
  lines: Line[]
  selectedId: string | null
  /** true — в режиме добавления линии (2 клика) */
  drawing: boolean
}>()

const emit = defineEmits<{
  (e: 'select', lineId: string | null): void
  (e: 'update-line', lineId: string, coords: [number, number, number, number]): void
  (e: 'add-line', coords: [number, number, number, number]): void
  (e: 'drawing-done'): void
  (e: 'image-loaded', width: number, height: number): void
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const view = ref<ViewTransform>(IDENTITY_VIEW)
const canvasSize = ref({ w: 800, h: 600 })

const image = ref<HTMLImageElement | null>(null)
const imageLoaded = ref(false)

// Состояние взаимодействия
type DragTarget = { kind: 'endpoint'; lineId: string; end: 0 | 1 }
  | { kind: 'pan' }
  | null
const drag = ref<DragTarget>(null)
const dragStart = ref<{ sx: number; sy: number; view: ViewTransform } | null>(null)
const pendingDraw = ref<[number, number] | null>(null) // первая точка линии
const cursorPos = ref<[number, number] | null>(null) // для превью

// --- загрузка изображения ---
watch(
  () => props.imageUrl,
  (url) => {
    imageLoaded.value = false
    image.value = null
    if (!url) return
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      image.value = img
      imageLoaded.value = true
      emit('image-loaded', img.naturalWidth, img.naturalHeight)
      requestAnimationFrame(() => fitToContainer())
    }
    img.onerror = () => {
      imageLoaded.value = false
    }
    img.src = url
  },
  { immediate: true },
)

// --- размеры canvas = размеры контейнера ---
let ro: ResizeObserver | null = null

function fitToContainer() {
  const el = containerRef.value
  const cv = canvasRef.value
  if (!el || !cv) return
  const w = el.clientWidth
  const h = el.clientHeight
  canvasSize.value = { w, h }
  const dpr = window.devicePixelRatio || 1
  cv.width = Math.round(w * dpr)
  cv.height = Math.round(h * dpr)
  cv.style.width = `${w}px`
  cv.style.height = `${h}px`
  if (props.imageWidth > 0 && props.imageHeight > 0) {
    view.value = fitView(props.imageWidth, props.imageHeight, w, h)
  }
  draw()
}

onMounted(() => {
  ro = new ResizeObserver(fitToContainer)
  if (containerRef.value) ro.observe(containerRef.value)
  fitToContainer()
})

onUnmounted(() => {
  ro?.disconnect()
})

// --- отрисовка ---
function draw() {
  const cv = canvasRef.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, canvasSize.value.w, canvasSize.value.h)

  // фон
  ctx.fillStyle = '#0a0f1a'
  ctx.fillRect(0, 0, canvasSize.value.w, canvasSize.value.h)

  // подложка
  if (image.value && imageLoaded.value) {
    const [dx, dy] = imageToScreen(0, 0, view.value)
    const dw = props.imageWidth * view.value.scale
    const dh = props.imageHeight * view.value.scale
    ctx.imageSmoothingEnabled = view.value.scale < 1
    ctx.drawImage(image.value, dx, dy, dw, dh)
  }

  // линии
  for (const line of props.lines) {
    const selected = line.line_id === props.selectedId
    drawLine(ctx, line, selected)
  }

  // превью добавляемой линии
  if (pendingDraw.value && cursorPos.value) {
    const [x1, y1] = imageToScreen(...pendingDraw.value, view.value)
    const [x2, y2] = imageToScreen(...cursorPos.value, view.value)
    ctx.save()
    ctx.strokeStyle = '#22c55e'
    ctx.lineWidth = 2
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
    ctx.restore()
  }
}

function drawLine(
  ctx: CanvasRenderingContext2D,
  line: Line,
  selected: boolean,
) {
  const [x1, y1, x2, y2] = line.coords
  const [sx1, sy1] = imageToScreen(x1, y1, view.value)
  const [sx2, sy2] = imageToScreen(x2, y2, view.value)

  ctx.save()
  ctx.strokeStyle = selected ? '#f59e0b' : '#06b6d4'
  ctx.lineWidth = selected ? 3 : 2
  ctx.beginPath()
  ctx.moveTo(sx1, sy1)
  ctx.lineTo(sx2, sy2)
  ctx.stroke()

  // концы
  const r = selected ? 7 : 5
  for (const [x, y] of [
    [sx1, sy1],
    [sx2, sy2],
  ] as const) {
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = selected ? '#f59e0b' : '#06b6d4'
    ctx.fill()
    ctx.strokeStyle = '#0f172a'
    ctx.lineWidth = 2
    ctx.stroke()
  }

  // подпись
  const midX = (sx1 + sx2) / 2
  const midY = (sy1 + sy2) / 2
  const label = `${line.line_id}: +→${line.direction_pos_to_neg} / −→${line.direction_neg_to_pos}`
  ctx.font = '12px ui-monospace, monospace'
  const metrics = ctx.measureText(label)
  const padX = 6
  const padY = 4
  const tw = metrics.width
  const th = 14
  ctx.fillStyle = 'rgba(0,0,0,0.7)'
  ctx.fillRect(midX + 6, midY - th - padY, tw + padX * 2, th + padY * 2)
  ctx.fillStyle = selected ? '#fbbf24' : '#67e8f9'
  ctx.fillText(label, midX + 6 + padX, midY - padY)

  ctx.restore()
}

watch(
  [() => props.lines, () => props.selectedId, () => props.drawing],
  () => draw(),
  { deep: true },
)
watch([view, canvasSize], () => draw(), { deep: true })

// --- мышь: hit-test ---
function hitTestEndpoints(ix: number, iy: number): DragTarget {
  const threshold = 8 / view.value.scale // 8 экранных пикселей
  for (const line of props.lines) {
    const [x1, y1, x2, y2] = line.coords
    if (Math.hypot(ix - x1, iy - y1) < threshold) {
      return { kind: 'endpoint', lineId: line.line_id, end: 0 }
    }
    if (Math.hypot(ix - x2, iy - y2) < threshold) {
      return { kind: 'endpoint', lineId: line.line_id, end: 1 }
    }
  }
  return null
}

function hitTestLine(ix: number, iy: number): string | null {
  const threshold = 6 / view.value.scale
  for (const line of props.lines) {
    const [x1, y1, x2, y2] = line.coords
    if (distToSegment(ix, iy, x1, y1, x2, y2) < threshold) {
      return line.line_id
    }
  }
  return null
}

// --- события мыши ---
function getMouse(e: MouseEvent): [number, number] {
  const cv = canvasRef.value
  if (!cv) return [0, 0]
  const rect = cv.getBoundingClientRect()
  return [e.clientX - rect.left, e.clientY - rect.top]
}

function onMouseDown(e: MouseEvent) {
  const [sx, sy] = getMouse(e)
  const [ix, iy] = screenToImage(sx, sy, view.value)

  // pan: средняя кнопка
  if (e.button === 1) {
    e.preventDefault()
    drag.value = { kind: 'pan' }
    dragStart.value = { sx, sy, view: { ...view.value } }
    return
  }

  if (e.button !== 0) return

  // режим рисования: клик 1 — первая точка, клик 2 — вторая
  if (props.drawing) {
    if (!pendingDraw.value) {
      pendingDraw.value = [ix, iy]
    } else {
      const [x1, y1] = pendingDraw.value
      emit('add-line', [x1, y1, ix, iy])
      pendingDraw.value = null
      emit('drawing-done')
    }
    draw()
    return
  }

  // обычный режим: сначала проверяем концы линий, потом тело
  const ep = hitTestEndpoints(ix, iy)
  if (ep) {
    drag.value = ep
    dragStart.value = { sx, sy, view: { ...view.value } }
    emit('select', ep.lineId)
    return
  }

  const hitLineId = hitTestLine(ix, iy)
  if (hitLineId) {
    emit('select', hitLineId)
    return
  }

  emit('select', null)
}

function onMouseMove(e: MouseEvent) {
  const [sx, sy] = getMouse(e)
  const [ix, iy] = screenToImage(sx, sy, view.value)
  cursorPos.value = [ix, iy]

  if (props.drawing && pendingDraw.value) {
    draw()
    return
  }

  if (!drag.value || !dragStart.value) return

  if (drag.value.kind === 'pan') {
    view.value = {
      scale: dragStart.value.view.scale,
      offsetX: dragStart.value.view.offsetX + (sx - dragStart.value.sx),
      offsetY: dragStart.value.view.offsetY + (sy - dragStart.value.sy),
    }
    return
  }

  // перетаскивание конца линии
  const { lineId, end } = drag.value
  const line = props.lines.find((l) => l.line_id === lineId)
  if (!line) return
  const coords: [number, number, number, number] = [...line.coords]
  coords[end * 2] = clampImage(ix, props.imageWidth)
  coords[end * 2 + 1] = clampImage(iy, props.imageHeight)
  emit('update-line', lineId, coords)
}

function onMouseUp() {
  drag.value = null
  dragStart.value = null
}

function onMouseLeave() {
  cursorPos.value = null
  onMouseUp()
  if (pendingDraw.value) {
    pendingDraw.value = null
    draw()
  }
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  const [sx, sy] = getMouse(e)
  const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
  view.value = zoomAt(view.value, sx, sy, factor)
}

function clampImage(v: number, max: number): number {
  if (max <= 0) return v
  return Math.min(max, Math.max(0, v))
}

defineExpose({
  resetView: () => fitToContainer(),
  cancelDraw: () => {
    pendingDraw.value = null
    draw()
  },
})

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (pendingDraw.value) {
      pendingDraw.value = null
      draw()
    }
    if (props.drawing) {
      emit('drawing-done')
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div
    ref="containerRef"
    class="line-canvas-container"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseLeave"
    @wheel="onWheel"
    @contextmenu.prevent
  >
    <canvas ref="canvasRef" />
    <div v-if="!imageUrl" class="canvas-overlay muted">
      Загрузите кадр (слева), чтобы начать
    </div>
    <div v-else-if="!imageLoaded" class="canvas-overlay muted">
      Загрузка кадра…
    </div>
    <div v-if="drawing" class="canvas-hint">
      {{ pendingDraw ? 'Кликните вторую точку линии' : 'Кликните первую точку линии' }}
      · Esc — отмена
    </div>
  </div>
</template>

<style scoped>
.line-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #0a0f1a;
  border-radius: 8px;
  overflow: hidden;
  cursor: crosshair;
}
canvas {
  display: block;
  touch-action: none;
}
.canvas-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.canvas-hint {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(34, 197, 94, 0.9);
  color: white;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  pointer-events: none;
}
</style>
