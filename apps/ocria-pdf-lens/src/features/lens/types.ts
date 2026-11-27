export interface Box {
  x: number
  y: number
  width: number
  height: number
}

export type OverlayKind =
  | "text"
  | "table"
  | "heading"
  | "paragraph"
  | "list"
  | "figure"
  | "code"
  | "rule"
  | "other"

export interface Overlay {
  id: string
  kind: OverlayKind
  text: string
  box: Box
  textItemIndices: number[]
}

export interface ShapedCell {
  text: string
  textItemIndices: number[]
  box?: Box
}

export interface ShapedTable {
  id: string
  box?: Box
  header: ShapedCell[]
  rows: ShapedCell[][]
}

export interface ShapedPage {
  pageNum: number
  width: number
  height: number
  markdown: string
  text: string
  ms: number
  overlays: Overlay[]
  tables: ShapedTable[]
}

export type ParseEngine = "ocria-nano" | "tesseract" | "fixture"

export interface ShapedDocument {
  sourceName: string
  engine: ParseEngine
  pages: ShapedPage[]
}

export interface RawCell {
  text?: string
  bbox?: Box
  textItemIndices?: number[]
}

export interface RawBlock {
  kind?: string
  text?: string
  level?: number
  header?: RawCell[]
  rows?: RawCell[][]
  lines?: string[]
  bbox?: Box
  textItemIndices?: number[]
}

export interface RawTextItem {
  text?: string
  x: number
  y: number
  width: number
  height: number
  confidence?: number
}

export interface RawPage {
  pageNum: number
  width: number
  height: number
  text?: string
  markdown?: string
  textItems?: RawTextItem[]
  blocks?: RawBlock[]
}

export interface LoadedFile {
  name: string
  bytes: Uint8Array
  mime: string
  kind: "pdf" | "image"
}

export interface PercentBox {
  left: number
  top: number
  width: number
  height: number
}
