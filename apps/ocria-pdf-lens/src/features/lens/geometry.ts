import type { Box, Overlay, PercentBox } from "./types"

export function boxToPercent(
  box: Box,
  page: { width: number; height: number },
): PercentBox {
  const width = page.width > 0 ? page.width : 1
  const height = page.height > 0 ? page.height : 1
  return {
    left: (box.x / width) * 100,
    top: (box.y / height) * 100,
    width: (box.width / width) * 100,
    height: (box.height / height) * 100,
  }
}

/** Overlay ids that share a text-item index with the hit, including the hit. */
export function relatedOverlayIds(
  overlays: readonly Overlay[],
  hitId: string | null,
): string[] {
  if (!hitId) return []
  const hit = overlays.find((overlay) => overlay.id === hitId)
  if (!hit) return [hitId]
  const ids = new Set<string>([hit.id])
  if (hit.textItemIndices.length === 0) return [...ids]
  const indexes = new Set(hit.textItemIndices)
  for (const overlay of overlays) {
    if (overlay.textItemIndices.some((index) => indexes.has(index))) {
      ids.add(overlay.id)
    }
  }
  return [...ids]
}
