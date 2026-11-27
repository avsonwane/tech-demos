import { shapePage } from "./shape"
import type { RawPage, ShapedDocument } from "./types"

const invoice: RawPage = {
  pageNum: 1,
  width: 612,
  height: 792,
  text: "NORTHWIND SUPPLY\nInvoice 1842\nCopper wire 3 12.50 37.50\nTotal 124.74",
  markdown: [
    "# NORTHWIND SUPPLY",
    "",
    "Invoice 1842",
    "12 March 2026",
    "",
    "Bill to",
    "Ada Lovelace",
    "Analytical Engines",
    "12 Threadneedle Street",
    "",
    "| Item | Qty | Price | Amount |",
    "| --- | --- | --- | --- |",
    "| Copper wire | 3 units | 12.50 | 37.50 |",
    "| Brass gears | 8 units | 4.00 | 32.00 |",
    "| Oak panel | 1 unit | 46.00 | 46.00 |",
    "",
    "Subtotal 115.50",
    "Tax 9.24",
    "Total 124.74",
    "",
    "Thank you for your order.",
  ].join("\n"),
  textItems: [
    { text: "NORTHWIND SUPPLY", x: 48, y: 46, width: 280, height: 26 },
    { text: "Invoice 1842", x: 48, y: 96, width: 140, height: 18 },
    { text: "Copper wire", x: 56, y: 308, width: 160, height: 16 },
    { text: "Brass gears", x: 56, y: 340, width: 150, height: 16 },
    { text: "Oak panel", x: 56, y: 372, width: 130, height: 16 },
    { text: "Total", x: 380, y: 478, width: 60, height: 16 },
  ],
  blocks: [
    {
      kind: "heading",
      text: "NORTHWIND SUPPLY",
      level: 1,
      bbox: { x: 48, y: 46, width: 280, height: 28 },
      textItemIndices: [0],
    },
    {
      kind: "paragraph",
      text: "Invoice 1842",
      bbox: { x: 48, y: 96, width: 200, height: 40 },
      textItemIndices: [1],
    },
    {
      kind: "table",
      bbox: { x: 48, y: 268, width: 516, height: 128 },
      textItemIndices: [2, 3, 4],
      header: [
        { text: "Item" },
        { text: "Qty" },
        { text: "Price" },
        { text: "Amount" },
      ],
      rows: [
        [{ text: "Copper wire", textItemIndices: [2] }, { text: "3 units" }, { text: "12.50" }, { text: "37.50" }],
        [{ text: "Brass gears", textItemIndices: [3] }, { text: "8 units" }, { text: "4.00" }, { text: "32.00" }],
        [{ text: "Oak panel", textItemIndices: [4] }, { text: "1 unit" }, { text: "46.00" }, { text: "46.00" }],
      ],
    },
  ],
}

const notes: RawPage = {
  pageNum: 2,
  width: 612,
  height: 792,
  text: "Notes\nShip the oak panel flat.",
  markdown: "# Notes\n\nShip the oak panel flat.\n\nCall the workshop before Thursday.\n\nPayment is due in 14 days.",
  textItems: [
    { text: "Notes", x: 48, y: 46, width: 90, height: 26 },
    { text: "Ship the oak panel flat.", x: 48, y: 110, width: 240, height: 18 },
  ],
  blocks: [
    {
      kind: "heading",
      text: "Notes",
      level: 1,
      bbox: { x: 48, y: 46, width: 120, height: 28 },
      textItemIndices: [0],
    },
    {
      kind: "paragraph",
      text: "Ship the oak panel flat.",
      bbox: { x: 48, y: 110, width: 320, height: 80 },
      textItemIndices: [1],
    },
  ],
}

export function fixtureDocument(sourceName: string): ShapedDocument {
  return {
    sourceName,
    engine: "fixture",
    pages: [shapePage(invoice, 0), shapePage(notes, 0)],
  }
}
