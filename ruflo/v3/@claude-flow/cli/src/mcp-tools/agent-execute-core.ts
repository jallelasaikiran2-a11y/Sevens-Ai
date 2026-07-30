/**
 * Shared agent-execution core.
 *
 * Provider priority order (VEXORA production config):
 *   1. OpenRouter  — PRIMARY  (OPENROUTER_API_KEY  or RUFLO_PROVIDER=openrouter)
 *   2. Google Gemini — SECONDARY (GEMINI_API_KEY     or RUFLO_PROVIDER=gemini)
 *   3. Ollama      — LOCAL    (OLLAMA_API_KEY       or RUFLO_PROVIDER=ollama)
 *   4. Anthropic   — OPTIONAL (ANTHROPIC_API_KEY    or RUFLO_PROVIDER=anthropic)
 *
 * Anthropic is NEVER mandatory. OpenRouter is the default execution provider.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { getProjectCwd } from './types.js';

const STORAGE_DIR = '.claude-flow';
const AGENT_DIR = 'agents';
const AGENT_FILE = 'store.json';

type ClaudeModel = 'haiku' | 'sonnet' | 'opus' | 'opus-4.7' | 'inherit';

export interface AgentRecord {
  agentId: string;
  agentType: string;
  status: 'idle' | 'busy' | 'terminated';
  health: number;
  taskCount: number;
  config: Record<string, unknown>;
  createdAt: string;
  domain?: string;
  model?: ClaudeModel;
  modelRoutedBy?: 'explicit' | 'router' | 'codemod' | 'default' | 'hybrid';
  /**
   * ADR-149 — concrete picked model id (e.g. `openai/gpt-4.1`,
   * `inclusionai/ling-2.6-flash`). Present when the cost-optimal neural
   * router contributed to the decision; downstream `executeAgentInline`
   * uses this to dispatch via the correct provider's API instead of
   * falling back to MODEL_MAP[tier].
   */
  modelId?: string;
  /** Execution provider hint — openrouter is PRIMARY, gemini SECONDARY. */
  provider?: 'anthropic' | 'openrouter' | 'gemini' | 'ollama';
  /** Concrete OpenRouter model slug when provider='openrouter'. */
  openrouterModel?: string;
  lastResult?: Record<string, unknown>;
}

interface AgentStore {
  agents: Record<string, AgentRecord>;
  version: string;
}

function getAgentDir(): string { return join(getProjectCwd(), STORAGE_DIR, AGENT_DIR); }
function getAgentPath(): string { return join(getAgentDir(), AGENT_FILE); }
function ensureAgentDir(): void {
  const dir = getAgentDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}
function loadAgentStore(): AgentStore {
  try {
    if (existsSync(getAgentPath())) return JSON.parse(readFileSync(getAgentPath(), 'utf-8'));
  } catch { /* fall through */ }
  return { agents: {}, version: '3.0.0' };
}
function saveAgentStore(store: AgentStore): void {
  ensureAgentDir();
  writeFileSync(getAgentPath(), JSON.stringify(store, null, 2), 'utf-8');
}

// #1906/#2232 — Current model ids (Claude 4.x family):
//   Opus 4.8    → claude-opus-4-8   (current, the `opus` alias)
//   Opus 4.7    → claude-opus-4-7   (prior pin, reachable via `opus-4.7`)
//   Sonnet 5    → claude-sonnet-5   (current, the `sonnet` alias)
//   Sonnet 4.6  → claude-sonnet-4-6 (prior pin, reachable via `sonnet-4.6`)
//   Haiku 4.5   → claude-haiku-4-5-20251001
// `inherit` and the various defaults below all map to Sonnet 5.
export const DEFAULT_ANTHROPIC_MODEL = 'claude-sonnet-5';
const MODEL_MAP: Record<string, string> = {
  haiku: 'claude-haiku-4-5-20251001',
  sonnet: 'claude-sonnet-5',
  'sonnet-4.6': 'claude-sonnet-4-6',
  opus: 'claude-opus-4-8',
  'opus-4.7': 'claude-opus-4-7',
  inherit: DEFAULT_ANTHROPIC_MODEL,
};

