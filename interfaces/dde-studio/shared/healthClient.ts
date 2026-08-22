/**
 * Live Gateway health client.
 * Consumes schemas/api/healthz.json and schemas/api/readyz.json only.
 * Shared by VS Code extension and Electron desktop shell.
 */

export interface HealthzResponse {
  status: "ok";
}

export interface ReadyzResponse {
  status: "ready" | "not_ready";
  database: boolean;
  redis: boolean;
  migrations: "head" | "behind" | "unknown";
}

export type ProbeState =
  | { kind: "idle" }
  | { kind: "checking"; url: string }
  | {
      kind: "ok";
      url: string;
      healthz: HealthzResponse;
      readyz: ReadyzResponse;
      checkedAt: string;
    }
  | {
      kind: "unreachable";
      url: string;
      error: string;
      checkedAt: string;
    }
  | {
      kind: "misconfigured";
      error: string;
      checkedAt: string;
    };

export class HealthClient {
  async probe(baseUrl: string): Promise<ProbeState> {
    const checkedAt = new Date().toISOString();
    try {
      const [healthz, readyz] = await Promise.all([
        this.getJson<HealthzResponse>(`${baseUrl}/healthz`),
        this.getJson<ReadyzResponse>(`${baseUrl}/readyz`),
      ]);

      if (healthz.status !== "ok") {
        return {
          kind: "unreachable",
          url: baseUrl,
          error: `Unexpected healthz status: ${String((healthz as { status?: string }).status)}`,
          checkedAt,
        };
      }

      return { kind: "ok", url: baseUrl, healthz, readyz, checkedAt };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return {
        kind: "unreachable",
        url: baseUrl,
        error: message,
        checkedAt,
      };
    }
  }

  private async getJson<T>(url: string): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} for ${url}`);
      }
      return (await response.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }
}
