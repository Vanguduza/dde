/** Connection settings — shared by extension and Electron desktop. */

export type PreferredTarget = "local" | "cloud";

export interface StudioConnection {
  coreUrl: string;
  cloudUrl: string;
  preferredTarget: PreferredTarget;
  pollIntervalMs: number;
  /** Effective base URL used for Gateway calls. */
  effectiveUrl: string;
}

export function readConnection(
  getConfig: (key: string) => unknown,
): StudioConnection {
  const coreUrl = normalizeUrl(
    String(getConfig("coreUrl") ?? "http://127.0.0.1:8000"),
  );
  const cloudUrl = normalizeUrl(String(getConfig("cloudUrl") ?? ""));
  const preferredTarget =
    getConfig("preferredTarget") === "cloud" ? "cloud" : "local";
  const pollIntervalMs = Number(getConfig("pollIntervalMs") ?? 5000);

  let effectiveUrl = coreUrl;
  if (preferredTarget === "cloud") {
    if (!cloudUrl) {
      throw new ConnectionConfigError(
        "Cloud target selected but cloud URL is empty.",
      );
    }
    effectiveUrl = cloudUrl;
  }

  return {
    coreUrl,
    cloudUrl,
    preferredTarget,
    pollIntervalMs:
      Number.isFinite(pollIntervalMs) && pollIntervalMs >= 1000
        ? pollIntervalMs
        : 5000,
    effectiveUrl,
  };
}

export class ConnectionConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionConfigError";
  }
}

function normalizeUrl(raw: string): string {
  return raw.trim().replace(/\/+$/, "");
}
