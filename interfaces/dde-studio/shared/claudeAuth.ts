/**
 * Claude Code subscription auth — official Anthropic mechanisms only.
 *
 * Docs:
 * - https://code.claude.com/docs/en/authentication
 * - https://code.claude.com/docs/en/cli-reference
 *
 * Anthropic does **not** publish a third-party OAuth client for Claude Code
 * subscriptions. Email / GitHub / Google IdP happen inside the browser flow
 * opened by `claude auth login` or `claude setup-token`. Device-code (RFC 8628)
 * is not supported (open request against anthropics/claude-code).
 */

export const CLAUDE_CODE_DOCS_AUTH =
  "https://code.claude.com/docs/en/authentication";
export const CLAUDE_CODE_DOCS_CLI =
  "https://code.claude.com/docs/en/cli-reference";
/** Legacy bookmark; real sign-in is via CLI, not opening this URL alone. */
export const CLAUDE_CODE_LOGIN_URL = "https://claude.ai/login";

export const CLAUDE_CODE_OAUTH_TOKEN_PREFIX = "sk-ant-oat01-";
export const CLAUDE_API_KEY_PREFIX = "sk-ant-api03-";

export type ClaudeSessionStatus =
  | "none"
  | "pending_cli_login"
  | "verified_cli_login"
  | "stored_setup_token"
  | "blocked";

export type ClaudeAuthMode = "subscription" | "api_key_backup";

/** Machine-readable slice of `claude auth status` JSON. */
export interface ClaudeAuthStatusJson {
  loggedIn: boolean;
  authMethod?: string | null;
  apiProvider?: string | null;
  email?: string | null;
  orgId?: string | null;
  orgName?: string | null;
  subscriptionType?: string | null;
  apiKeySource?: string | null;
}

export type ClaudeCodeAuthState =
  | { kind: "none" }
  | {
      kind: "pending_cli_login";
      source: "claude_auth_login" | "claude_setup_token";
    }
  | {
      kind: "verified_cli_login";
      email?: string;
      authMethod?: string;
      subscriptionType?: string;
      orgName?: string;
    }
  | {
      kind: "stored_setup_token";
      /** Opaque ref or "secret_storage" — never the raw token. */
      tokenRef: string;
      email?: string;
    }
  | {
      kind: "blocked";
      reason: string;
      docsUrl: string;
    };

const OAUTH_TOKEN_RE = /sk-ant-oat01-[A-Za-z0-9\-_]+/;
const API_KEY_RE = /sk-ant-api03-[A-Za-z0-9\-_]+/;

export function isClaudeOAuthToken(value: string | undefined | null): boolean {
  if (!value) {
    return false;
  }
  const t = value.trim();
  return OAUTH_TOKEN_RE.test(t) && !API_KEY_RE.test(t);
}

export function isAnthropicApiKey(value: string | undefined | null): boolean {
  if (!value) {
    return false;
  }
  return API_KEY_RE.test(value.trim());
}

export function extractClaudeOAuthToken(
  text: string | undefined | null,
): string | undefined {
  if (!text) {
    return undefined;
  }
  const m = text.match(OAUTH_TOKEN_RE);
  return m?.[0];
}

/** Extract first JSON object from CLI stdout/stderr (handles banners). */
export function extractJsonObject(text: string): string | undefined {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start < 0 || end <= start) {
    return undefined;
  }
  return text.slice(start, end + 1);
}

export function parseClaudeAuthStatusJson(
  text: string,
): ClaudeAuthStatusJson | undefined {
  const json = extractJsonObject(text);
  if (!json) {
    return undefined;
  }
  try {
    const parsed = JSON.parse(json) as Record<string, unknown>;
    if (typeof parsed.loggedIn !== "boolean") {
      return undefined;
    }
    return {
      loggedIn: parsed.loggedIn,
      authMethod:
        parsed.authMethod === null || parsed.authMethod === undefined
          ? null
          : String(parsed.authMethod),
      apiProvider:
        parsed.apiProvider === null || parsed.apiProvider === undefined
          ? null
          : String(parsed.apiProvider),
      email:
        parsed.email === null || parsed.email === undefined
          ? null
          : String(parsed.email),
      orgId:
        parsed.orgId === null || parsed.orgId === undefined
          ? null
          : String(parsed.orgId),
      orgName:
        parsed.orgName === null || parsed.orgName === undefined
          ? null
          : String(parsed.orgName),
      subscriptionType:
        parsed.subscriptionType === null ||
        parsed.subscriptionType === undefined
          ? null
          : String(parsed.subscriptionType),
      apiKeySource:
        parsed.apiKeySource === null || parsed.apiKeySource === undefined
          ? null
          : String(parsed.apiKeySource),
    };
  } catch {
    return undefined;
  }
}

/**
 * Auth state machine: prefer verified CLI status; never invent signed-in.
 * A stored setup-token is only accepted when shape-validated.
 */
