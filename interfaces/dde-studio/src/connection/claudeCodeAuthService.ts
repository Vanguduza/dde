import type * as vscode from "vscode";
import {
  CLAUDE_CODE_DOCS_AUTH,
  extractClaudeOAuthToken,
  isClaudeOAuthToken,
  resolveClaudeCodeAuthState,
  type ClaudeCodeAuthState,
} from "../../shared/claudeAuth";
import {
  findClaudeExecutable,
  queryClaudeAuthStatus,
  startClaudeAuthLogin,
  startClaudeSetupToken,
} from "../../shared/claudeCli";

const OAUTH_TOKEN_KEY = "dde.studio.claudeCode.oauthToken";
const META_KEY = "dde.studio.claudeCode.meta";

interface StoredMeta {
  email?: string;
  pendingSource?: "claude_auth_login" | "claude_setup_token";
}

/**
 * Claude Code subscription auth for the extension host.
 * Tokens live in SecretStorage only — never dde.studio.* settings.
 */
export class ClaudeCodeAuthService {
  private pendingSource?: "claude_auth_login" | "claude_setup_token";
  private cachedEmail?: string;

  constructor(private readonly secrets: vscode.SecretStorage) {}

  async getState(): Promise<ClaudeCodeAuthState> {
    const token = await this.secrets.get(OAUTH_TOKEN_KEY);
    const hasStoredSetupToken = isClaudeOAuthToken(token);
    const meta = await this.readMeta();
    const cliFound = Boolean(findClaudeExecutable());

    let statusJson;
    if (cliFound) {
      try {
        const probed = await queryClaudeAuthStatus();
        statusJson = probed.status;
        if (probed.status?.email) {
          this.cachedEmail = probed.status.email;
        }
      } catch {
        // keep offline resolution
      }
    }

    return resolveClaudeCodeAuthState({
      cliFound,
      statusJson,
      hasStoredSetupToken,
      tokenRef: hasStoredSetupToken ? "secret_storage" : undefined,
      pendingSource: this.pendingSource ?? meta.pendingSource,
    });
  }

  async startLogin(email?: string): Promise<{ ok: boolean; message: string }> {
    const result = startClaudeAuthLogin({ email });
    if (!result.ok) {
      return {
        ok: false,
        message: result.error ?? `CLI login failed. ${CLAUDE_CODE_DOCS_AUTH}`,
      };
    }
    this.pendingSource = "claude_auth_login";
    await this.writeMeta({
      email: email?.trim() || this.cachedEmail,
      pendingSource: "claude_auth_login",
    });
    return {
      ok: true,
      message:
        "Claude Code CLI login started. Complete browser sign-in (email / GitHub / Google), then Verify.",
    };
  }

  async startSetupToken(): Promise<{ ok: boolean; message: string }> {
    const result = startClaudeSetupToken();
    if (!result.ok) {
      return {
        ok: false,
        message: result.error ?? `setup-token failed. ${CLAUDE_CODE_DOCS_AUTH}`,
      };
    }
    this.pendingSource = "claude_setup_token";
    await this.writeMeta({ pendingSource: "claude_setup_token" });
    return {
      ok: true,
      message:
        "claude setup-token started. Copy the printed sk-ant-oat01-… token and paste it via Store setup-token.",
    };
  }

  async storeSetupToken(
    raw: string,
  ): Promise<{ ok: boolean; message: string }> {
    const token = extractClaudeOAuthToken(raw)?.trim() ?? raw.trim();
    if (!isClaudeOAuthToken(token)) {
      return {
        ok: false,
        message:
          "Expected a Claude Code OAuth token (sk-ant-oat01-…). API keys belong under API key backup.",
      };
    }
    await this.secrets.store(OAUTH_TOKEN_KEY, token);
    this.pendingSource = undefined;
    await this.writeMeta({
      email: this.cachedEmail,
      pendingSource: undefined,
    });
    return {
      ok: true,
      message: "Setup-token stored in VS Code SecretStorage.",
    };
  }

  async clearSetupToken(): Promise<void> {
    await this.secrets.delete(OAUTH_TOKEN_KEY);
  }

  async verify(): Promise<ClaudeCodeAuthState> {
    const state = await this.getState();
    if (state.kind === "verified_cli_login" || state.kind === "stored_setup_token") {
      this.pendingSource = undefined;
      await this.writeMeta({
        email: state.kind === "verified_cli_login" ? state.email : undefined,
        pendingSource: undefined,
      });
    }
    return state;
  }

  private async readMeta(): Promise<StoredMeta> {
    try {
      const raw = await this.secrets.get(META_KEY);
      if (!raw) {
        return {};
      }
      return JSON.parse(raw) as StoredMeta;
    } catch {
      return {};
    }
  }

  private async writeMeta(meta: StoredMeta): Promise<void> {
    await this.secrets.store(META_KEY, JSON.stringify(meta));
  }
}
