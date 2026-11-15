import { spawn, type ChildProcess } from "node:child_process"
import { createConnection } from "node:net"
import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"

const appRoot = join(import.meta.dirname, "..")
const sidecar = join(appRoot, "sidecar")
const python = join(sidecar, ".venv", "bin", "python")
const binPath = `${join(appRoot, "node_modules", ".bin")}:${process.env.PATH ?? ""}`

function run(command: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: appRoot, stdio: "inherit", env: process.env })
    child.on("error", reject)
    child.on("exit", (code) => {
      if (code === 0) resolve()
      else reject(new Error(`${command} ${args.join(" ")} exited ${code}`))
    })
  })
}

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
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    process.env[key] = value
  }
}

function portNumber(name: string, fallback: number): number {
  const raw = (process.env[name] ?? "").trim()
  if (!raw) return fallback
  const value = Number(raw)
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    throw new Error(`${name} must be a TCP port. Got ${raw}.`)
  }
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

async function pythonReady(): Promise<boolean> {
  if (!existsSync(python)) return false
  return new Promise((resolve) => {
    const check = spawn(
      python,
      ["-c", "import fastapi, uvicorn, httpx, importlib.metadata as m; m.version('vibe-trading-ai'); m.version('langchain-anthropic')"],
      { stdio: "ignore" },
    )
    check.on("exit", (code) => resolve(code === 0))
    check.on("error", () => resolve(false))
  })
}

async function ensurePython(): Promise<void> {
  if (await pythonReady()) return
  console.log("Installing the Python sidecar (vibe-trading-ai, FastAPI)...")
  if (!existsSync(python)) {
    await run("uv", ["venv", "--python", "3.13", join(sidecar, ".venv")])
  }
  await run("uv", ["pip", "install", "--python", python, "-r", join(sidecar, "requirements.txt")])
}

async function ensureNode(): Promise<void> {
  const viteBin = join(appRoot, "node_modules", ".bin", "vite")
  if (existsSync(viteBin)) return
  console.log("node_modules is missing, so vite is not on PATH. Running bun install...")
  await run("bun", ["install"])
}

loadEnvFile(join(appRoot, ".env"))

const deskPort = portNumber("DESK_PORT", 8010)
const vitePort = portNumber("VITE_PORT", 5174)
const vibePort = portNumber("VIBE_PORT", 8899)
process.env.DESK_PORT = String(deskPort)
process.env.VITE_PORT = String(vitePort)
process.env.VIBE_PORT = String(vibePort)
process.env.VIBE_SERVE_PORT = String(vibePort)

await ensureNode()
await ensurePython()
await ensurePortFree(deskPort, "Desk")
await ensurePortFree(vitePort, "Vite")
await ensurePortFree(vibePort, "Vibe-Trading")

console.log(`Desk http://127.0.0.1:${deskPort}`)
console.log(`Page http://127.0.0.1:${vitePort}`)
console.log(`Vibe-Trading http://127.0.0.1:${vibePort}`)

const children: ChildProcess[] = []

function start(command: string, args: string[], cwd: string): ChildProcess {
  const child = spawn(command, args, {
    cwd,
    stdio: "inherit",
    env: { ...process.env, PATH: binPath, PYTHONUNBUFFERED: "1", VIBE_DESK_AUTOSTART: "1" },
  })
  children.push(child)
  return child
}

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

const api = start(
  python,
  ["-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", String(deskPort)],
  sidecar,
)
const web = start("vite", ["--host", "127.0.0.1", "--port", String(vitePort), "--strictPort"], appRoot)

for (const child of [api, web]) {
  child.on("exit", (code) => {
    if (!stopped) shutdown(code ?? 1)
  })
}