// #2357 — the adaptive-thinking family (Fable 5, Opus 4.8, Opus 4.7, Sonnet 5)
// removed the sampling parameters (temperature/top_p/top_k); the Anthropic API
// returns 400 "Extra inputs are not permitted" when any is present.
// Prefix-match so dated snapshots (e.g. claude-opus-4-8-YYYYMMDD) are
// covered. Applies only to the direct Anthropic path — the Ollama/OpenRouter
// OpenAI-compat paths accept temperature and are unchanged.
export function modelRejectsSamplingParams(model: string): boolean {
  return /^claude-(fable-5|opus-4-8|opus-4-7|sonnet-5)/.test(model);
}

export interface AnthropicCallInput {
  prompt: string;
  systemPrompt?: string;
  model?: string;          // already-resolved Anthropic model id (e.g. 'claude-sonnet-4-6')
  maxTokens?: number;
  temperature?: number;
  timeoutMs?: number;
}

export interface AnthropicCallResult {
  success: boolean;
  model?: string;
  messageId?: string;
  stopReason?: string;
  output?: string;
  usage?: { inputTokens: number; outputTokens: number; totalTokens: number };
  durationMs?: number;
  error?: string;
}

/**
 * Unified LLM call — provider priority: OpenRouter → Gemini → Ollama → Anthropic.
 *
 * OpenRouter is the PRIMARY provider for VEXORA. No provider is mandatory;
 * the function tries available providers in priority order and returns the
 * first successful result. Anthropic is the final optional fallback.
 */
export async function callAnthropicMessages(input: AnthropicCallInput): Promise<AnthropicCallResult> {
  const explicitProvider = (process.env.RUFLO_PROVIDER || '').toLowerCase();
  const openrouterKey = process.env.OPENROUTER_API_KEY;
  const geminiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  const ollamaKey = process.env.OLLAMA_API_KEY;
  const anthropicKey = process.env.ANTHROPIC_API_KEY;

  // Determine provider selection:
  // Explicit override wins; otherwise auto-detect by available keys.
  // Priority: openrouter > gemini > ollama > anthropic
  const useOpenRouter = explicitProvider === 'openrouter' ||
    (!explicitProvider && !!openrouterKey);
  const useGemini = explicitProvider === 'gemini' ||
    (!explicitProvider && !openrouterKey && !!geminiKey);
  const useOllama = explicitProvider === 'ollama' ||
    (!explicitProvider && !openrouterKey && !geminiKey && !!ollamaKey);
  const useAnthropic = explicitProvider === 'anthropic' ||
    (!explicitProvider && !openrouterKey && !geminiKey && !ollamaKey && !!anthropicKey);

  // 1. OpenRouter — PRIMARY provider
  if (useOpenRouter && openrouterKey) {
    return callOpenAICompat({
      ...input,
      apiKey: openrouterKey,
      baseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api',
      providerLabel: 'openrouter',
      // VEXORA default: DeepSeek V3 via OpenRouter (cost-efficient, highly capable)
      defaultModel: process.env.OPENROUTER_DEFAULT_MODEL || 'deepseek/deepseek-chat',
    });
  }

  // 2. Gemini — SECONDARY provider
  if (useGemini && geminiKey) {
    return callGeminiCompat({ ...input, apiKey: geminiKey });
  }

  // 3. Ollama — LOCAL/self-hosted provider
  if (useOllama && ollamaKey) {
    return callOllamaCompat({ ...input, apiKey: ollamaKey });
  }

  // 4. Anthropic — OPTIONAL fallback (never mandatory)
  if (!useAnthropic || !anthropicKey) {
    return {
      success: false,
      error:
        'No LLM provider configured. Set OPENROUTER_API_KEY (primary), GEMINI_API_KEY (secondary), ' +
        'OLLAMA_API_KEY (local), or ANTHROPIC_API_KEY (optional). ' +
        'Or set RUFLO_PROVIDER=openrouter|gemini|ollama|anthropic to force a specific provider.',
    };
  }
  const model = input.model || DEFAULT_ANTHROPIC_MODEL;
  const startedAt = Date.now();
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), input.timeoutMs || 60000);
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': anthropicKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model,
        max_tokens: input.maxTokens || 1024,
        // #2357 — omit temperature for models that reject sampling params
        // (Fable 5 / Opus 4.8 / Opus 4.7 → 400 "Extra inputs are not
        // permitted"); keep the 0.7 default unchanged for models that still
        // accept it (sonnet / haiku / opus ≤4.6).
        ...(modelRejectsSamplingParams(model)
          ? {}
          : { temperature: typeof input.temperature === 'number' ? input.temperature : 0.7 }),
        // #8 prompt caching (hermes-agent pattern): mark the (often large,
        // stable) system prompt as an ephemeral cache breakpoint so repeated
        // agent_execute calls with the same system prompt hit Anthropic's
        // prompt cache (~90% discount on cached input tokens, 5-min TTL).
        ...(input.systemPrompt
          ? { system: [{ type: 'text', text: input.systemPrompt, cache_control: { type: 'ephemeral' } }] }
          : {}),
        messages: [{ role: 'user', content: input.prompt }],
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      const errText = await res.text().catch(() => '<unreadable error body>');
      return { success: false, model, error: `Anthropic API error ${res.status}: ${errText.slice(0, 400)}` };
    }
    const data = await res.json() as {
      id: string;
      model: string;
      content: Array<{ type: string; text?: string }>;
      stop_reason: string;
      usage: { input_tokens: number; output_tokens: number };
    };
    const textOut = data.content
      .filter(c => c.type === 'text' && typeof c.text === 'string')
      .map(c => c.text as string)
      .join('');
    return {
      success: true,
      model: data.model,
      messageId: data.id,
      stopReason: data.stop_reason,
      output: textOut,
      usage: {
        inputTokens: data.usage.input_tokens,
        outputTokens: data.usage.output_tokens,
        totalTokens: data.usage.input_tokens + data.usage.output_tokens,
      },
      durationMs: Date.now() - startedAt,
    };
  } catch (err) {
    return {
      success: false,
      model,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Date.now() - startedAt,
    };
  }
}