export function resolveClaudeCodeAuthState(input: {
  cliFound: boolean;
  statusJson?: ClaudeAuthStatusJson;
  /** True when a shape-validated setup-token exists in secure storage. */
  hasStoredSetupToken: boolean;
  tokenRef?: string;
  pendingSource?: "claude_auth_login" | "claude_setup_token";
  cliMissingMessage?: string;
}): ClaudeCodeAuthState {
  if (input.statusJson?.loggedIn) {
    return {
      kind: "verified_cli_login",
      email: input.statusJson.email ?? undefined,
      authMethod: input.statusJson.authMethod ?? undefined,
      subscriptionType: input.statusJson.subscriptionType ?? undefined,
      orgName: input.statusJson.orgName ?? undefined,
    };
  }

  if (input.hasStoredSetupToken) {
    return {
      kind: "stored_setup_token",
      tokenRef: input.tokenRef ?? "secret_storage",
      email: input.statusJson?.email ?? undefined,
    };
  }

  if (!input.cliFound) {
    return {
      kind: "blocked",
      reason:
        input.cliMissingMessage ??
        "Claude Code CLI not found on PATH. Install Claude Code to sign in with a subscription.",
      docsUrl: CLAUDE_CODE_DOCS_AUTH,
    };
  }

  if (input.pendingSource) {
    return { kind: "pending_cli_login", source: input.pendingSource };
  }

  return { kind: "none" };
}

export function claudeCodeAuthStatusLabel(state: ClaudeCodeAuthState): string {
  switch (state.kind) {
    case "verified_cli_login": {
      const who = state.email ?? "account";
      const plan = state.subscriptionType
        ? ` (${state.subscriptionType})`
        : "";
      return `Signed in — ${who}${plan}`;
    }
    case "stored_setup_token":
      return `Setup-token stored (${state.tokenRef})`;
    case "pending_cli_login":
      return "Pending — complete browser login, then verify";
    case "blocked":
      return `CLI missing — ${state.reason}`;
    default:
      return "Not signed in";
  }
}

export function isClaudeCodeSignedIn(state: ClaudeCodeAuthState): boolean {
  return (
    state.kind === "verified_cli_login" || state.kind === "stored_setup_token"
  );
}

/** Escape for HTML attribute/text (UI helpers; keep dependency-free). */
function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Shared Claude Code auth banner for Connection + Mission Control.
 * Shows signed-in only for verified CLI login or stored setup-token.
 */
export function claudeCodeAuthBannerHtml(
  state: ClaudeCodeAuthState = { kind: "none" },
): string {
  const signedIn = isClaudeCodeSignedIn(state);
  const cliMissing = state.kind === "blocked";
  const statusPill = signedIn
    ? `<span class="pill ok">${esc(claudeCodeAuthStatusLabel(state))}</span>`
    : cliMissing
      ? `<span class="pill warn">CLI missing</span>`
      : state.kind === "pending_cli_login"
        ? `<span class="pill warn">Pending</span>`
        : `<span class="pill warn">Sign in</span>`;

  const detail =
    state.kind === "blocked"
      ? `<p class="muted" style="margin:8px 0 0">${esc(state.reason)} Use <strong>Install Claude Code CLI</strong>, then Sign in. Docs: <a href="${esc(state.docsUrl)}">${esc(state.docsUrl)}</a></p>`
      : state.kind === "verified_cli_login" && state.authMethod
        ? `<p class="muted" style="margin:8px 0 0">Verified via <code>claude auth status</code> (${esc(state.authMethod)}).</p>`
        : state.kind === "stored_setup_token"
          ? `<p class="muted" style="margin:8px 0 0">Long-lived token from <code>claude setup-token</code> in secure storage.</p>`
          : state.kind === "pending_cli_login"
            ? `<p class="muted" style="margin:8px 0 0">Complete browser OAuth, then Verify.</p>`
            : `<p class="muted" style="margin:8px 0 0">Official path: <code>claude auth login</code> / <code>claude setup-token</code>. No third-party OAuth client.</p>`;

  const installBtn = cliMissing
    ? `<button type="button" class="secondary" data-cmd="installClaudeCodeCli">Install Claude Code CLI</button>`
    : "";

  return `
  <div class="banner" role="status">
    <div class="meta-row">
      <span class="pill">subscription</span>
      ${statusPill}
    </div>
    ${detail}
    <div class="row" style="margin-top:8px">
      ${installBtn}
      <button type="button" class="secondary" data-cmd="openClaudeCodeSignIn">Sign in with Claude Code CLI</button>
      <button type="button" class="secondary" data-cmd="verifyClaudeCodeAuth">Verify</button>
      <button type="button" class="secondary" data-cmd="storeClaudeCodeSetupToken">Store setup-token</button>
      <button type="button" class="secondary" data-cmd="openClaudeCodeApiKeyBackup">API key backup</button>
    </div>
  </div>`;
}
