/**
 * Live /v1 session lifecycle for dde-studio (extension + desktop shell).
 *
 * Opens a real Gateway session (Chapter 15.1) when a principal UUID is
 * configured, then reads missions through it. Everything degrades to
 * `unavailable` when Core is unreachable or no principal is configured —
 * never fabricated rows. The harness→mission binding is not served by any
 * Gateway endpoint yet, so mission reads here are driven by the caller's
 * known-mission ids; list endpoints are DDE-027 scope.
 */

import { randomUUID } from "node:crypto";
import {
  GatewayApiClient,
  type CommandAcceptance,
  type GatewayMission,
  type GatewaySession,
} from "./gatewayClient";

export type SessionState =
  | { kind: "disabled"; reason: string }
  | { kind: "unreachable"; reason: string }
  | { kind: "ready" };

export interface MissionReadResult {
  ok: boolean;
  mission?: GatewayMission;
  reason?: string;
}

export class StudioGatewayService {
  private client: GatewayApiClient | null = null;
  private session: GatewaySession | null = null;
  private principalId = "";
  private clientType = "human";
  /** Missions this studio instance has actually seen via reads/commands. */
  private readonly knownMissions = new Set<string>();

  constructor(
    readonly baseUrl: string,
    principalId: string,
    clientType = "human",
  ) {
    this.reset(baseUrl, principalId, clientType);
  }

  getPrincipalId(): string {
    return this.principalId;
  }

  reset(baseUrl: string, principalId: string, clientType = "human"): void {
    const usable = baseUrl.trim().length > 0 && isUuid(principalId.trim());
    this.client =
      usable && baseUrl.trim().length > 0 ? new GatewayApiClient(baseUrl.trim()) : null;
    this.principalId = principalId.trim();
    if (!isUuid(this.principalId)) {
      this.principalId = "";
    }
    this.clientType = clientType || "human";
    this.session = null;
  }

  /** Record a mission id seen from user input so it can be read later. */
  trackMission(missionId: string): void {
    if (isUuid(missionId)) {
      this.knownMissions.add(missionId);
    }
  }

  get trackedMissionIds(): string[] {
    return [...this.knownMissions];
  }

  async state(): Promise<SessionState> {
    if (!this.client || !this.principalId) {
      return {
        kind: "disabled",
        reason:
          "Set dde.studio.principalId to your DDE principal UUID to enable live mission reads.",
      };
    }
    if (!this.session) {
      try {
        await this.open();
        return { kind: "ready" };
      } catch (err) {
        return { kind: "unreachable", reason: describe(err) };
      }
    }
    return { kind: "ready" };
  }

  async readMission(missionId: string): Promise<MissionReadResult> {
    const state = await this.state();
    if (state.kind !== "ready" || !this.session) {
      return {
        ok: false,
        reason:
          state.kind === "ready"
            ? "session not open yet"
            : (state as { reason: string }).reason,
      };
    }
    this.trackMission(missionId);
    try {
      const mission = await this.client!.readMission(
        this.session.session_id,
        this.principalId,
        missionId,
      );
      return { ok: true, mission };
    } catch (err) {
      // A closed/expired session heals on the next attempt.
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  async readMissionControl(
    missionId: string,
  ): Promise<MissionReadResult & { control?: import("./gatewayClient").GatewayMissionControl }> {
    const state = await this.state();
    if (state.kind !== "ready" || !this.session) {
      return {
        ok: false,
        reason:
          state.kind === "ready"
            ? "session not open yet"
            : (state as { reason: string }).reason,
      };
    }
    try {
      const control = await this.client!.readMissionControl(
        this.session.session_id,
        this.principalId,
        missionId,
      );
      return { ok: true, control };
    } catch (err) {
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  /**
   * Accept a Chapter 15.2 command (mission.pause/resume/cancel) for a
   * tracked mission. Idempotency key is minted per call; acceptance (202)
   * is not completion.
   */
  async sendCommand(
    commandType: "mission.pause" | "mission.resume" | "mission.cancel",
    missionId: string,
  ): Promise<{ ok: boolean; acceptance?: CommandAcceptance; reason?: string }> {
    const state = await this.state();
    if (state.kind !== "ready" || !this.session) {
      return {
        ok: false,
        reason:
          state.kind === "ready"
            ? "session not open yet"
            : (state as { reason: string }).reason,
      };
    }
    try {
      const acceptance = await this.client!.acceptCommand({
        commandId: randomUUID(),
        idempotencyKey: `${commandType}:${missionId}:${randomUUID()}`,
        principalId: this.principalId,
        clientSessionId: this.session.session_id,
        targetType: "mission",
        targetId: missionId,
        commandType,
        parameters: {},
      });
      return { ok: true, acceptance };
    } catch (err) {
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  private async open(): Promise<void> {
    const session = await this.client!.openSession({
      principalId: this.principalId,
      clientType: this.clientType,
      scopes: ["mission.read", "mission.create", "mission.control"],
      subscriptions: ["mission"],
    });
    this.session = session;
  }
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
    value,
  );
}

function describe(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}
