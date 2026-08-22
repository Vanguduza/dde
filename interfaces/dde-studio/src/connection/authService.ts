import type * as vscode from "vscode";
import type { AuthState } from "../../shared/authTypes";

export type { AuthState };

/**
 * Session credential seam for Gateway Bearer/OIDC (Ch.15.2, S3).
 * Token MUST live in SecretStorage, never in dde.studio.* settings.
 */
const SESSION_TOKEN_KEY = "dde.studio.sessionToken";

export class AuthService {
  constructor(private readonly secrets: vscode.SecretStorage) {}

  async getState(): Promise<AuthState> {
    const token = await this.secrets.get(SESSION_TOKEN_KEY);
    if (token) {
      return { kind: "session", hasToken: true };
    }
    return { kind: "unauthenticated" };
  }

  async getSessionToken(): Promise<string | undefined> {
    return this.secrets.get(SESSION_TOKEN_KEY);
  }

  async setSessionToken(token: string): Promise<void> {
    const trimmed = token.trim();
    if (!trimmed) {
      await this.clearSession();
      return;
    }
    await this.secrets.store(SESSION_TOKEN_KEY, trimmed);
  }

  async clearSession(): Promise<void> {
    await this.secrets.delete(SESSION_TOKEN_KEY);
  }
}
