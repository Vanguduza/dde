/**
 * DDE-052 web dashboard UI. Renders Gateway reads only — never invents
 * fleet/mission list rows. Mutations use real idempotency keys.
 */
(function () {
  "use strict";

  const { GatewayApiClient, GatewayApiError } = window.DdeDashboard;

  const HUMAN_SCOPES = [
    "mission.read",
    "mission.create",
    "mission.control",
    "approval.read",
    "approval.decide",
    "approval.request",
    "credential.capture",
  ];

  const els = {
    gatewayUrl: document.getElementById("gateway-url"),
    principalId: document.getElementById("principal-id"),
    missionId: document.getElementById("mission-id"),
    sessionStatus: document.getElementById("session-status"),
    missionBody: document.getElementById("mission-body"),
    controlBody: document.getElementById("control-body"),
    btnConnect: document.getElementById("btn-connect"),
    btnLoad: document.getElementById("btn-load"),
    btnPause: document.getElementById("btn-pause"),
    btnResume: document.getElementById("btn-resume"),
    btnCancel: document.getElementById("btn-cancel"),
    btnClose: document.getElementById("btn-close"),
  };

  const state = {
    client: null,
    session: null,
    mission: null,
  };

  function defaultGatewayUrl() {
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return window.location.origin;
    }
    return "http://127.0.0.1:8000";
  }

  function setStatus(kind, text) {
    els.sessionStatus.className = `status ${kind}`;
    els.sessionStatus.textContent = text;
  }

  function setSessionButtons(connected) {
    els.btnLoad.disabled = !connected;
    els.btnPause.disabled = !connected;
    els.btnResume.disabled = !connected;
    els.btnCancel.disabled = !connected;
    els.btnClose.disabled = !connected;
  }

  function escapeText(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => {
      switch (ch) {
        case "&":
          return "&amp;";
        case "<":
          return "&lt;";
        case ">":
          return "&gt;";
        case '"':
          return "&quot;";
        default:
          return "&#39;";
      }
    });
  }

  function renderKv(entries) {
    const rows = entries
      .map(
        ([k, v]) =>
          `<dt>${escapeText(k)}</dt><dd>${escapeText(v == null || v === "" ? "—" : v)}</dd>`,
      )
      .join("");
    return `<dl class="kv">${rows}</dl>`;
  }

  function renderMission(mission) {
    els.missionBody.className = "";
    els.missionBody.innerHTML = renderKv([
      ["slug", mission.slug],
      ["title", mission.title],
      ["status", mission.status],
      ["mission_id", mission.mission_id],
      ["project_id", mission.project_id],
      ["tenant_id", mission.tenant_id],
      ["autonomy_ceiling", mission.autonomy_ceiling],
      ["lock_version", mission.lock_version],
      ["updated_at", mission.updated_at],
    ]);
  }

  function renderControl(control) {
    els.controlBody.className = "";
    els.controlBody.innerHTML = renderKv([
      ["status", control.status],
      ["task_total", control.task_total],
      ["tasks_completed", control.tasks_completed],
      ["open_attention_items", control.open_attention_items],
      ["attention_debt", control.attention_debt],
      ["human_minutes", control.human_minutes],
      ["approvals_per_mission", control.approvals_per_mission],
      ["blocked_requests", control.blocked_requests],
      ["last_event_at", control.last_event_at],
    ]);
  }

  function newIdempotencyKey(prefix) {
    if (globalThis.crypto && crypto.randomUUID) {
      return `${prefix}-${crypto.randomUUID()}`;
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function requireSession() {
    if (!state.session || !state.client) {
      throw new Error("Open a session first");
    }
    return state;
  }

  async function connect() {
    const principalId = els.principalId.value.trim();
    if (!principalId) {
      setStatus("err", "Principal UUID is required.");
      return;
    }
    state.client = new GatewayApiClient(els.gatewayUrl.value.trim() || defaultGatewayUrl());
    try {
      state.session = await state.client.openSession({
        principalId,
        clientType: "human",
        scopes: HUMAN_SCOPES,
        subscriptions: ["mission"],
      });
      setSessionButtons(true);
      setStatus(
        "ok",
        `Session ${state.session.session_id} · tenant ${state.session.tenant_id} · status ${state.session.status}`,
      );
    } catch (err) {
      state.session = null;
      setSessionButtons(false);
      if (err instanceof GatewayApiError) {
        setStatus("err", `${err.errorFamily}: ${err.detail}`);
      } else {
        setStatus("err", String(err.message || err));
      }
    }
  }

  async function loadMission() {
    try {
      const { client, session } = requireSession();
      const missionId = els.missionId.value.trim();
      if (!missionId) {
        setStatus("err", "Mission UUID is required.");
        return;
      }
      const principalId = els.principalId.value.trim();
      const [mission, control] = await Promise.all([
        client.readMission(session.session_id, principalId, missionId),
        client.readMissionControl(session.session_id, principalId, missionId),
      ]);
      state.mission = mission;
      renderMission(mission);
      renderControl(control);
      setStatus("ok", `Loaded ${mission.slug} (${mission.status}).`);
    } catch (err) {
      if (err instanceof GatewayApiError) {
        setStatus("err", `${err.errorFamily}: ${err.detail}`);
      } else {
        setStatus("err", String(err.message || err));
      }
    }
  }

  async function controlMission(commandType) {
    try {
      const { client, session, mission } = requireSession();
      const missionId = (mission && mission.mission_id) || els.missionId.value.trim();
      if (!missionId) {
        setStatus("err", "Load a mission first.");
        return;
      }
      if (!mission || mission.lock_version == null) {
        setStatus("err", "Load a mission first so lock_version is known.");
        return;
      }
      const principalId = els.principalId.value.trim();
      const acceptance = await client.acceptCommand({
        commandId: newIdempotencyKey("cmd"),
        idempotencyKey: newIdempotencyKey(commandType),
        principalId,
        clientSessionId: session.session_id,
        targetType: "mission",
        targetId: missionId,
        commandType,
        parameters: { lock_version: mission.lock_version },
      });
      setStatus(
        "warn",
        `Accepted ${commandType} (command_id=${acceptance.command_id}, status=${acceptance.status}). Reloading…`,
      );
      await loadMission();
    } catch (err) {
      if (err instanceof GatewayApiError) {
        setStatus("err", `${err.errorFamily}: ${err.detail}`);
      } else {
        setStatus("err", String(err.message || err));
      }
    }
  }

  async function closeSession() {
    try {
      const { client, session } = requireSession();
      await client.closeSession(session.session_id);
      state.session = null;
      state.mission = null;
      setSessionButtons(false);
      els.missionBody.className = "empty";
      els.missionBody.textContent = "Nothing loaded.";
      els.controlBody.className = "empty";
      els.controlBody.textContent = "Nothing loaded.";
      setStatus("warn", "Session closed.");
    } catch (err) {
      if (err instanceof GatewayApiError) {
        setStatus("err", `${err.errorFamily}: ${err.detail}`);
      } else {
        setStatus("err", String(err.message || err));
      }
    }
  }

  els.gatewayUrl.value = defaultGatewayUrl();
  els.btnConnect.addEventListener("click", () => {
    void connect();
  });
  els.btnLoad.addEventListener("click", () => {
    void loadMission();
  });
  els.btnPause.addEventListener("click", () => {
    void controlMission("mission.pause");
  });
  els.btnResume.addEventListener("click", () => {
    void controlMission("mission.resume");
  });
  els.btnCancel.addEventListener("click", () => {
    void controlMission("mission.cancel");
  });
  els.btnClose.addEventListener("click", () => {
    void closeSession();
  });
})();
