import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, it } from "node:test";

import { GatewayApiClient } from "./gatewayClient";
import { StudioGatewayService } from "./studioGateway";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("Frontend Studio Gateway transport", () => {
  it("uses the mission-scoped Core read routes", async () => {
    const seen: string[] = [];
    globalThis.fetch = async (input) => {
      seen.push(String(input));
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    const client = new GatewayApiClient("http://core.test");
    await client.readFrontendSnapshot("session", "principal", "mission");
    await client.readFrontendPreview("session", "principal", "mission", "preview");
    await client.readFrontendInspector(
      "session",
      "principal",
      "mission",
      "candidate",
      "screens/checkout#hero",
    );
    assert.deepEqual(seen, [
      "http://core.test/v1/missions/mission/frontend/snapshot",
      "http://core.test/v1/missions/mission/frontend/previews/preview",
      "http://core.test/v1/missions/mission/frontend/inspector/candidate?pxg_key=screens%2Fcheckout%23hero",
    ]);
  });

  it("preserves the bridge caller's frontend idempotency key", async () => {
    const bodies: Array<Record<string, unknown>> = [];
    globalThis.fetch = async (_input, init) => {
      const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
      if (String(_input).endsWith("/v1/sessions")) {
        return json({
          session_id: "00000000-0000-0000-0000-000000000002",
          tenant_id: "00000000-0000-0000-0000-000000000003",
          principal_id: "00000000-0000-0000-0000-000000000001",
          client_type: "human",
          protocol_version: "1",
          scopes: ["mission.read", "mission.control"],
          connected_at: "2026-09-05T00:00:00Z",
          last_seen_at: "2026-09-05T00:00:00Z",
          subscriptions: [],
          status: "OPEN",
          created_at: "2026-09-05T00:00:00Z",
          updated_at: "2026-09-05T00:00:00Z",
        });
      }
      bodies.push(body);
      return json({
        command_id: "00000000-0000-0000-0000-000000000004",
        status: "accepted",
        target_type: "mission",
        target_id: "00000000-0000-0000-0000-000000000005",
        payload: {},
      }, 202);
    };
    const gateway = new StudioGatewayService(
      "http://core.test",
      "00000000-0000-0000-0000-000000000001",
    );
    const result = await gateway.sendFrontendCommand(
      "frontend.preview.start",
      "00000000-0000-0000-0000-000000000005",
      { candidate_id: "candidate" },
      "ui-action-123",
    );
    assert.equal(result.ok, true);
    assert.equal(bodies.length, 1);
    assert.equal(bodies[0]?.idempotency_key, "ui-action-123");
  });
});

describe("Frontend Studio VSIX packaging", () => {
  it("builds the React bundle before prepublish and packages stable asset names", () => {
    const root = resolve(__dirname, "..", "..");
    const pkg = JSON.parse(
      readFileSync(resolve(root, "package.json"), "utf8"),
    ) as { scripts: Record<string, string> };
    assert.match(pkg.scripts["vscode:prepublish"] ?? "", /build:frontend-ui/);
    assert.match(pkg.scripts.package ?? "", /build:frontend-ui/);
    const vite = readFileSync(resolve(root, "ui", "vite.config.ts"), "utf8");
    assert.match(vite, /entryFileNames:\s*"assets\/dde-studio\.js"/);
    assert.match(vite, /"assets\/dde-studio\.css"/);
    const ignore = readFileSync(resolve(root, ".vscodeignore"), "utf8");
    assert.match(ignore, /!ui\/dist\/\*\*/);
  });
});

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}
