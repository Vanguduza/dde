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
      usable && baseUrl.trim().length > 0
        ? new GatewayApiClient(baseUrl.trim())
        : null;
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
  ): Promise<
    MissionReadResult & {
      control?: import("./gatewayClient").GatewayMissionControl;
    }
  > {
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

  /**
   * Send one DDE-067 Frontend Studio mutation through the ordinary Gateway
   * command ledger. The caller supplies only structured parameters; the
   * client never patches preview DOM or writes prototype files directly.
   */
  async sendFrontendCommand(
    commandType: string,
    missionId: string,
    parameters: Record<string, unknown>,
    idempotencyKey?: string,
    commandId?: string,
  ): Promise<{ ok: boolean; acceptance?: CommandAcceptance; reason?: string }> {
    if (!/^frontend\./.test(commandType) || !isUuid(missionId.trim())) {
      return {
        ok: false,
        reason: "Frontend Studio needs a valid command and mission UUID.",
      };
    }
    const state = await this.state();
    if (state.kind !== "ready" || !this.session) {
      return {
        ok: false,
        reason: state.kind === "ready" ? "session not open yet" : state.reason,
      };
    }
    try {
      this.trackMission(missionId);
      const acceptance = await this.client!.acceptCommand({
        commandId: commandId ?? randomUUID(),
        idempotencyKey: idempotencyKey ?? `${commandType}:${missionId}:${randomUUID()}`,
        principalId: this.principalId,
        clientSessionId: this.session.session_id,
        targetType: "mission",
        targetId: missionId,
        commandType,
        parameters,
      });
      return { ok: true, acceptance };
    } catch (err) {
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  async readFrontendSnapshot(
    missionId: string,
  ): Promise<{
    ok: boolean;
    value?: Record<string, unknown>;
    reason?: string;
  }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendSnapshot(session, this.principalId, missionId),
    );
  }

  async readFrontendChat(
    missionId: string,
  ): Promise<{
    ok: boolean;
    value?: Record<string, unknown>;
    reason?: string;
  }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendChat(session, this.principalId, missionId),
    );
  }

  async readFrontendChats(
    missionId: string,
    opts?: { query?: string; includeArchived?: boolean },
  ): Promise<{ ok: boolean; value?: Record<string, unknown>; reason?: string }> {
    const query = new URLSearchParams();
    if (opts?.query) query.set("query", opts.query);
    if (opts?.includeArchived) query.set("include_archived", "true");
    return this.readFrontendResource((session) =>
      this.client!.readFrontendChatResource(
        session, this.principalId, missionId, `?${query.toString()}`.replace(/^\?$/, ""),
      ),
    );
  }

  async readFrontendChatById(
    missionId: string,
    conversationId: string,
  ): Promise<{ ok: boolean; value?: Record<string, unknown>; reason?: string }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendChatResource(
        session, this.principalId, missionId, conversationId,
      ),
    );
  }

  async readFrontendChatSubresource(
    missionId: string,
    conversationId: string,
    resource: "attachments" | "plans" | "activities" | "checkpoints" | "changes",
  ): Promise<{ ok: boolean; value?: Record<string, unknown>; reason?: string }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendChatResource(
        session, this.principalId, missionId, `${conversationId}/${resource}`,
      ),
    );
  }

  async readFrontendChatModels(
    missionId: string,
  ): Promise<{ ok: boolean; value?: Record<string, unknown>; reason?: string }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendChatResource(
        session, this.principalId, missionId, "models",
      ),
    );
  }

  async readFrontendChatContext(
    missionId: string,
    conversationId: string,
    refs: readonly string[],
    budgetTokens = 24_000,
  ): Promise<{ ok: boolean; value?: Record<string, unknown>; reason?: string }> {
    const query = new URLSearchParams({
      refs: refs.join(","),
      budget_tokens: String(budgetTokens),
    });
    return this.readFrontendResource((session) =>
      this.client!.readFrontendChatResource(
        session, this.principalId, missionId, `${conversationId}/context`, query,
      ),
    );
  }

  async uploadFrontendChatAttachment(
    missionId: string,
    conversationId: string,
    attachmentId: string,
    bytes: Uint8Array,
    idempotencyKey: string,
  ): Promise<{ ok: boolean; value?: Record<string, unknown>; reason?: string }> {
    return this.readFrontendResource((session) =>
      this.client!.uploadFrontendChatAttachment(
        session, this.principalId, missionId, conversationId, attachmentId, bytes, idempotencyKey,
      ),
    );
  }

  async readFrontendPreview(
    missionId: string,
    previewSessionId: string,
  ): Promise<{
    ok: boolean;
    value?: Record<string, unknown>;
    reason?: string;
  }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendPreview(
        session,
        this.principalId,
        missionId,
        previewSessionId,
      ),
    );
  }

  async readFrontendInspector(
    missionId: string,
    candidateId: string,
    pxgKey: string,
  ): Promise<{
    ok: boolean;
    value?: Record<string, unknown>;
    reason?: string;
  }> {
    return this.readFrontendResource((session) =>
      this.client!.readFrontendInspector(
        session,
        this.principalId,
        missionId,
        candidateId,
        pxgKey,
      ),
    );
  }

  private async readFrontendResource(
    read: (sessionId: string) => Promise<Record<string, unknown>>,
  ): Promise<{
    ok: boolean;
    value?: Record<string, unknown>;
    reason?: string;
  }> {
    const state = await this.state();
    if (state.kind !== "ready" || !this.session) {
      return {
        ok: false,
        reason: state.kind === "ready" ? "session not open yet" : state.reason,
      };
    }
    try {
      return { ok: true, value: await read(this.session.session_id) };
    } catch (err) {
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  /**
   * Accept `approval.batch_decide` for a set of pending approvals
   * (Chapter 13.1 amendment on POST /v1/commands). The engine requires
   * scope_hashes parallel to approval_ids and rejects an empty batch or
   * mismatched lists with POLICY_DENIED, so the caller supplies the hash
   * list it read from the approvals surface; nothing is guessed here.
   * The session does not carry project_id, so it must be given — a
   * non-UUID projectId fails fast instead of addressing a fabricated
   * target. Acceptance is 202 only; it never implies the decisions are
   * applied yet.
   */
  async sendBatchApprove(
    projectId: string,
    approvalIds: string[],
    opts: {
      scopeHashes: string[];
      rationale: string;
      humanMinutes?: number;
    },
  ): Promise<{ ok: boolean; acceptance?: CommandAcceptance; reason?: string }> {
    if (!isUuid(projectId.trim())) {
      return {
        ok: false,
        reason:
          "batch approve needs the DDE project UUID (no project_id exists in the Gateway session); set dde.studio.projectId",
      };
    }
    if (
      approvalIds.length === 0 ||
      approvalIds.some((id) => !isUuid(id.trim()))
    ) {
      return {
        ok: false,
        reason: "batch approve needs at least one approval UUID",
      };
    }
    if (
      opts.scopeHashes.length !== approvalIds.length ||
      opts.scopeHashes.some((h) => typeof h !== "string" || h.length === 0)
    ) {
      return {
        ok: false,
        reason:
          "scopeHashes must be parallel to approvalIds (one per approval)",
      };
    }
    const parameters: Record<string, unknown> = {
      approval_ids: approvalIds.map((id) => id.trim()),
      scope_hashes: opts.scopeHashes,
      decision: "APPROVED",
      rationale: opts.rationale,
    };
    if (
      typeof opts.humanMinutes === "number" &&
      Number.isInteger(opts.humanMinutes)
    ) {
      parameters.human_minutes = opts.humanMinutes;
    }
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
        idempotencyKey: `approval.batch:${randomUUID()}`,
        principalId: this.principalId,
        clientSessionId: this.session.session_id,
        targetType: "project",
        targetId: projectId.trim(),
        commandType: "approval.batch_decide",
        parameters,
      });
      return { ok: true, acceptance };
    } catch (err) {
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  /**
   * Paste → hash → capture OpenSandbox API key via Credential Broker.
   * Acceptance payload is fingerprint/last4 only — never the raw key.
   */
  async captureOpensandboxKey(
    projectId: string,
    apiKey: string,
    domain?: string,
  ): Promise<{ ok: boolean; acceptance?: CommandAcceptance; reason?: string }> {
    if (!isUuid(projectId.trim())) {
      return {
        ok: false,
        reason:
          "OpenSandbox capture needs the DDE project UUID; set dde.studio.projectId",
      };
    }
    if (!apiKey.trim()) {
      return { ok: false, reason: "API key is empty" };
    }
    const parameters: Record<string, unknown> = { api_key: apiKey };
    if (domain && domain.trim()) {
      parameters.domain = domain.trim();
    }
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
        idempotencyKey: `credential.capture_opensandbox:${randomUUID()}`,
        principalId: this.principalId,
        clientSessionId: this.session.session_id,
        targetType: "project",
        targetId: projectId.trim(),
        commandType: "credential.capture_opensandbox",
        parameters,
      });
      return { ok: true, acceptance };
    } catch (err) {
      if (err instanceof Error && /SESSION_EXPIRED|401/.test(err.message)) {
        this.session = null;
      }
      return { ok: false, reason: describe(err) };
    }
  }

  async inspectOpensandboxKey(
    projectId: string,
  ): Promise<{ ok: boolean; acceptance?: CommandAcceptance; reason?: string }> {
    if (!isUuid(projectId.trim())) {
      return {
        ok: false,
        reason:
          "OpenSandbox inspect needs the DDE project UUID; set dde.studio.projectId",
      };
    }
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
        idempotencyKey: `credential.inspect_opensandbox:${randomUUID()}`,
        principalId: this.principalId,
        clientSessionId: this.session.session_id,
        targetType: "project",
        targetId: projectId.trim(),
        commandType: "credential.inspect_opensandbox",
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
      scopes: [
        "mission.read",
        "mission.create",
        "mission.control",
        "approval.read",
        "approval.decide",
        "approval.request",
        "credential.capture",
      ],
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
