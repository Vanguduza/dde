/**
 * Typed client for the live Gateway /v1 surface (engine/gateway/api.py):
 * session open/resume/close, command acceptance (202), mission read and
 * mission-control projection. Shapes mirror engine/contracts (generated
 * from schemas/) — do not widen them client-side.
 *
 * Not yet served by Core: mission/run/event LIST endpoints (DDE-027).
 * Fleet-room list views therefore stay empty; this client only calls
 * endpoints that really exist. Errors map onto the Chapter 15.5 Error
 * contract (error family + retryable flag).
 */

export interface GatewayMission {
  mission_id: string;
  tenant_id: string;
  project_id: string;
  slug: string;
  title: string;
  intent: string;
  success_definition: string;
  scope: string[];
  requirement_refs: string[];
  status:
    | "CREATED"
    | "ACTIVE"
    | "PARTIAL"
    | "PAUSED"
    | "COMPLETED"
    | "FAILED"
    | "CANCELLED";
  autonomy_ceiling: number;
  lock_version: number;
  created_at: string;
  updated_at: string;
}

export interface GatewayMissionControl {
  mission_id: string;
  tenant_id: string;
  project_id: string;
  slug: string;
  title: string;
  status: GatewayMission["status"];
  autonomy_ceiling: number;
  lock_version: number;
  task_total: number;
  task_counts: Record<string, number>;
  tasks_completed: number;
  open_attention_items: number;
  attention_debt: number;
  human_minutes: number;
  approvals_per_mission: number;
  approvals_by_type: Record<string, number>;
  blocked_requests: number;
  standing_approval_usage: number;
  last_event_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GatewaySession {
  session_id: string;
  tenant_id: string;
  principal_id: string;
  client_type: string;
  device_id?: string | null;
  protocol_version: string;
  scopes: string[];
  connected_at: string;
  last_seen_at: string;
  subscriptions: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CommandAcceptance {
  command_id: string;
  status: string;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown>;
}

/** Chapter 15.5 Error contract subset clients act on. */
export class GatewayApiError extends Error {
  constructor(
    readonly errorFamily: string,
    readonly detail: string,
    readonly httpStatus: number,
    readonly retryable?: boolean,
  ) {
    super(`Gateway ${errorFamily}: ${detail} (HTTP ${httpStatus})`);
    this.name = "GatewayApiError";
  }
}

export interface OpenSessionInput {
  principalId: string;
  clientType: string;
  scopes: string[];
  deviceId?: string;
  subscriptions?: string[];
  protocolVersion?: string;
}

export class GatewayApiClient {
  constructor(private readonly baseUrl: string) {}

  getBasePath(): string {
    return `${this.baseUrl}/v1`;
  }

  async openSession(input: OpenSessionInput): Promise<GatewaySession> {
    return this.post("/sessions", {
      principal_id: input.principalId,
      client_type: input.clientType,
      device_id: input.deviceId ?? null,
      protocol_version: input.protocolVersion ?? "1",
      scopes: input.scopes,
      subscriptions: input.subscriptions ?? [],
    });
  }

  async resumeSession(
    sessionId: string,
    lastEventAt?: string,
  ): Promise<{
    session: GatewaySession;
    fresh_snapshot: boolean;
    events: unknown[];
  }> {
    return this.post(`/sessions/${sessionId}/resume`, {
      last_event_at: lastEventAt ?? null,
    });
  }

  async closeSession(sessionId: string): Promise<GatewaySession> {
    return this.post(`/sessions/${sessionId}/close`, {});
  }

  async acceptCommand(command: {
    commandId: string;
    idempotencyKey: string;
    principalId: string;
    clientSessionId: string;
    targetType: string;
    targetId: string;
    commandType: string;
    parameters: Record<string, unknown>;
    protocolVersion?: string;
  }): Promise<CommandAcceptance> {
    return this.post("/commands", {
      command_id: command.commandId,
      idempotency_key: command.idempotencyKey,
      principal_id: command.principalId,
      client_session_id: command.clientSessionId,
      target_type: command.targetType,
      target_id: command.targetId,
      command_type: command.commandType,
      parameters: command.parameters,
      requested_at: new Date().toISOString(),
      protocol_version: command.protocolVersion ?? "1",
    });
  }

  async readMission(
    sessionId: string,
    principalId: string,
    missionId: string,
  ): Promise<GatewayMission> {
    return this.get(`/missions/${missionId}`, sessionId, principalId);
  }

  async readMissionControl(
    sessionId: string,
    principalId: string,
    missionId: string,
  ): Promise<GatewayMissionControl> {
    return this.get(`/mission-control/${missionId}`, sessionId, principalId);
  }

  async readFrontendSnapshot(
    sessionId: string,
    principalId: string,
    missionId: string,
  ): Promise<Record<string, unknown>> {
    return this.get(
      `/missions/${missionId}/frontend/snapshot`,
      sessionId,
      principalId,
    );
  }

  async readDdeChat(
    sessionId: string,
    principalId: string,
    missionId: string,
  ): Promise<Record<string, unknown>> {
    return this.get(`/missions/${missionId}/chat/latest`, sessionId, principalId);
  }

  async readDdeChatResource(
    sessionId: string,
    principalId: string,
    missionId: string,
    suffix: string,
    query?: URLSearchParams,
  ): Promise<Record<string, unknown>> {
    const clean = suffix.replace(/^\/+/, "");
    const tail = query && [...query.keys()].length ? `?${query.toString()}` : "";
    let path: string;
    if (clean.startsWith("?")) {
      path = `/missions/${missionId}/chat/conversations${clean}`;
    } else if (clean === "models") {
      path = `/missions/${missionId}/chat/models${tail}`;
    } else if (clean.length) {
      path = `/missions/${missionId}/chat/conversations/${clean}${tail}`;
    } else {
      path = `/missions/${missionId}/chat/conversations${tail}`;
    }
    return this.get(path, sessionId, principalId);
  }

  async uploadDdeChatAttachment(
    sessionId: string,
    principalId: string,
    missionId: string,
    conversationId: string,
    attachmentId: string,
    bytes: Uint8Array,
    idempotencyKey: string,
  ): Promise<Record<string, unknown>> {
    const response = await fetch(
      `${this.getBasePath()}/missions/${missionId}/chat/conversations/${conversationId}/attachments/${attachmentId}/content`,
      {
        method: "PUT",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/octet-stream",
          "X-Session-Id": sessionId,
          "X-Principal-Id": principalId,
          "X-Idempotency-Key": idempotencyKey,
        },
        body: bytes,
      },
    );
    return this.parse<Record<string, unknown>>(response);
  }

  /** @deprecated Compatibility alias for pre-universal Frontend Studio Chat. */
  async readFrontendChat(
    sessionId: string,
    principalId: string,
    missionId: string,
  ): Promise<Record<string, unknown>> {
    return this.readDdeChat(sessionId, principalId, missionId);
  }

  /** @deprecated Compatibility alias for pre-universal Frontend Studio Chat. */
  async readFrontendChatResource(
    sessionId: string,
    principalId: string,
    missionId: string,
    suffix: string,
    query?: URLSearchParams,
  ): Promise<Record<string, unknown>> {
    return this.readDdeChatResource(sessionId, principalId, missionId, suffix, query);
  }

  /** @deprecated Compatibility alias for pre-universal Frontend Studio Chat. */
  async uploadFrontendChatAttachment(
    sessionId: string,
    principalId: string,
    missionId: string,
    conversationId: string,
    attachmentId: string,
    bytes: Uint8Array,
    idempotencyKey: string,
  ): Promise<Record<string, unknown>> {
    return this.uploadDdeChatAttachment(
      sessionId, principalId, missionId, conversationId, attachmentId, bytes, idempotencyKey,
    );
  }

  async readFrontendAudit(
    sessionId: string,
    principalId: string,
    missionId: string,
    suffix = "summary",
  ): Promise<Record<string, unknown>> {
    const clean = suffix.replace(/^\/+/, "");
    return this.get(
      `/missions/${missionId}/frontend/audit/${clean}`,
      sessionId,
      principalId,
    );
  }

  async readFrontendSources(
    sessionId: string,
    principalId: string,
    missionId: string,
  ): Promise<Record<string, unknown>> {
    return this.get(`/missions/${missionId}/frontend/sources`, sessionId, principalId);
  }

  async readFrontendSourceArtifact(
    sessionId: string,
    principalId: string,
    missionId: string,
    artifactId: string,
  ): Promise<Record<string, unknown>> {
    return this.get(
      `/missions/${missionId}/frontend/sources/artifacts/${artifactId}`,
      sessionId,
      principalId,
    );
  }

  async readFrontendSourceProvenance(
    sessionId: string,
    principalId: string,
    missionId: string,
    subjectKind: string,
    subjectRef: string,
  ): Promise<Record<string, unknown>> {
    const query = new URLSearchParams({ subject_kind: subjectKind, subject_ref: subjectRef });
    return this.get(
      `/missions/${missionId}/frontend/sources/provenance?${query.toString()}`,
      sessionId,
      principalId,
    );
  }

  async readFrontendSourceTargetBlend(
    sessionId: string,
    principalId: string,
    missionId: string,
    scopeKey: string,
  ): Promise<Record<string, unknown>> {
    const query = new URLSearchParams({ scope_key: scopeKey });
    return this.get(
      `/missions/${missionId}/frontend/sources/target-blend?${query.toString()}`,
      sessionId,
      principalId,
    );
  }

  async readFrontendCandidateScore(
    sessionId: string,
    principalId: string,
    missionId: string,
    candidateId: string,
  ): Promise<Record<string, unknown>> {
    return this.get(
      `/missions/${missionId}/frontend/sources/candidates/${candidateId}/score`,
      sessionId,
      principalId,
    );
  }

  async readFrontendPreview(
    sessionId: string,
    principalId: string,
    missionId: string,
    previewSessionId: string,
  ): Promise<Record<string, unknown>> {
    return this.get(
      `/missions/${missionId}/frontend/previews/${previewSessionId}`,
      sessionId,
      principalId,
    );
  }

  async readFrontendInspector(
    sessionId: string,
    principalId: string,
    missionId: string,
    candidateId: string,
    pxgKey: string,
  ): Promise<Record<string, unknown>> {
    const query = new URLSearchParams({ pxg_key: pxgKey });
    return this.get(
      `/missions/${missionId}/frontend/inspector/${candidateId}?${query.toString()}`,
      sessionId,
      principalId,
    );
  }

  private async get<T>(
    path: string,
    sessionId: string,
    principalId: string,
  ): Promise<T> {
    const response = await fetch(`${this.getBasePath()}${path}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Session-Id": sessionId,
        "X-Principal-Id": principalId,
      },
    });
    return this.parse<T>(response);
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.getBasePath()}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });
    return this.parse<T>(response);
  }

  private async parse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let family = `HTTP_${response.status}`;
      let detail = response.statusText;
      let retryable: boolean | undefined;
      try {
        const body = (await response.json()) as {
          error_code?: string;
          message?: string;
          retryable?: boolean;
        };
        if (body.error_code) {
          family = body.error_code;
        }
        if (body.message) {
          detail = body.message;
        }
        if (typeof body.retryable === "boolean") {
          retryable = body.retryable;
        }
      } catch {
        // Non-JSON error body: fall back to status-line detail.
      }
      throw new GatewayApiError(family, detail, response.status, retryable);
    }
    return (await response.json()) as T;
  }
}
