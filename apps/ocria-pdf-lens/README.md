# OCRia PDF Lens

A single-user desk for [OCRia-nano-1](https://huggingface.co/llamaindex/OCRia-nano-1), LlamaIndex’s open-weight 8.1M-parameter CPU OCR model (line detector, script router, four recognizers, and LayoutNet). It runs locally in the browser through [LiteParse](https://github.com/run-llama/liteparse)’s WASM build. Drop a PDF or a scan, or open the bundled invoice, and the page is drawn with boxes for text, tables, and layout next to the extracted Markdown and tables. Each page shows its own millisecond time.

No API key. The file stays in the browser.

## Sources

- Weights: [llamaindex/OCRia-nano-1](https://huggingface.co/llamaindex/OCRia-nano-1) (modified Open RAIL-M). Not committed.
- Runtime: [@llamaindex/liteparse-wasm](https://www.npmjs.com/package/@llamaindex/liteparse-wasm) 2.21.3, from [run-llama/liteparse](https://github.com/run-llama/liteparse) (Apache 2.0)
- Blog: [Introducing OCRia-nano-1](https://www.llamaindex.ai/blog/introducing-ocria-nano-1)
- Bookmark: [https://x.com/jerryjliu0/status/2124909031999553926](https://x.com/jerryjliu0/status/2124909031999553926)

## Run

Requires [Bun](https://bun.sh).

```bash
cd apps/ocria-pdf-lens
bun install
bun run dev
```

Open http://127.0.0.1:5176/

The first visit downloads OCRia-nano-1 with `OcriaNano.fromUrl()` (the browser API; `models.pull` is the Node and CLI call and is not in the WASM package). The desk shows byte progress. The download is the model files from Hugging Face, sha256-checked, about 30 MB. The native pull is quoted at 60–75 MB because it also fetches ONNX Runtime, which this build does not use. Weights are not written into the repo.

`bunfig.toml` keeps a 3-day `minimumReleaseAge`. `@llamaindex/liteparse-wasm@2.21.3` was published 2026-11-26, so that exact version is listed in `minimumReleaseAgeExcludes`.

## Tesseract

LiteParse’s compiled Tesseract backend is not in the WASM build. Compare uses LiteParse’s `ocrEngine` callback with [tesseract.js](https://github.com/naptha/tesseract.js) (`eng`), timed per page the same way. The column is labeled Tesseract.js. The first compare also downloads Tesseract’s English traineddata.

## Fixture mode

If the model download fails, the bundled sample still opens with a banner and a saved reading. That view is not a live parse, and the timer stays blank.

## Tests

```bash
bun test
```

Tests cover box-to-percent mapping and result shaping. They do not download models or use the network.
