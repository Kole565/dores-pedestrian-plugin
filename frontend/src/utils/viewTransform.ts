/**
 * View transform: canvas ↔ image координаты.
 *
 * scale — во сколько раз увеличен image при отрисовке.
 * offsetX/Y — смещение в canvas-пикселях (левый верхний угол image).
 *
 * screen = image * scale + offset
 * image  = (screen - offset) / scale
 */
export interface ViewTransform {
  scale: number
  offsetX: number
  offsetY: number
}

export const IDENTITY_VIEW: ViewTransform = {
  scale: 1,
  offsetX: 0,
  offsetY: 0,
}

export function screenToImage(
  sx: number,
  sy: number,
  view: ViewTransform,
): [number, number] {
  return [(sx - view.offsetX) / view.scale, (sy - view.offsetY) / view.scale]
}

export function imageToScreen(
  ix: number,
  iy: number,
  view: ViewTransform,
): [number, number] {
  return [ix * view.scale + view.offsetX, iy * view.scale + view.offsetY]
}

/**
 * Zoom к точке курсора: точка (sx, sy) на экране остаётся на месте.
 * factor > 1 — приблизить, < 1 — отдалить.
 */
export function zoomAt(
  view: ViewTransform,
  sx: number,
  sy: number,
  factor: number,
  minScale = 0.1,
  maxScale = 10,
): ViewTransform {
  const newScale = clamp(view.scale * factor, minScale, maxScale)
  const realFactor = newScale / view.scale
  return {
    scale: newScale,
    offsetX: sx - (sx - view.offsetX) * realFactor,
    offsetY: sy - (sy - view.offsetY) * realFactor,
  }
}

/**
 * Вписать изображение в canvas: scale=fit, центрирование.
 */
export function fitView(
  imageW: number,
  imageH: number,
  canvasW: number,
  canvasH: number,
): ViewTransform {
  if (imageW <= 0 || imageH <= 0) return IDENTITY_VIEW
  const scale = Math.min(canvasW / imageW, canvasH / imageH)
  const offsetX = (canvasW - imageW * scale) / 2
  const offsetY = (canvasH - imageH * scale) / 2
  return { scale, offsetX, offsetY }
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

/** Расстояние от точки (px, py) до отрезка (x1,y1)-(x2,y2). */
export function distToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): number {
  const dx = x2 - x1
  const dy = y2 - y1
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.hypot(px - x1, py - y1)
  let t = ((px - x1) * dx + (py - y1) * dy) / lenSq
  t = clamp(t, 0, 1)
  const projX = x1 + t * dx
  const projY = y1 + t * dy
  return Math.hypot(px - projX, py - projY)
}
