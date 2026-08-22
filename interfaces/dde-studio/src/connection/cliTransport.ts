/**
 * S1 transport bridge (planning doc §3.1a) — now live for read paths.
 *
 * `dde … --json` ships in interfaces/cli (all four subcommands), so this
 * transport spawns the real CLI and parses stdout as JSON. It requires a
 * PostgreSQL-backed Core install; failures surface as CliTransportError
 * rather than fabricated rows. List-shaped fleet views still wait on
 * Gateway list endpoints (DDE-027); single-mission reads go through
 * GatewayApiClient.
 */

import { spawn } from "node:child_process";

export class CliTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CliTransportError";
  }
}

export interface CliJsonTransport {
  /** Run `dde <args…>` and parse stdout as JSON. */
  runJson<T>(args: readonly string[]): Promise<T>;
}

export class ProcessCliJsonTransport implements CliJsonTransport {
  constructor(
    private readonly command: string = "dde",
    private readonly timeoutMs: number = 15000,
  ) {}

  async runJson<T>(args: readonly string[]): Promise<T> {
    const raw = await this.runRaw(args);
    try {
      return JSON.parse(raw) as T;
    } catch (err) {
      throw new CliTransportError(
        `dde ${args.join(" ")} printed non-JSON output: ${
          err instanceof Error ? err.message : String(err)
        }`,
      );
    }
  }

  private runRaw(args: readonly string[]): Promise<string> {
    return new Promise((resolve, reject) => {
      const child = spawn(this.command, [...args, "--json"], {
        shell: process.platform === "win32",
      });
      let stdout = "";
      let stderr = "";
      const timer = setTimeout(() => {
        child.kill();
        reject(new CliTransportError(`dde timed out after ${this.timeoutMs}ms`));
      }, this.timeoutMs);
      child.stdout.on("data", (chunk: Buffer) => {
        stdout += chunk.toString();
      });
      child.stderr.on("data", (chunk: Buffer) => {
        stderr += chunk.toString();
      });
      child.on("error", (err) => {
        clearTimeout(timer);
        reject(
          new CliTransportError(
            `could not launch '${this.command}' (is Core installed?): ${err.message}`,
          ),
        );
      });
      child.on("close", (code) => {
        clearTimeout(timer);
        if (code === 0 && stdout.trim().length > 0) {
          resolve(stdout);
        } else {
          reject(
            new CliTransportError(
              `dde ${args.join(" ")} exited ${code}: ${stderr.trim() || "no output"}`,
            ),
          );
        }
      });
    });
  }
}

/** @deprecated Kept only so existing imports keep compiling; throws. */
export class StubCliJsonTransport implements CliJsonTransport {
  async runJson<T>(_args: readonly string[]): Promise<T> {
    throw new CliTransportError("StubCliJsonTransport is deprecated; use ProcessCliJsonTransport.");
  }
}
