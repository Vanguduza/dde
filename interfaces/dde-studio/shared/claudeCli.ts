/**
 * Spawn helpers for official Claude Code CLI auth commands.
 * Live OAuth is skipped in CI — unit-test parsers/state machine only.
 */

import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import {
  CLAUDE_CODE_DOCS_AUTH,
  parseClaudeAuthStatusJson,
  type ClaudeAuthStatusJson,
} from "./claudeAuth";

export interface ClaudeCliRunResult {
  exitCode: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
}

/** Native Windows installer layout: %USERPROFILE%\.local\bin\claude.exe */
export function claudeNativeBinPath(
  env: NodeJS.ProcessEnv = process.env,
): string | undefined {
  if (process.platform !== "win32") {
    return undefined;
  }
  const home = env.USERPROFILE ?? env.HOME;
  if (!home) {
    return undefined;
  }
  return path.join(home, ".local", "bin", "claude.exe");
}

export function findClaudeExecutable(
  env: NodeJS.ProcessEnv = process.env,
): string | undefined {
  const pathEnv = env.PATH ?? env.Path ?? "";
  const parts = pathEnv.split(path.delimiter).filter(Boolean);
  const names =
    process.platform === "win32"
      ? ["claude.exe", "claude.cmd", "claude"]
      : ["claude"];

  for (const dir of parts) {
    for (const name of names) {
      const candidate = path.join(dir.replace(/^"|"$/g, ""), name);
      try {
        if (fs.existsSync(candidate)) {
          return candidate;
        }
      } catch {
        // skip
      }
    }
  }

  const native = claudeNativeBinPath(env);
  if (native && fs.existsSync(native)) {
    return native;
  }

  if (process.platform === "win32" && env.LOCALAPPDATA) {
    const npmClaude = path.join(env.LOCALAPPDATA, "npm", "claude.cmd");
    if (fs.existsSync(npmClaude)) {
      return npmClaude;
    }
  }

  if (process.platform === "win32" && env.APPDATA) {
    const npmExe = path.join(env.APPDATA, "npm", "claude.exe");
    if (fs.existsSync(npmExe)) {
      return npmExe;
    }
  }

  return undefined;
}

export function runClaudeCli(
  args: string[],
  opts?: { timeoutMs?: number; env?: NodeJS.ProcessEnv },
): Promise<ClaudeCliRunResult> {
  const timeoutMs = opts?.timeoutMs ?? 45_000;
  const claude = findClaudeExecutable(opts?.env ?? process.env);
  if (!claude) {
    return Promise.resolve({
      exitCode: null,
      stdout: "",
      stderr: `Claude Code CLI not found. Docs: ${CLAUDE_CODE_DOCS_AUTH}`,
      timedOut: false,
    });
  }

  return new Promise((resolve) => {
    const child = spawn(claude, args, {
      env: opts?.env ?? process.env,
      windowsHide: true,
      shell: process.platform === "win32" && claude.endsWith(".cmd"),
    });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      try {
        child.kill();
      } catch {
        // ignore
      }
      resolve({ exitCode: null, stdout, stderr, timedOut: true });
    }, timeoutMs);

    child.stdout?.on("data", (chunk: Buffer | string) => {
      stdout += String(chunk);
    });
    child.stderr?.on("data", (chunk: Buffer | string) => {
      stderr += String(chunk);
    });
    child.on("error", (err) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      resolve({
        exitCode: null,
        stdout,
        stderr: err.message,
        timedOut: false,
      });
    });
    child.on("close", (code) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      resolve({
        exitCode: code,
        stdout,
        stderr,
        timedOut: false,
      });
    });
  });
}

export async function queryClaudeAuthStatus(
  env?: NodeJS.ProcessEnv,
): Promise<{
  cliFound: boolean;
  status?: ClaudeAuthStatusJson;
  raw: string;
  error?: string;
}> {
  const claude = findClaudeExecutable(env);
  if (!claude) {
    return {
      cliFound: false,
      raw: "",
      error: `Claude Code CLI not found. Docs: ${CLAUDE_CODE_DOCS_AUTH}`,
    };
  }

  const result = await runClaudeCli(["auth", "status"], { env });
  const combined = result.stdout || result.stderr;
  const status = parseClaudeAuthStatusJson(combined);
  if (status) {
    return { cliFound: true, status, raw: combined };
  }

  if (result.timedOut) {
    return { cliFound: true, raw: combined, error: "claude auth status timed out" };
  }

  if (result.exitCode === 0) {
    return {
      cliFound: true,
      status: { loggedIn: true },
      raw: combined,
    };
  }

  return {
    cliFound: true,
    status: { loggedIn: false },
    raw: combined,
    error: result.stderr.trim() || "Not logged in.",
  };
}

/** Open interactive login in a detached process (browser OAuth). */
export function startClaudeAuthLogin(opts?: {
  email?: string;
  env?: NodeJS.ProcessEnv;
}): { ok: boolean; error?: string } {
  const claude = findClaudeExecutable(opts?.env);
  if (!claude) {
    return {
      ok: false,
      error: `Claude Code CLI not found. Docs: ${CLAUDE_CODE_DOCS_AUTH}`,
    };
  }

  const args = ["auth", "login"];
  if (opts?.email?.trim()) {
    args.push("--email", opts.email.trim());
  }

  try {
    const child = spawn(claude, args, {
      detached: true,
      stdio: "ignore",
      env: opts?.env ?? process.env,
      shell: process.platform === "win32" && claude.endsWith(".cmd"),
      windowsHide: false,
    });
    child.unref();
    return { ok: true };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export function startClaudeSetupToken(opts?: {
  env?: NodeJS.ProcessEnv;
}): { ok: boolean; error?: string } {
  const claude = findClaudeExecutable(opts?.env);
  if (!claude) {
    return {
      ok: false,
      error: `Claude Code CLI not found. Docs: ${CLAUDE_CODE_DOCS_AUTH}`,
    };
  }

  try {
    const child = spawn(claude, ["setup-token"], {
      detached: true,
      stdio: "ignore",
      env: opts?.env ?? process.env,
      shell: process.platform === "win32" && claude.endsWith(".cmd"),
      windowsHide: false,
    });
    child.unref();
    return { ok: true };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
