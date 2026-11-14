import { spawn, type ChildProcess } from "node:child_process"
import { existsSync } from "node:fs"
import { join } from "node:path"

const appRoot = join(import.meta.dirname, "..")
const sidecar = join(appRoot, "sidecar")
const python = join(sidecar, ".venv", "bin", "python")
const binPath = `${join(appRoot, "node_modules", ".bin")}:${process.env.PATH ?? ""}`

function run(command: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: appRoot, stdio: "inherit" })
    child.on("error", reject)
    child.on("exit", (code) => {
      if (code === 0) resolve()
      else reject(new Error(`${command} ${args.join(" ")} exited ${code}`))
    })
  })
}

async function pythonReady(): Promise<boolean> {
  if (!existsSync(python)) return false
  return new Promise((resolve) => {
    const check = spawn(python, ["-c", "import fastapi, uvicorn, tradingagents"], { stdio: "ignore" })
    check.on("exit", (code) => resolve(code === 0))
    check.on("error", () => resolve(false))
  })
}

async function ensurePython(): Promise<void> {
  if (await pythonReady()) return
  console.log("Installing the Python sidecar (TradingAgents, FastAPI)...")
  if (!existsSync(python)) {
    await run("uv", ["venv", "--python", "3.13", join(sidecar, ".venv")])
  }
  await run("uv", ["pip", "install", "--python", python, "-r", join(sidecar, "requirements.txt")])
}

await ensurePython()

const children: ChildProcess[] = []

function start(command: string, args: string[], cwd: string): ChildProcess {
  const child = spawn(command, args, {
    cwd,
    stdio: "inherit",
    env: { ...process.env, PATH: binPath, PYTHONUNBUFFERED: "1" },
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

const api = start(python, ["-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"], sidecar)
const web = start("vite", ["--host", "127.0.0.1", "--port", "5173"], appRoot)

for (const child of [api, web]) {
  child.on("exit", (code) => {
    if (!stopped) shutdown(code ?? 1)
  })
}
