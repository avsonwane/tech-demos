import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  optimizeDeps: {
    exclude: ["@llamaindex/liteparse-wasm"],
  },
  server: {
    host: "127.0.0.1",
    port: 5176,
  },
  preview: {
    host: "127.0.0.1",
    port: 5176,
  },
})
