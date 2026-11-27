# OCRia PDF Lens

## Goal

A single-user desk that drops in a PDF or scan, runs OCRia-nano-1 locally through LiteParse, and shows each page with box overlays beside the extracted Markdown and tables, plus a per-page millisecond timer.

## Single-user MVP

- `cd apps/ocria-pdf-lens && bun install && bun run dev` opens a working page on port 5176.
- A bundled two-page scan-like invoice (image-only PDF, includes a ruled table) loads with no upload.
- The user can also drop a PDF or a PNG/JPEG.
- Parse on CPU in the browser with LiteParse’s OCRia-nano-1 build. Each page shows its own milliseconds.
- Page preview with bounding-box overlays for text lines, tables, and other layout blocks. Hover or click a box to highlight the matching extracted text, and the other way around.
- Extracted Markdown and reconstructed tables in a side panel.
- Optional Tesseract compare on the same page, with its own times.
- First-run model download with a visible progress state. Model weights are not committed. No API key.

## Out of scope

LlamaParse cloud, OCRia-1 VLM, chart-to-table, handwriting showcases, accounts, multi-user, batch folders, a document library, PDF editing or export, sending documents to any remote parse API, and a new Cloudflare Pages project.

## Vertical slices

1. Scaffold Vite, `bunfig.toml`, README, and this plan.
2. Bundled sample, drop zone, and page preview.
3. OCRia-nano-1 parse, model-download progress, per-page timer, Markdown and tables.
4. Overlays synced to the extraction.
5. Optional Tesseract compare.
6. Tests for result shaping and box mapping, then a screenshot and a screen recording.
7. Append the source bookmark under `tracking/seen-bookmarks.json` `built`.

## Stack

- **Bun + Vite + React + TypeScript.** One screen, so no Next.js. Scaffolded with `bunx create-vite --template react-ts --no-immediate`, then `bunfig.toml`, then `bun install`.
- **shadcn/ui minimalist preset** (`sera` / `radix-sera`, the editorial preset already used in this monorepo). Components added only as needed.
- **`@llamaindex/liteparse-wasm@2.21.3`.** The official browser build runs OCRia-nano-1 with no server: `OcriaNano.fromUrl()` then `LiteParse.withOcriaNano(...).parse()`. It returns Markdown on each page plus `textItems` and, with `extractBlocks`, layout blocks and table cells. Boxes are top-left, 72 DPI points (`x`, `y`, `width`, `height`) against `page.width` / `page.height`. `parse` also accepts a PNG or JPEG as a one-page document. `2.21.1` is old enough for the age gate, but its `parse` notes only PDF bytes, so this app pins `2.21.3`.
- **No Bun API.** The wasm path returns Markdown and boxes locally, so ports 8012 and a sidecar are unused. UI is `http://127.0.0.1:5176`.
- **Model download.** Wasm does not export `models.pull` (that is the Node, Python, and CLI API). The official browser call is `OcriaNano.fromUrl()`, which fetches this release’s files from Hugging Face and checks the pinned sha256. The desk wraps `fetch` for that call so the UI can show loaded bytes. Weights stay in the browser cache. The native pull is about 60–75 MB because it includes ONNX Runtime; the wasm files are the models only (recognizers plus LayoutNet, on the order of 30 MB).
- **Age gate.** `bunfig.toml` keeps `minimumReleaseAge = 259200`. `2.21.3` is younger than three days, so `minimumReleaseAgeExcludes` lists only `@llamaindex/liteparse-wasm@2.21.3`.
- **Per-page time.** `openBatchSession(bytes, 1)` times each `nextBatch()`. A one-page batch skips cross-page header stripping, which is acceptable for this desk.
- **Tables.** Layout blocks with kind `table`, `merged_table`, or `grid_fallback` (or any block that already has rows) become the reconstructed table. A blank cell is filled from a text line whose center sits in that column, which is how a narrow quantity survives when the cell text comes back empty.
- **Page raster.** The wasm build does not provide screenshots. PDF pages are drawn with pdf.js. PNG/JPEG drops are shown as images. Overlays are percentages of the parsed page size, so they track the preview.
- **Tesseract.** The wasm build has no compiled Tesseract (`ocrBackend: "tesseract"` is the native package). The compare uses LiteParse’s documented `ocrEngine` callback with tesseract.js (`eng`), timed the same way. The panel labels that engine as Tesseract.js, not the native backend.
- **Fixture mode.** If `fromUrl` fails after a real attempt, the sample still opens with a clearly labeled saved parse and no invented timer. Live OCRia is the default.

## Layout

```
apps/ocria-pdf-lens/
  public/sample/invoice-scan.pdf
  src/features/lens/          desk, preview, overlays, parse, shaping
  src/features/lens/*.test.ts pure shaping and box mapping
  src/components/ui/          shadcn components actually used
  scripts/make-sample.py      regenerates the bundled scan
```

## Testing

`bun test` covers box-to-percent mapping and parse-result shaping only. It does not download models or open the network. No git hooks: this repo has no hook runner.

## Deferred

- Batch ingest, parse history, and a deploy preview.
- A required CJK or RTL fixture. The model can route those scripts; this sample stays Latin so the first screen is readable.
- Native `@llamaindex/liteparse` and `models.pull`, unless the wasm smoke test fails. That path would also unlock LiteParse’s compiled Tesseract and `screenshot()`.
