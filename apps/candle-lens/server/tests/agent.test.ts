import { expect, test } from "bun:test"
import {
  askAgent,
  buildMessageParams,
  clientOptions,
  createWithRetry,
  defaultModel,
  healthBody,
  illustrativeSample,
  isSamplingRejection,
  redact,
  resolveModel,
  type AgentRequest,
} from "../agent.ts"

const SECRET = "sk-ant-test-secret-value"

test("the model list, page selection, and Claude 5 request omit sampling fields", () => {
  expect(defaultModel({})).toBe("claude-sonnet-5-5")
  expect(defaultModel({ ANTHROPIC_MODEL: "claude-opus-5-5" })).toBe("claude-opus-5-5")
  const choices = resolveModel("", { ANTHROPIC_MODEL: "claude-custom-model" })
  expect(choices).toBe("claude-custom-model")
  expect(resolveModel("claude-fable-5-2", { ANTHROPIC_MODEL: "claude-opus-5-5" })).toBe("claude-fable-5-2")
  expect(() => resolveModel("claude-not-a-model", {})).toThrow("Unknown Anthropic model.")

  for (const model of ["claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-2"]) {
    const params = buildMessageParams({ model, system: "system", packet: { schema: "ai-agent-lens/v1" } })
    expect(params).not.toHaveProperty("temperature")
    expect(params).not.toHaveProperty("top_p")
    expect(params).not.toHaveProperty("top_k")
    expect(params.messages[0]?.content).toContain("ai-agent-lens/v1")
  }
})

test("the workspace header is set only when an id is present", () => {
  const withWorkspace = clientOptions("key", "wrkspc_test")
  expect(withWorkspace.defaultHeaders).toEqual({ "anthropic-workspace-id": "wrkspc_test" })
  expect(clientOptions("key", "  ").defaultHeaders).toBeUndefined()
})

test("a 400 invalid_request_error for sampling fields is retried once without them", async () => {
  const calls: AgentRequest[] = []
  const create = async (params: AgentRequest) => {
    calls.push(params)
    if (calls.length === 1) {
      const error = new Error("400 invalid_request_error: temperature is not supported") as Error & { status: number }
      error.status = 400
      throw error
    }
    return { content: [{ type: "text", text: '{"decision":"WAIT","why_this_could_fail":"one factor is missing"}\nWait for the missing factor.\nThe score has not crossed.\nCheck the next close.' }] }
  }
  const first: AgentRequest = {
    model: "claude-sonnet-5-5",
    max_tokens: 100,
    system: "s",
    messages: [{ role: "user", content: "{}" }],
    temperature: 1,
    top_p: 1,
    top_k: 5,
  }
  expect(isSamplingRejection(Object.assign(new Error("400 invalid_request_error temperature"), { status: 400 }))).toBe(true)
  const message = await createWithRetry(create, first)
  expect(calls).toHaveLength(2)
  expect(calls[1]).not.toHaveProperty("temperature")
  expect(calls[1]).not.toHaveProperty("top_p")
  expect(calls[1]).not.toHaveProperty("top_k")
  expect(message).toBeTruthy()

  const refused: AgentRequest[] = []
  await expect(
    createWithRetry(async (params) => {
      refused.push(params)
      throw Object.assign(new Error("400 invalid_request_error: model missing"), { status: 400 })
    }, first),
  ).rejects.toThrow("model missing")
  expect(refused).toHaveLength(1)
})

test("no key returns the labeled sample and does not call the network", async () => {
  let called = false
  const result = await askAgent({
    env: {},
    symbol: "RELIANCE.NS",
    capital: 100_000,
    currency: "INR",
    packet: { schema: "ai-agent-lens/v1" },
    model: "claude-opus-5-5",
    create: async () => {
      called = true
      return {}
    },
  })
  expect(called).toBe(false)
  expect(result.illustrative).toBe(true)
  expect(result.label).toContain("Illustrative sample")
  expect(result.decision).toBe("LONG")
  expect(result.why_this_could_fail).toContain("relief rally")
  expect(result.summary.length).toBeGreaterThan(0)
  expect(illustrativeSample().signal.decision).toBe("LONG")
})

test("health and logs never contain the key value", () => {
  const health = JSON.stringify(healthBody({ ANTHROPIC_API_KEY: SECRET, ANTHROPIC_MODEL: "claude-sonnet-5-5" }))
  expect(health).not.toContain(SECRET)
  expect(health).toContain("\"anthropic\":true")
  const line = redact(`upstream failed using ${SECRET}`, [SECRET])
  expect(line).not.toContain(SECRET)
  expect(line).toContain("[redacted]")
  const empty = JSON.stringify(healthBody({ ANTHROPIC_API_KEY: "  " }))
  expect(empty).toContain("\"anthropic\":false")
})
