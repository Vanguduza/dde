/**
 * Browser Gateway /v1 client for the web dashboard (DDE-052).
 * Mirrors interfaces/dde-studio/shared/gatewayClient.ts — only endpoints
 * that Core actually serves. Do not add list/stream shapes here.
 */
(function (global) {
  "use strict";

  class GatewayApiError extends Error {
    constructor(errorFamily, detail, httpStatus, retryable) {
      super(`Gateway ${errorFamily}: ${detail} (HTTP ${httpStatus})`);
      this.name = "GatewayApiError";
      this.errorFamily = errorFamily;
      this.detail = detail;
      this.httpStatus = httpStatus;
      this.retryable = retryable;
    }
  }

  class GatewayApiClient {
    constructor(baseUrl) {
      this.baseUrl = String(baseUrl || "").replace(/\/$/, "");
    }

    getBasePath() {
      return `${this.baseUrl}/v1`;
    }

    async openSession(input) {
      return this.post("/sessions", {
        principal_id: input.principalId,
        client_type: input.clientType,
        device_id: input.deviceId ?? null,
        protocol_version: input.protocolVersion ?? "1",
        scopes: input.scopes,
        subscriptions: input.subscriptions ?? [],
      });
    }

    async resumeSession(sessionId, lastEventAt) {
      return this.post(`/sessions/${sessionId}/resume`, {
        last_event_at: lastEventAt ?? null,
      });
    }

    async closeSession(sessionId) {
      return this.post(`/sessions/${sessionId}/close`, {});
    }

    async acceptCommand(command) {
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

    async readMission(sessionId, principalId, missionId) {
      return this.get(`/missions/${missionId}`, sessionId, principalId);
    }

    async readMissionControl(sessionId, principalId, missionId) {
      return this.get(`/mission-control/${missionId}`, sessionId, principalId);
    }

    async get(path, sessionId, principalId) {
      const response = await fetch(`${this.getBasePath()}${path}`, {
        method: "GET",
        headers: {
          Accept: "application/json",
          "X-Session-Id": sessionId,
          "X-Principal-Id": principalId,
        },
      });
      return this.parse(response);
    }

    async post(path, body) {
      const response = await fetch(`${this.getBasePath()}${path}`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      return this.parse(response);
    }

    async parse(response) {
      const text = await response.text();
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { message: text };
        }
      }
      if (!response.ok) {
        const family =
          (data && (data.error_code || data.error_family || data.errorFamily)) ||
          "UNKNOWN";
        const detail =
          (data && (data.message || data.detail || data.error)) ||
          response.statusText;
        const retryable = data && data.retryable;
        throw new GatewayApiError(family, detail, response.status, retryable);
      }
      return data;
    }
  }

  /** Endpoints this client is allowed to call — honesty pin for tests. */
  GatewayApiClient.ALLOWED_PATHS = Object.freeze([
    "POST /v1/sessions",
    "POST /v1/sessions/{id}/resume",
    "POST /v1/sessions/{id}/close",
    "POST /v1/commands",
    "GET /v1/missions/{id}",
    "GET /v1/mission-control/{id}",
  ]);

  global.DdeDashboard = global.DdeDashboard || {};
  global.DdeDashboard.GatewayApiClient = GatewayApiClient;
  global.DdeDashboard.GatewayApiError = GatewayApiError;
})(typeof window !== "undefined" ? window : globalThis);
