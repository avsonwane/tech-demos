import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "")
  const deskPort = env.DESK_PORT || process.env.DESK_PORT || "8011"
  const vitePort = Number(env.VITE_PORT || process.env.VITE_PORT || "5175")
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      host: "127.0.0.1",
      port: vitePort,
      strictPort: true,
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${deskPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
