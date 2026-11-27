import { describe, expect, test } from "bun:test"
import { boxToPercent, relatedOverlayIds } from "./geometry"
import type { Overlay } from "./types"

const page = { width: 612, height: 792 }

describe("boxToPercent", () => {
  test("maps the origin and a full page", () => {
    expect(boxToPercent({ x: 0, y: 0, width: 0, height: 0 }, page)).toEqual({
      left: 0,
      top: 0,
      width: 0,
      height: 0,
    })
    expect(boxToPercent({ x: 0, y: 0, width: 612, height: 792 }, page)).toEqual({
      left: 0,
      top: 0,
      width: 100,
      height: 100,
    })
  })

  test("maps a box in the middle of a letter page", () => {
    const percent = boxToPercent({ x: 306, y: 198, width: 153, height: 79.2 }, page)
    expect(percent.left).toBeCloseTo(50, 5)
    expect(percent.top).toBeCloseTo(25, 5)
    expect(percent.width).toBeCloseTo(25, 5)
    expect(percent.height).toBeCloseTo(10, 5)
  })

  test("uses a unit page when the parse result has no size", () => {
    const percent = boxToPercent({ x: 0.5, y: 0.25, width: 0.5, height: 0.25 }, { width: 0, height: 0 })
    expect(percent).toEqual({ left: 50, top: 25, width: 50, height: 25 })
  })
})

describe("relatedOverlayIds", () => {
  const overlays: Overlay[] = [
    {
      id: "p1-t0",
      kind: "text",
      text: "Copper wire",
      box: { x: 56, y: 308, width: 120, height: 16 },
      textItemIndices: [0],
    },
    {
      id: "p1-t1",
      kind: "text",
      text: "Brass gears",
      box: { x: 56, y: 340, width: 120, height: 16 },
      textItemIndices: [1],
    },
    {
      id: "p1-b0",
      kind: "table",
      text: "Item table",
      box: { x: 48, y: 268, width: 516, height: 128 },
      textItemIndices: [0, 1],
    },
    {
      id: "p1-b1",
      kind: "rule",
      text: "",
      box: { x: 48, y: 82, width: 516, height: 1 },
      textItemIndices: [],
    },
  ]

  test("a text line highlights the table that contains it", () => {
    expect(new Set(relatedOverlayIds(overlays, "p1-t0"))).toEqual(
      new Set(["p1-t0", "p1-b0"]),
    )
  })

  test("a table highlights every line it was read from", () => {
    expect(new Set(relatedOverlayIds(overlays, "p1-b0"))).toEqual(
      new Set(["p1-t0", "p1-t1", "p1-b0"]),
    )
  })

  test("a box with no text items highlights only itself", () => {
    expect(relatedOverlayIds(overlays, "p1-b1")).toEqual(["p1-b1"])
  })

  test("an unknown id is kept so the panel can still mark it", () => {
    expect(relatedOverlayIds(overlays, "missing")).toEqual(["missing"])
    expect(relatedOverlayIds(overlays, null)).toEqual([])
  })
})