/**
 * Google Gemini provider — SECONDARY provider for VEXORA.
 *
 * Endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
 * Auth: ?key=GEMINI_API_KEY
 *
 * Translates the Ruflo/Anthropic-flavored input onto Gemini's generateContent
 * format and normalizes the response back. Logical tier names map to Gemini models:
 *   - 'haiku'  → gemini-2.0-flash-001  (fast, cheap)
 *   - 'sonnet' → gemini-2.0-flash-001  (balanced default)
 *   - 'opus'   → gemini-2.5-pro        (complex reasoning)
 *   - explicit 'gemini:model-name'     → passed through
 *
 * Override the default model via GEMINI_DEFAULT_MODEL env var.
 */
async function callGeminiCompat(
  input: AnthropicCallInput & { apiKey: string },
): Promise<AnthropicCallResult> {
  const resolvedModel = resolveGeminiModel(input.model);
  const startedAt = Date.now();
  const base = (process.env.GEMINI_BASE_URL || 'https://generativelanguage.googleapis.com').replace(/\/+$/, '');
  const url = `${base}/v1beta/models/${resolvedModel}:generateContent?key=${input.apiKey}`;

  // Build Gemini content parts
  const contents: Array<{ role: string; parts: Array<{ text: string }> }> = [];
  if (input.systemPrompt) {
    contents.push({ role: 'user', parts: [{ text: `[System]: ${input.systemPrompt}` }] });
    contents.push({ role: 'model', parts: [{ text: 'Understood. I will follow these instructions.' }] });
  }
  contents.push({ role: 'user', parts: [{ text: input.prompt }] });

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), input.timeoutMs || 60000);
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        contents,
        generationConfig: {
          maxOutputTokens: input.maxTokens || 1024,
          temperature: typeof input.temperature === 'number' ? input.temperature : 0.7,
        },
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      const errText = await res.text().catch(() => '<unreadable error body>');
      return { success: false, model: resolvedModel, error: `Gemini API error ${res.status}: ${errText.slice(0, 400)}` };
    }
    const data = await res.json() as {
      candidates?: Array<{
        content?: { parts?: Array<{ text?: string }> };
        finishReason?: string;
      }>;
      usageMetadata?: { promptTokenCount?: number; candidatesTokenCount?: number; totalTokenCount?: number };
    };
    const textOut = data.candidates?.[0]?.content?.parts
      ?.filter(p => typeof p.text === 'string')
      .map(p => p.text as string)
      .join('') ?? '';
    const usage = data.usageMetadata ?? {};
    return {
      success: true,
      model: resolvedModel,
      messageId: `gemini-${Date.now()}`,
      stopReason: data.candidates?.[0]?.finishReason ?? 'STOP',
      output: textOut,
      usage: {
        inputTokens: usage.promptTokenCount ?? 0,
        outputTokens: usage.candidatesTokenCount ?? 0,
        totalTokens: usage.totalTokenCount ?? 0,
      },
      durationMs: Date.now() - startedAt,
    };
  } catch (err) {
    return {
      success: false,
      model: resolvedModel,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Date.now() - startedAt,
    };
  }
}

