import { spawn, type ChildProcess } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { createConnection } from "node:net"
import { join } from "node:path"

const appRoot = join(import.meta.dirname, "..")
const binPath = `${join(appRoot, "node_modules", ".bin")}:${process.env.PATH ?? ""}`

function loadEnvFile(file: string): void {
  if (!existsSync(file)) return
  for (const line of readFileSync(file, "utf8").split("\n")) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) continue
    const eq = trimmed.indexOf("=")
    if (eq < 0) continue
    const key = trimmed.slice(0, eq).trim()
    if (!key || process.env[key] !== undefined) continue
    let value = trimmed.slice(eq + 1).trim()
    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    process.env[key] = value
  }
}

function portNumber(name: string, fallback: number): number {
  const raw = (process.env[name] ?? "").trim()
  if (!raw) return fallback
  const value = Number(raw)
  if (!Number.isInteger(value) || value < 1 || value > 65535) throw new Error(`${name} must be a TCP port. Got ${raw}.`)
  return value
}

function portInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host: "127.0.0.1" })
    const finish = (used: boolean) => {
      socket.removeAllListeners()
      socket.destroy()
      resolve(used)
    }
    socket.once("connect", () => finish(true))
    socket.once("error", () => finish(false))
  })
}

async function ensurePortFree(port: number, label: string): Promise<void> {
  if (!(await portInUse(port))) return
  console.error(`${label} port ${port} is already in use.`)
  console.error(`Free it with: lsof -ti tcp:${port} | xargs kill`)
  process.exit(1)
}

loadEnvFile(join(appRoot, ".env"))
const deskPort = portNumber("DESK_PORT", 8011)
const vitePort = portNumber("VITE_PORT", 5175)
process.env.DESK_PORT = String(deskPort)
process.env.VITE_PORT = String(vitePort)

await ensurePortFree(deskPort, "API")
await ensurePortFree(vitePort, "Vite")

console.log(`API http://127.0.0.1:${deskPort}`)
console.log(`Page http://127.0.0.1:${vitePort}`)

const children: ChildProcess[] = []
let stopped = false

function shutdown(code = 0): void {
  if (stopped) return
  stopped = true
  for (const child of children) {
    if (child.exitCode === null) child.kill("SIGTERM")
  }
  process.exit(code)
}

process.on("SIGINT", () => shutdown(0))
process.on("SIGTERM", () => shutdown(0))

function start(command: string, args: string[]): ChildProcess {
  const child = spawn(command, args, {
    cwd: appRoot,
    stdio: "inherit",
    env: { ...process.env, PATH: binPath },
  })
  children.push(child)
  child.on("exit", (code) => {
    if (!stopped) shutdown(code ?? 1)
  })
  return child
}

start("bun", ["server/index.ts"])
start("vite", ["--host", "127.0.0.1", "--port", String(vitePort), "--strictPort"])
