import { describe, expect, test } from "bun:test"
import { shapePage } from "./shape"
import type { RawPage } from "./types"

const page: RawPage = {
  pageNum: 2,
  width: 612,
  height: 792,
  text: "Invoice 1842",
  markdown: "| Item | Qty |\n| --- | --- |\n| Copper wire | 3 |",
  textItems: [
    { text: "Invoice 1842", x: 48, y: 96, width: 110, height: 16, confidence: 0.99 },
    { text: "   ", x: 10, y: 10, width: 8, height: 8 },
    { text: "Copper wire", x: 56, y: 308, width: 140, height: 16, confidence: 0.91 },
  ],
  blocks: [
    {
      kind: "heading",
      text: "NORTHWIND SUPPLY",
      level: 1,
      bbox: { x: 48, y: 46, width: 280, height: 28 },
      textItemIndices: [],
    },
    {
      kind: "table",
      bbox: { x: 48, y: 268, width: 516, height: 128 },
      textItemIndices: [2],
      header: [
        { text: "Item", textItemIndices: [] },
        { text: "Qty", textItemIndices: [] },
      ],
      rows: [[{ text: "Copper wire", textItemIndices: [2] }, { text: "3" }]],
    },
    {
      kind: "figure",
      text: "",
    },
    {
      kind: "grid_fallback",
      rows: [[{ text: "loose" }]],
    },
  ],
}

describe("shapePage", () => {
  const shaped = shapePage(page, 841.6)

  test("keeps markdown and rounds the page time", () => {
    expect(shaped.pageNum).toBe(2)
    expect(shaped.markdown).toContain("Copper wire")
    expect(shaped.ms).toBe(842)
    expect(shaped.width).toBe(612)
  })

  test("drops blank text items and keeps line boxes", () => {
    const lines = shaped.overlays.filter((overlay) => overlay.kind === "text")
    expect(lines.map((overlay) => overlay.text)).toEqual(["Invoice 1842", "Copper wire"])
    expect(lines[1]?.id).toBe("p2-t2")
    expect(lines[1]?.box).toEqual({ x: 56, y: 308, width: 140, height: 16 })
    expect(lines[1]?.textItemIndices).toEqual([2])
  })

  test("builds table rows and a table overlay from layout blocks", () => {
    expect(shaped.tables).toHaveLength(2)
    expect(shaped.tables[0]?.header.map((cell) => cell.text)).toEqual(["Item", "Qty"])
    expect(shaped.tables[0]?.rows).toEqual([
      [
        { text: "Copper wire", textItemIndices: [2] },
        { text: "3", textItemIndices: [] },
      ],
    ])
    const table = shaped.overlays.find((overlay) => overlay.kind === "table")
    expect(table?.id).toBe("p2-b1")
    expect(table?.textItemIndices).toEqual([2])
    expect(shaped.overlays.some((overlay) => overlay.kind === "heading")).toBe(true)
  })

  test("skips a block that has no box and still records a grid table", () => {
    expect(shaped.overlays.some((overlay) => overlay.kind === "figure")).toBe(false)
    expect(shaped.tables[1]?.rows[0]?.[0]?.text).toBe("loose")
  })

  test("fills a blank table cell from the text line in that column", () => {
    const repaired = shapePage(
      {
        pageNum: 1,
        width: 612,
        height: 792,
        textItems: [
          { text: "Copper wire", x: 56, y: 309, width: 73, height: 12 },
          { text: "3", x: 312, y: 309, width: 12, height: 12 },
          { text: "12.50", x: 389, y: 309, width: 36, height: 12 },
        ],
        blocks: [
          {
            kind: "merged_table",
            bbox: { x: 48, y: 268, width: 516, height: 128 },
            rows: [
              [
                { text: "Item", bbox: { x: 56, y: 277, width: 31, height: 12 } },
                { text: "Qty", bbox: { x: 308, y: 277, width: 23, height: 12 } },
                { text: "Price", bbox: { x: 387, y: 275, width: 37, height: 16 } },
              ],
              [
                { text: "Copper wire", bbox: { x: 56, y: 309, width: 73, height: 12 } },
                { text: "" },
                { text: "12.50", bbox: { x: 389, y: 309, width: 36, height: 12 } },
              ],
            ],
          },
        ],
      },
      10,
    )
    const table = repaired.tables[0]
    expect(table?.header.map((cell) => cell.text)).toEqual(["Item", "Qty", "Price"])
    expect(table?.rows[0]?.map((cell) => cell.text)).toEqual(["Copper wire", "3", "12.50"])
    expect(table?.rows[0]?.[1]?.textItemIndices).toEqual([1])
    expect(repaired.overlays.some((overlay) => overlay.kind === "table")).toBe(true)
  })

  test("an empty page still shapes", () => {
    const empty = shapePage({ pageNum: 1, width: 100, height: 100 }, 0)
    expect(empty.overlays).toEqual([])
    expect(empty.tables).toEqual([])
    expect(empty.markdown).toBe("")
    expect(empty.ms).toBe(0)
  })
})