function resolveGeminiModel(input: string | undefined): string {
  const DEFAULT = process.env.GEMINI_DEFAULT_MODEL || 'gemini-2.0-flash-001';
  if (!input) return DEFAULT;
  if (input === 'haiku' || input === 'sonnet' || input === 'inherit') return DEFAULT;
  if (input === 'opus' || input === 'opus-4.7') return process.env.GEMINI_PRO_MODEL || 'gemini-2.5-pro';
  // Allow explicit 'gemini:model-name' prefix
  if (input.startsWith('gemini:')) return input.slice('gemini:'.length);
  // If it looks like a Gemini model name, pass through
  if (input.startsWith('gemini-')) return input;
  return DEFAULT;
}

/**
 * Ollama Cloud / OpenAI-compat provider — Tier-2 routing per ADR-026 + #1725.
 *
 * Endpoint: https://ollama.com/v1/chat/completions
 * Auth: Authorization: Bearer <OLLAMA_API_KEY>
 *
 * Translates the Anthropic-flavored input shape onto OpenAI chat-completions
 * and translates the response back so callers never see provider-specific
 * fields. Logical model names are mapped to Ollama Cloud defaults:
 *   - 'haiku'  / 'sonnet'  → 'gpt-oss:120b-cloud' (sensible single default)
 *   - 'opus'              → 'gpt-oss:120b-cloud' (no opus tier on Ollama)
 *   - explicit 'ollama:<model>' or bare provider-native name → passed through
 */
async function callOllamaCompat(
  input: AnthropicCallInput & { apiKey: string },
): Promise<AnthropicCallResult> {
  const model = resolveOllamaModel(input.model);
  const startedAt = Date.now();
  // OLLAMA_BASE_URL lets users point at local/self-hosted endpoints
  // (e.g. http://ruvultra:11434, http://localhost:11434) instead of
  // Ollama Cloud. Default is the public cloud endpoint.
  const base = (process.env.OLLAMA_BASE_URL || 'https://ollama.com').replace(/\/+$/, '');
  const url = `${base}/v1/chat/completions`;
  // Self-hosted endpoints typically don't need an Authorization header
  // (the daemon binds to 11434 with no auth by default), but Ollama Cloud
  // does. Send the bearer when the key is non-empty AND looks cloud-shaped.
  const sendAuth = input.apiKey && input.apiKey !== 'local';
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), input.timeoutMs || 60000);
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        ...(sendAuth ? { Authorization: `Bearer ${input.apiKey}` } : {}),
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model,
        max_tokens: input.maxTokens || 1024,
        temperature: typeof input.temperature === 'number' ? input.temperature : 0.7,
        messages: [
          ...(input.systemPrompt
            ? [{ role: 'system' as const, content: input.systemPrompt }]
            : []),
          { role: 'user' as const, content: input.prompt },
        ],
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      const errText = await res.text().catch(() => '<unreadable error body>');
      return { success: false, model, error: `Ollama API error ${res.status} at ${url}: ${errText.slice(0, 400)}` };
    }
    const data = (await res.json()) as {
      id?: string;
      model?: string;
      choices: Array<{
        message: { role: string; content: string };
        finish_reason?: string;
      }>;
      usage?: {
        prompt_tokens?: number;
        completion_tokens?: number;
        total_tokens?: number;
      };
    };
    const textOut = data.choices?.[0]?.message?.content ?? '';
    const usage = data.usage ?? {};
    return {
      success: true,
      model: data.model ?? model,
      messageId: data.id ?? `ollama-${Date.now()}`,
      stopReason: data.choices?.[0]?.finish_reason ?? 'end_turn',
      output: textOut,
      usage: {
        inputTokens: usage.prompt_tokens ?? 0,
        outputTokens: usage.completion_tokens ?? 0,
        totalTokens: usage.total_tokens ?? 0,
      },
      durationMs: Date.now() - startedAt,
    };
  } catch (err) {
    return {
      success: false,
      model,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Date.now() - startedAt,
    };
  }
}

