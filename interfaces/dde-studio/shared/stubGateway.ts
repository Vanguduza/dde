/**
 * Harness fleet profiles + pending Gateway client.
 * Shared by VS Code extension and Electron desktop shell.
 *
 * Each harness (Hermes / Claude Code / DeepSeek) is a Mission Control /
 * agent fleet-manager room for that Appendix A role — not a thin catalog card.
 *
 * Honest S1 boundary: only /healthz + /readyz are live. Mission/run/event
 * lists return empty arrays — never fabricated rows that look like Core data.
 * Wire to Chapter 15 REST / CLI-JSON when those surfaces exist.
 */

export type HarnessId = "hermes" | "claude-code" | "deepseek";

export type CertificationLevel = "Pending" | "Smoke" | "Standard" | "Full" | "STALE";

export interface HarnessProfile {
  id: HarnessId;
  title: string;
  appendixRole: string;
  summary: string;
  containment: "T2";
  /** Client-side label only until Worker Manager certifies a real adapter. */
  certification: CertificationLevel;
  blockedOn: string;
}

export interface MissionSummary {
  missionId: string;
  title: string;
  state: string;
  note: string;
}

export interface RunSummary {
  runId: string;
  harness: HarnessId;
  state: string;
  note: string;
}

export interface ActivityEventSummary {
  eventId: string;
  kind: string;
  summary: string;
  at: string;
}

export const HARNESS_PROFILES: Record<HarnessId, HarnessProfile> = {
  hermes: {
    id: "hermes",
    title: "Hermes",
    appendixRole: "Hermes-class harness",
    summary:
      "Mission Control for the Hermes fleet — persistent orchestration, memory, skills, delegation, browser/computer use. Status, activity, routing, observability, and control room for this T2 role.",
    containment: "T2",
    certification: "Pending",
    blockedOn:
      "Needs certified WorkerAdapter + Gateway/CLI mission, event, route, and worker APIs (DDE-011 / DDE-015 / DDE-027). Not embedded in this client.",
  },
  "claude-code": {
    id: "claude-code",
    title: "Claude Code",
    appendixRole: "Claude-Code-class",
    summary:
      "Mission Control for the Claude Code fleet — high-value reasoning, architecture, difficult debugging, premium review. Auth: Claude subscription (email / GitHub / Google); API key is backup only.",
    containment: "T2",
    certification: "Pending",
    blockedOn:
      "Needs Claude subscription session (OAuth) + certified WorkerAdapter + Gateway/CLI APIs. API key is backup only — not the primary path.",
  },
  deepseek: {
    id: "deepseek",
    title: "DeepSeek",
    appendixRole: "DeepSeek-harness-class",
    summary:
      "Mission Control for the DeepSeek fleet — long-context analysis, corpus/batch work, economical execution. Shared fleet-manager chrome for this T2 role.",
    containment: "T2",
    certification: "Pending",
    blockedOn:
      "Needs certified WorkerAdapter + Gateway/CLI mission, event, route, and worker APIs (DDE-011 / DDE-015 / DDE-027). Not embedded in this client.",
  },
};

/**
 * Placeholder client until Gateway mission/worker/event endpoints exist.
 * Returns empty collections — do not invent fake mission_stub_* rows.
 */
export class PendingGatewayClient {
  constructor(private readonly baseUrl: string) {}

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async listMissions(_harness: HarnessId): Promise<MissionSummary[]> {
    return [];
  }

  async listRuns(_harness: HarnessId): Promise<RunSummary[]> {
    return [];
  }

  /** Unified activity stream — empty until Gateway/CLI event APIs exist. */
  async listActivity(_harness: HarnessId): Promise<ActivityEventSummary[]> {
    return [];
  }
}

/** @deprecated Use PendingGatewayClient — name kept for import compatibility. */
export const StubGatewayClient = PendingGatewayClient;

/** @deprecated Use MissionSummary */
export type StubMissionSummary = MissionSummary;
/** @deprecated Use RunSummary */
export type StubRunSummary = RunSummary;
