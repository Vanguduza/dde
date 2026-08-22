import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  CLAUDE_CODE_DOCS_AUTH,
  claudeCodeAuthStatusLabel,
  extractClaudeOAuthToken,
  extractJsonObject,
  isAnthropicApiKey,
  isClaudeCodeSignedIn,
  isClaudeOAuthToken,
  parseClaudeAuthStatusJson,
  resolveClaudeCodeAuthState,
} from "./claudeAuth";

describe("claudeAuth token shapes", () => {
  it("accepts setup-token OAuth prefix and rejects API keys", () => {
    const oauth = "sk-ant-oat01-abcdefghijklmnopqrstuvwxyz0123456789";
    const api = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789";
    assert.equal(isClaudeOAuthToken(oauth), true);
    assert.equal(isClaudeOAuthToken(api), false);
    assert.equal(isAnthropicApiKey(api), true);
    assert.equal(isAnthropicApiKey(oauth), false);
  });

  it("extracts oauth token from noisy setup-token output", () => {
    const text =
      "Approve in browser…\nYour token:\nsk-ant-oat01-AbCdEfGhIjKlMnOpQrStUvWxYz\nDone.";
    assert.equal(
      extractClaudeOAuthToken(text),
      "sk-ant-oat01-AbCdEfGhIjKlMnOpQrStUvWxYz",
    );
  });
});

describe("parseClaudeAuthStatusJson", () => {
  it("parses documented auth status fields", () => {
    const raw = `{
  "loggedIn": true,
  "authMethod": "claude.ai",
  "apiProvider": "firstParty",
  "email": "user@example.com",
  "orgId": "org-1",
  "orgName": "Acme",
  "subscriptionType": "max"
}`;
    const parsed = parseClaudeAuthStatusJson(raw);
    assert.ok(parsed);
    assert.equal(parsed!.loggedIn, true);
    assert.equal(parsed!.email, "user@example.com");
    assert.equal(parsed!.subscriptionType, "max");
    assert.equal(parsed!.authMethod, "claude.ai");
  });

  it("extracts JSON when CLI prints a banner first", () => {
    const noisy = "Checking…\n{\"loggedIn\":false}\n";
    assert.equal(extractJsonObject(noisy), '{"loggedIn":false}');
    const parsed = parseClaudeAuthStatusJson(noisy);
    assert.equal(parsed?.loggedIn, false);
  });

  it("returns undefined for non-JSON", () => {
    assert.equal(parseClaudeAuthStatusJson("Not logged in."), undefined);
  });
});

describe("resolveClaudeCodeAuthState", () => {
  it("never invents signed-in without evidence", () => {
    const state = resolveClaudeCodeAuthState({
      cliFound: true,
      hasStoredSetupToken: false,
    });
    assert.equal(state.kind, "none");
    assert.equal(isClaudeCodeSignedIn(state), false);
  });

  it("prefers verified CLI login over stored token", () => {
    const state = resolveClaudeCodeAuthState({
      cliFound: true,
      hasStoredSetupToken: true,
      tokenRef: "secret_storage",
      statusJson: {
        loggedIn: true,
        email: "a@b.co",
        subscriptionType: "pro",
        authMethod: "claude.ai",
      },
    });
    assert.equal(state.kind, "verified_cli_login");
    if (state.kind === "verified_cli_login") {
      assert.equal(state.email, "a@b.co");
    }
    assert.match(claudeCodeAuthStatusLabel(state), /Signed in/);
  });

  it("accepts stored setup-token only when flag is set", () => {
    const state = resolveClaudeCodeAuthState({
      cliFound: false,
      hasStoredSetupToken: true,
      tokenRef: "wincred:DDE/ClaudeCodeOAuthToken",
    });
    assert.equal(state.kind, "stored_setup_token");
    assert.equal(isClaudeCodeSignedIn(state), true);
  });

  it("blocks with docs URL when CLI missing and no token", () => {
    const state = resolveClaudeCodeAuthState({
      cliFound: false,
      hasStoredSetupToken: false,
    });
    assert.equal(state.kind, "blocked");
    if (state.kind === "blocked") {
      assert.equal(state.docsUrl, CLAUDE_CODE_DOCS_AUTH);
      assert.match(state.reason, /CLI not found/i);
    }
  });

  it("keeps pending while browser login in flight", () => {
    const state = resolveClaudeCodeAuthState({
      cliFound: true,
      hasStoredSetupToken: false,
      pendingSource: "claude_auth_login",
      statusJson: { loggedIn: false },
    });
    assert.equal(state.kind, "pending_cli_login");
  });
});
