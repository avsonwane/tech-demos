import type {
  Box,
  Overlay,
  OverlayKind,
  RawBlock,
  RawCell,
  RawPage,
  RawTextItem,
  ShapedCell,
  ShapedPage,
  ShapedTable,
} from "./types"

const KINDS: Record<string, OverlayKind> = {
  heading: "heading",
  paragraph: "paragraph",
  list_item: "list",
  table: "table",
  merged_table: "table",
  grid_fallback: "table",
  figure: "figure",
  code: "code",
  rule: "rule",
}

function cellOf(raw: RawCell): ShapedCell {
  const cell: ShapedCell = {
    text: raw.text ?? "",
    textItemIndices: raw.textItemIndices ?? [],
  }
  if (raw.bbox) cell.box = raw.bbox
  return cell
}

function centerOf(box: Box): { x: number; y: number } {
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
}

function average(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

/**
 * LayoutNet sometimes leaves a cell blank even when a text line sits in that
 * column. Fill those cells from the page's text items, and point every cell
 * at the lines it covers so a hover can move both ways.
 */
export function repairTableBlock(block: RawBlock, items: RawTextItem[]): RawBlock {
  const rows = (block.rows ?? []).map((row) =>
    row.map((cell) => ({ ...cell, textItemIndices: [...(cell.textItemIndices ?? [])] })),
  )
  const columnX: number[][] = []
  const rowY: number[][] = []
  for (const [rowIndex, row] of rows.entries()) {
    for (const [columnIndex, cell] of row.entries()) {
      if (!cell.bbox) continue
      const point = centerOf(cell.bbox)
      ;(columnX[columnIndex] ??= []).push(point.x)
      ;(rowY[rowIndex] ??= []).push(point.y)
    }
  }
  const columnCenter = columnX.map((values) => average(values ?? []))
  const rowCenter = rowY.map((values) => average(values ?? []))
  const claimed = new Set<number>()

  const repaired = rows.map((row, rowIndex) =>
    row.map((cell, columnIndex) => {
      const y = rowCenter[rowIndex]
      const x = columnCenter[columnIndex]
      if (y == null || x == null) return cell
      const nearby = items
        .map((item, index) => {
          const text = (item.text ?? "").trim()
          if (!text) return null
          const point = centerOf({ x: item.x, y: item.y, width: item.width, height: item.height })
          const distance = Math.abs(point.x - x) + Math.abs(point.y - y)
          if (Math.abs(point.x - x) > 48 || Math.abs(point.y - y) > 18) return null
          return { index, text, item, distance }
        })
        .filter((hit): hit is NonNullable<typeof hit> => hit !== null)
        .sort((a, b) => a.distance - b.distance)

      if (!(cell.text ?? "").trim()) {
        const hit = nearby.find((candidate) => !claimed.has(candidate.index))
        if (!hit) return cell
        claimed.add(hit.index)
        return {
          ...cell,
          text: hit.text,
          textItemIndices: [hit.index],
          bbox: { x: hit.item.x, y: hit.item.y, width: hit.item.width, height: hit.item.height },
        }
      }

      const indexes = nearby
        .filter((candidate) => !claimed.has(candidate.index))
        .map((candidate) => candidate.index)
      for (const index of indexes) claimed.add(index)
      if ((cell.textItemIndices ?? []).length > 0 || indexes.length === 0) return cell
      return { ...cell, textItemIndices: indexes }
    }),
  )

  return { ...block, rows: repaired }
}

function blockText(block: RawBlock): string {
  if (block.text && block.text.trim()) return block.text
  if (block.lines && block.lines.length > 0) return block.lines.join("\n")
  const header = (block.header ?? []).map((cell) => cell.text ?? "").join(" | ")
  const rows = (block.rows ?? []).map((row) =>
    row.map((cell) => cell.text ?? "").join(" | "),
  )
  return [header, ...rows].filter((line) => line.trim()).join("\n")
}

export function shapePage(page: RawPage, ms: number): ShapedPage {
  const overlays: Overlay[] = []
  for (const [index, item] of (page.textItems ?? []).entries()) {
    const text = item.text ?? ""
    if (!text.trim()) continue
    overlays.push({
      id: `p${page.pageNum}-t${index}`,
      kind: "text",
      text,
      box: { x: item.x, y: item.y, width: item.width, height: item.height },
      textItemIndices: [index],
    })
  }

  const tables: ShapedTable[] = []
  for (const [index, block] of (page.blocks ?? []).entries()) {
    const hasGrid =
      (block.header?.length ?? 0) > 0 || (block.rows?.length ?? 0) > 0
    const kind = hasGrid ? "table" : (KINDS[block.kind ?? ""] ?? "other")
    const id = `p${page.pageNum}-b${index}`
    if (block.bbox && block.bbox.width > 0 && block.bbox.height > 0) {
      overlays.push({
        id,
        kind,
        text: blockText(block),
        box: block.bbox,
        textItemIndices: block.textItemIndices ?? [],
      })
    }
    if (block.kind === "table" || block.kind === "grid_fallback" || block.kind === "merged_table" || hasGrid) {
      const repaired = repairTableBlock(block, page.textItems ?? [])
      let header = (repaired.header ?? []).map(cellOf)
      let rows = (repaired.rows ?? []).map((row) => row.map(cellOf))
      if (header.length === 0 && rows.length > 1) {
        header = rows[0] ?? []
        rows = rows.slice(1)
      }
      tables.push({ id, box: block.bbox, header, rows })
    }
  }

  return {
    pageNum: page.pageNum,
    width: page.width,
    height: page.height,
    markdown: page.markdown ?? "",
    text: page.text ?? "",
    ms: Math.round(ms),
    overlays,
    tables,
  }
}