/**
 * Generic OpenAI-compat caller for OpenRouter and other OpenAI-shaped
 * endpoints. #2042 — reporter (@ummcke00) configured OpenRouter via
 * config.yaml but agent_execute hardcoded the Anthropic fetch. This is
 * the same shape as `callOllamaCompat` but routes to a configurable
 * baseUrl + sends an OpenRouter-friendly default model when none is
 * specified. Logical model names (haiku/sonnet/opus) pass through —
 * OpenRouter accepts vendor-prefixed names like `anthropic/claude-3.5-sonnet`.
 */
async function callOpenAICompat(
  input: AnthropicCallInput & {
    apiKey: string;
    baseUrl: string;
    providerLabel: string;
    defaultModel: string;
  },
): Promise<AnthropicCallResult> {
  const model = resolveOpenAICompatModel(input.model, input.defaultModel);
  const startedAt = Date.now();
  const base = input.baseUrl.replace(/\/+$/, '');
  const url = `${base}/v1/chat/completions`;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), input.timeoutMs || 60000);
    const messages: Array<{ role: string; content: string }> = [];
    if (input.systemPrompt) messages.push({ role: 'system', content: input.systemPrompt });
    messages.push({ role: 'user', content: input.prompt });
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${input.apiKey}`,
        'content-type': 'application/json',
        // OpenRouter convention: identify the integrating app for analytics
        // and rate-limit tiering. Harmless on other OpenAI-compat backends.
        'HTTP-Referer': 'https://github.com/ruvnet/ruflo',
        'X-Title': 'Ruflo',
      },
      body: JSON.stringify({
        model,
        max_tokens: input.maxTokens || 1024,
        temperature: typeof input.temperature === 'number' ? input.temperature : 0.7,
        messages,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      const errText = await res.text().catch(() => '<unreadable error body>');
      return { success: false, model, error: `${input.providerLabel} API error ${res.status}: ${errText.slice(0, 400)}` };
    }
    const data = await res.json() as {
      id?: string;
      model?: string;
      choices: Array<{ message: { content: string }; finish_reason?: string }>;
      usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    };
    const textOut = data.choices?.[0]?.message?.content ?? '';
    const usage = data.usage ?? {};
    return {
      success: true,
      model: data.model || model,
      messageId: data.id,
      stopReason: data.choices?.[0]?.finish_reason ?? 'end_turn',
      output: textOut,
      usage: {
        inputTokens: usage.prompt_tokens ?? 0,
        outputTokens: usage.completion_tokens ?? 0,
        totalTokens: usage.total_tokens ?? 0,
      },
      durationMs: Date.now() - startedAt,
    };
  } catch (err) {
    return {
      success: false,
      model,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Date.now() - startedAt,
    };
  }
}

function resolveOpenAICompatModel(input: string | undefined, fallback: string): string {
  if (!input) return fallback;
  // VEXORA model routing: logical tier names → cost-optimal OpenRouter slugs.
  // These map to: haiku=fast/cheap → Gemini Flash,
  //               sonnet=balanced → DeepSeek Chat,
  //               opus=complex    → DeepSeek R1 (reasoning),
  //               inherit         → DeepSeek Chat (default).
  // Users can override any of these by passing a full OpenRouter slug directly.
  // Anthropic-prefixed slugs are passed through unchanged for backward compat.
  if (input === 'haiku') return process.env.RUFLO_MODEL_HAIKU || 'google/gemini-2.0-flash-001';
  if (input === 'sonnet' || input === 'inherit') return process.env.RUFLO_MODEL_SONNET || 'deepseek/deepseek-chat';
  if (input === 'opus' || input === 'opus-4.7') return process.env.RUFLO_MODEL_OPUS || 'deepseek/deepseek-r1';
  return input;
}

function resolveOllamaModel(input: string | undefined): string {
  const DEFAULT = 'gpt-oss:120b-cloud';
  if (!input) return DEFAULT;
  // Logical → cloud default
  if (input === 'haiku' || input === 'sonnet' || input === 'opus' || input === 'inherit') {
    return DEFAULT;
  }
  // Explicit provider prefix
  if (input.startsWith('ollama:')) return input.slice('ollama:'.length);
  // Bare name with cloud suffix (e.g. 'llama3:70b-cloud') passes through
  return input;
}

/**
 * Resolve a model identifier to an Anthropic model ID. Accepts:
 * - logical names: 'haiku', 'sonnet', 'opus', 'inherit'
 * - prefixed: 'anthropic:claude-sonnet-4-6'
 * - direct: 'claude-sonnet-4-6'
 */
export function resolveAnthropicModel(input: string | undefined): string {
  if (!input) return DEFAULT_ANTHROPIC_MODEL;
  if (input in MODEL_MAP) return MODEL_MAP[input];
  if (input.startsWith('anthropic:')) return input.slice('anthropic:'.length);
  return input;
}

export interface AgentExecuteInput {
  agentId: string;
  prompt: string;
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
  timeoutMs?: number;
}

export interface AgentExecuteResult {
  success: boolean;
  agentId: string;
  model?: string;
  messageId?: string;
  stopReason?: string;
  output?: string;
  usage?: { inputTokens: number; outputTokens: number; totalTokens: number };
  durationMs?: number;
  error?: string;
  remediation?: string;
  /**
   * ADR-149 iter 7 — present when the request was retried after a 429/5xx
   * via `nextCostOptimalAlternative`. Each entry records a model that
   * was tried and failed, in attempt order. The final `model` field is
   * the one that produced the surfaced result (success or final error).
   */
  fallbackHistory?: Array<{ modelId: string; error: string }>;
}

export async function executeAgentTask(input: AgentExecuteInput): Promise<AgentExecuteResult> {
  const store = loadAgentStore();
  const agent = store.agents[input.agentId];
  if (!agent) return { success: false, agentId: input.agentId, error: 'Agent not found' };
  if (agent.status === 'terminated') return { success: false, agentId: input.agentId, error: 'Agent has been terminated' };

  // ADR-149 iter 13 — first-call dispatch prefers `agent.modelId` (the
  // cost-optimal pick from the neural backend) over `MODEL_MAP[agent.model]`
  // when present. Before this fix the first attempt always used the tier
  // mapping; only the iter-7 fallback chain used modelId on retry, which
  // meant the cost-optimal pick was wasted unless the first call failed
  // with a 429/5xx.
  //
  // Rules:
  //   - agent.modelId is set AND it's a non-Anthropic slug (e.g.
  //     'inclusionai/ling-2.6-flash', 'openai/gpt-4.1') → dispatch
  //     directly via that id. callAnthropicMessages forwards non-Anthropic
  //     ids through OpenRouter (#2042), so this gets us the cost-optimal
  //     model on attempt 1.
  //   - agent.modelId starts with 'anthropic/' → strip the prefix, use the
  //     bare Anthropic id (e.g. 'anthropic/claude-haiku-4.5' → 'claude-haiku-4.5').
  //   - agent.modelId is unset (no neural backend fired) → fall back to the
  //     legacy tier-mapped MODEL_MAP path. Existing behaviour preserved.
  let firstCallModel: string;
  if (agent.modelId) {
    firstCallModel = agent.modelId.startsWith('anthropic/')
      ? agent.modelId.slice('anthropic/'.length)
      : agent.modelId;
  } else {
    firstCallModel = resolveAnthropicModel(agent.model || 'sonnet');
  }
  // Kept for legacy error-path remediation message + final-result `model` field
  // (returned when the request fully fails with no successful retry).
  const anthropicModel = firstCallModel;
  const systemPrompt = input.systemPrompt ||
    `You are a ${agent.agentType} agent operating as part of a Ruflo swarm. ` +
    `Agent ID: ${input.agentId}. Domain: ${agent.domain ?? 'general'}. ` +
    `Respond directly and stay focused on the task. If you need information you don't have, state that explicitly.`;

  agent.status = 'busy';
  agent.taskCount = (agent.taskCount || 0) + 1;
  saveAgentStore(store);

  const startedAt = Date.now();

  // #2042 — delegate to callAnthropicMessages so the v3 provider router
  // (Anthropic / Ollama / OpenRouter) governs which backend is hit.
  let result = await callAnthropicMessages({
    model: anthropicModel,
    prompt: input.prompt,
    systemPrompt,
    maxTokens: input.maxTokens,
    temperature: input.temperature,
    timeoutMs: input.timeoutMs,
  });

  // ADR-149 iter 7 — fallback chain on retryable failures (429, 5xx,
  // timeout). When the cost-optimal neural backend picked a specific
  // model id and that model fails for a transient reason, fall back to
  // the next-cheapest candidate that clears the quality bar. Budget is
  // bounded by CLAUDE_FLOW_ROUTER_FALLBACK_MAX_RETRIES (default 1) so
  // upstream outages don't cause retry storms.
  const fallbackBudget = Math.max(0, parseInt(process.env.CLAUDE_FLOW_ROUTER_FALLBACK_MAX_RETRIES ?? '1', 10) || 1);
  const fallbackHistory: Array<{ modelId: string; error: string }> = [];
  if (!result.success && agent.modelId && fallbackBudget > 0) {
    const isRetryable = /\b(429|500|502|503|504|timeout|ECONNRESET|ETIMEDOUT)\b/i.test(result.error ?? '');
    if (isRetryable) {
      try {
        const { nextCostOptimalAlternative } = await import('../ruvector/neural-router.js');
        // ADR-149 iter 9 — delegate to the shared task-embedder LRU. The
        // pipeline + cache are shared with agent-tools.ts, so the embedding
        // for this prompt is almost always already cached from the initial
        // routing decision (no extra inference cost in steady state).
        const { embedTaskWithCache } = await import('../ruvector/task-embedder.js');
        const embedding = await embedTaskWithCache(input.prompt);
        if (embedding) {
          const excludeIds: string[] = [agent.modelId];
          for (let attempt = 0; attempt < fallbackBudget && !result.success; attempt++) {
            fallbackHistory.push({ modelId: excludeIds[excludeIds.length - 1], error: result.error ?? '' });
            const alt = await nextCostOptimalAlternative(embedding, excludeIds);
            if (!alt || !alt.modelId) break;
            excludeIds.push(alt.modelId);
            const altResult = await callAnthropicMessages({
              model: alt.modelId,
              prompt: input.prompt,
              systemPrompt,
              maxTokens: input.maxTokens,
              temperature: input.temperature,
              timeoutMs: input.timeoutMs,
            });
            // Record the model that ACTUALLY answered (or errored). On success,
            // update agent.modelId so downstream observers see the retry winner.
            agent.modelId = alt.modelId;
            result = altResult;
          }
        }
      } catch {
        // Fallback chain is best-effort — preserve the original error result.
      }
    }
  }

  agent.status = 'idle';

  // ADR-149 — close the bandit feedback loop. `recordModelOutcome` updates
  // the Beta(α,β) prior for the agent's tier so the Thompson sampler learns
  // from production traffic instead of staying frozen at install-day priors.
  // This is best-effort: any error here must NOT break the agent execution.
  // For now, "success" = the model returned a response without an API error.
  // A finer-grained signal (user-accepted output / regression-detected) is a
  // follow-up; this commit closes the bandit's basic learning loop.
  try {
    const { recordModelOutcome, recordModelOutcomeByModelId } = await import('../ruvector/model-router.js');
    // Bandit priors are keyed on the 3 canonical tiers (haiku/sonnet/opus/inherit);
    // collapse opus-4.7 → opus before recording so the bandit's per-tier Beta
    // updates correctly.
    const tier: 'haiku' | 'sonnet' | 'opus' | 'inherit' =
      agent.model === 'opus-4.7' ? 'opus' :
      (agent.model as 'haiku' | 'sonnet' | 'opus' | 'inherit' | undefined) ?? 'sonnet';
    const outcome: 'success' | 'failure' = result.success ? 'success' : 'failure';
    recordModelOutcome(input.prompt, tier, outcome);
    // ADR-149 — also write to the shadow per-modelId priors when the cost-
    // optimal neural backend picked a concrete model id. Selection logic
    // still uses tier priors, but the per-modelId data accumulates so a
    // future refactor can switch the selector over.
    if (agent.modelId) {
      recordModelOutcomeByModelId(input.prompt, agent.modelId, outcome);
    }
    // ADR-149 iter 17 — close the production-data side of the feedback loop.
    // The trajectory recorder (CLAUDE_FLOW_ROUTER_TRAJECTORY=1) writes
    // per-decision rows to .swarm/model-router-trajectories.jsonl from the
    // model-router itself. Now we ALSO write outcome rows here so future
    // training (scripts/train-from-trajectories.mjs, follow-up) can pair
    // decision+outcome by task_hash and produce DRACO-shaped retraining
    // rows from real production traffic. quality = 1.0 on success, 0.0 on
    // failure (coarse signal; finer-grained quality from user ratings or
    // regression-detection is a separate hook).
    if (process.env.CLAUDE_FLOW_ROUTER_TRAJECTORY === '1') {
      try {
        const { recordTrajectoryOutcome } = await import('../ruvector/router-trajectory.js');
        const scores: Record<string, number> | undefined = agent.modelId
          ? { [agent.modelId]: outcome === 'success' ? 1.0 : 0.0 }
          : undefined;
        // iter 31 — pass token usage + modelId so the recorder can compute
        // USD spend at write time. Consumers (`router decisions`, cost-
        // savings reports) get cost without their own price table.
        recordTrajectoryOutcome({
          task: input.prompt,
          quality: outcome === 'success' ? 1.0 : 0.0,
          scores,
          source: 'agent-execute',
          tokens: result.usage ? { input: result.usage.inputTokens, output: result.usage.outputTokens } : undefined,
          modelId: agent.modelId,
        });
      } catch { /* never break execution */ }
    }
    // ADR-150 weight-eft capture seam — the ONLY place a run's full outcome is
    // known here: prompt (issue), assistant transcript, model, tier, and a
    // resolved PROXY. Gated behind CLAUDE_FLOW_RUN_TRANSCRIPTS=1 (off by
    // default; PII/retention surface, mirrors the router trajectory recorder).
    // HONESTY: `resolved` here is the WEAKEST proxy — 'api-success' means only
    // that the model returned without an API error, NOT that the output is
    // correct (ruflo has no SWE-bench gold oracle). model_patch is '' because
    // this single-shot execute path produces no unified diff. Both facts are
    // stamped so no downstream weight-eft export mistakes this for gold data.
    if (process.env.CLAUDE_FLOW_RUN_TRANSCRIPTS === '1') {
      try {
        const { recordRunTranscript, tierForModel } = await import('../ruvector/run-transcript-recorder.js');
        const modelId = agent.modelId ?? String(agent.model ?? 'unknown');
        const messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = [];
        if (systemPrompt) messages.push({ role: 'system', content: systemPrompt });
        messages.push({ role: 'user', content: input.prompt });
        if (result.success && typeof result.output === 'string') {
          messages.push({ role: 'assistant', content: result.output });
        }
        recordRunTranscript({
          task: input.prompt,
          model: modelId,
          tier: tierForModel(modelId),
          resolved: outcome === 'success',
          resolvedSource: 'api-success',
          messages,
          source: 'agent-execute',
          tokens: result.usage ? { input: result.usage.inputTokens, output: result.usage.outputTokens } : undefined,
        });
      } catch { /* never break execution */ }
    }
  } catch {
    // Silent — bandit feedback must never block routing.
  }

  if (result.success) {
    const out: AgentExecuteResult = {
      success: true,
      agentId: input.agentId,
      messageId: result.messageId,
      model: result.model,
      stopReason: result.stopReason,
      output: result.output,
      usage: result.usage,
      durationMs: result.durationMs ?? Date.now() - startedAt,
      ...(fallbackHistory.length > 0 ? { fallbackHistory } : {}),
    };
    agent.lastResult = out as unknown as Record<string, unknown>;
    saveAgentStore(store);
    return out;
  }

  saveAgentStore(store);
  // No-provider-configured error → surface actionable remediation with VEXORA priority order.
  const noProvider = (result.error || '').includes('No LLM provider configured');
  return {
    success: false,
    agentId: input.agentId,
    model: anthropicModel,
    error: result.error || 'agent_execute failed',
    durationMs: result.durationMs ?? Date.now() - startedAt,
    ...(fallbackHistory.length > 0 ? { fallbackHistory } : {}),
    ...(noProvider && {
      remediation:
        'VEXORA Provider Setup: Set OPENROUTER_API_KEY (primary), GEMINI_API_KEY (secondary), ' +
        'OLLAMA_API_KEY (local), or ANTHROPIC_API_KEY (optional fallback). ' +
        'Or set RUFLO_PROVIDER=openrouter|gemini|ollama|anthropic to force a specific provider. ' +
        'Recommended: export OPENROUTER_API_KEY=<your-key> RUFLO_PROVIDER=openrouter',
    }),
  };
}

