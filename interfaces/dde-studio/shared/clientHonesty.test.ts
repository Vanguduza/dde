/**

 * Client-local unit tests (no Core required).

 * Run via: npm test (compiles then node --test).

 */



import assert from "node:assert/strict";

import { describe, it } from "node:test";



import {

  MODULE_REGISTRY,

  RESEARCH_MODULE_IDS,

  SIDEBAR_STUB_MODULES,

  moduleById,

  modulesWithViewId,

} from "./registry";

import { readConnection, ConnectionConfigError } from "./settings";
import { claudeCodeAuthBannerHtml, CLAUDE_CODE_DOCS_AUTH } from "./claudeAuth";
import { messageBridgeScript } from "./ui/base";
import { frontendStudioHtml } from "./ui/frontendStudio";

import {

  HARNESS_PROFILES,

  PendingGatewayClient,

  StubGatewayClient,

} from "./stubGateway";

import {

  connectionHtml,

  harnessHtml,

  modulePanelHtml,

  morningReviewHtml,

  overviewHtml,

  escapeHtml,

  MISSION_CONTROL_SECTIONS,

  OVERVIEW_ZONES,

} from "./ui/html";

import type { ProbeState } from "./healthClient";

import type { AuthState } from "./authTypes";



/** Tiny DOM stub sufficient to execute messageBridgeScript() in node. */

interface BridgeElementStub {

  getAttribute(name: string): string | null;

  addEventListener(type: string, handler: (event?: unknown) => void): void;

}



function bridgeWindow(): {

  window: Record<string, unknown>;

  document: { querySelectorAll(sel: string): BridgeElementStub[]; elements: BridgeElementStub[] };

  posted: Array<Record<string, unknown>>;

  handlers: Array<(event?: unknown) => void>;

} {

  const posted: Array<Record<string, unknown>> = [];

  const handlers: Array<(event?: unknown) => void> = [];

  const document = {

    elements: [] as BridgeElementStub[],

    querySelectorAll(_sel: string) {

      return this.elements;

    },

  };

  const window: Record<string, unknown> = {

    document,

    ddeDesktop: { postMessage: (m: Record<string, unknown>) => posted.push(m) },

  };

  return { window, document, posted, handlers };

}



function runBridge(window: Record<string, unknown>): void {

  // The bridge is emitted as inline script text; evaluating it here keeps

  // the contract test client-local with a minimal DOM stub.

  const fn = new Function("window", "document", "JSON", messageBridgeScript());

  fn(window, window.document, JSON);

}




/** Phrases that must not appear as user-visible helper / tutorial copy. */const FORBIDDEN_HELPER = [

  /Blocked on Gateway/i,

  /Needs Gateway or CLI-JSON/i,

  /Needs mission command API/i,

  /Needs DDE-026/i,

  /not inventing/i,

  /not invent/i,

  /fabricat/i,

  /Live today:/i,

  /Activity will appear here/i,

  /All clear!/i,

  /Appendix A role identity/i,

  /honest reasons/i,

  /will bind to Gateway/i,

  /Chat Participant/i,

  /Connect Gateway sessions/i,

  /session API not available/i,

  /No Chat Participant/i,

  /empty by design/i,

  /not client-faked/i,

  /Informational shell/i,

  /Docs surface not wired/i,

  /Never writes Project Truth/i,

  /other sidebar views show honest/i,

  /Primary home is shown/i,

  /No fabricated mission/i,

  /What ran overnight/i,

  /first thing/i,

];



function assertNoHelperCopy(html: string, label: string): void {

  for (const re of FORBIDDEN_HELPER) {

    assert.doesNotMatch(html, re, `${label} must not contain helper: ${re}`);

  }

}



const probe: ProbeState = {

  kind: "ok",

  url: "http://127.0.0.1:8000",

  healthz: { status: "ok" },

  readyz: {

    status: "ready",

    database: true,

    redis: true,

    migrations: "head",

  },

  checkedAt: "2026-01-01T00:00:00.000Z",

};



describe("settings", () => {

  it("builds local effectiveUrl", () => {

    const c = readConnection(() => undefined);

    assert.equal(c.preferredTarget, "local");

    assert.equal(c.effectiveUrl, "http://127.0.0.1:8000");

  });



  it("requires cloudUrl when target is cloud", () => {

    assert.throws(

      () =>

        readConnection((key) => {

          if (key === "preferredTarget") return "cloud";

          if (key === "cloudUrl") return "";

          return undefined;

        }),

      (err: unknown) => err instanceof ConnectionConfigError,

    );

  });

});



describe("PendingGatewayClient honesty", () => {

  it("returns empty missions and runs (no fake stub rows)", async () => {

    const client = new PendingGatewayClient("http://127.0.0.1:8000");

    assert.deepEqual(await client.listMissions("hermes"), []);

    assert.deepEqual(await client.listRuns("claude-code"), []);

    assert.deepEqual(await client.listActivity("deepseek"), []);

  });



  it("StubGatewayClient alias also returns empty (no fake IDs)", async () => {

    const client = new StubGatewayClient("http://127.0.0.1:8000");

    const missions = await client.listMissions("deepseek");

    const runs = await client.listRuns("deepseek");

    const activity = await client.listActivity("deepseek");

    assert.equal(missions.length, 0);

    assert.equal(runs.length, 0);

    assert.equal(activity.length, 0);

    assert.doesNotMatch(JSON.stringify(missions), /stub|fake|demo/i);

    assert.doesNotMatch(JSON.stringify(runs), /stub|fake|demo/i);

    assert.doesNotMatch(JSON.stringify(activity), /stub|fake|demo/i);

  });

});

describe("Frontend Studio honesty", () => {
  it("contributes six real views without fabricated rows or verdicts", () => {
    for (const view of ["home", "intake", "donors", "canvas", "verify", "approvals"] as const) {
      const html = frontendStudioHtml(view);
      assert.match(html, new RegExp(`data-frontend-studio-view="${view}"`));
      assert.doesNotMatch(html, /stub[_-]?(mission|donor)|sample donor|rubric passed|quality score:\s*\d/i);
    }
  });

  it("offers only registered structured frontend commands", () => {
    const html = frontendStudioHtml("canvas");
    assert.match(html, /frontend\.canvas\.insert_component/);
    assert.match(html, /frontend\.canvas\.update_element/);
    assert.match(html, /JSON\.parse/);
    assert.doesNotMatch(html, /contenteditable|execCommand|innerHTML\s*=/i);
  });
});



describe("registry completeness vs research §7", () => {

  it("covers every RESEARCH_MODULE_IDS entry", () => {

    for (const id of RESEARCH_MODULE_IDS) {

      const mod = moduleById(id);

      assert.ok(mod, `missing registry entry for ${id}`);

      assert.equal(mod.id, id);

    }

  });



  it("has no extra registry ids beyond research list", () => {

    for (const mod of MODULE_REGISTRY) {

      assert.ok(

        RESEARCH_MODULE_IDS.includes(mod.id),

        `unexpected module ${mod.id}`,

      );

    }

  });



  it("marks Connection as the only exists module with live health", () => {

    const core = moduleById("dde-core-ui");

    assert.ok(core);

    assert.equal(core.status, "exists");

    assert.match(core.liveToday, /healthz/);

    const exists = MODULE_REGISTRY.filter((m) => m.status === "exists");

    assert.equal(exists.length, 2);

  });



  it("marks worker harnesses as Mission Control stub, not exists", () => {

    const workers = moduleById("dde-workers");

    assert.ok(workers);

    assert.equal(workers.status, "stub");

    assert.match(workers.summary, /Mission Control/i);

    assert.match(workers.liveToday, /empty/i);

  });



  it("contributes chat/donor/knowledge/evaluation/debug as stubs", () => {

    for (const id of [

      "dde-chat",

      "dde-donor",

      "dde-knowledge",

      "dde-evaluation",

      "dde-debug",

    ] as const) {

      const m = moduleById(id);

      assert.ok(m);

      assert.equal(m.status, "stub");

      assert.ok(m.viewId, `${id} must have viewId`);

    }

  });



  it("preview gallery is live: exists status, honest liveToday, sandboxed law cited", () => {

    const m = moduleById("product-environment");

    assert.ok(m);

    assert.equal(m.status, "exists");

    assert.match(m.liveToday, /sandboxed srcdoc/);

    assert.match(m.summary, /Prototype Gallery/);

    assert.match(m.liveToday, /DDE-038.*not exposed/);

  });



  it("every sidebar stub has a viewId and honest liveToday", () => {

    for (const m of SIDEBAR_STUB_MODULES) {

      assert.equal(m.status, "stub");

      assert.ok(m.viewId);

      assert.ok(m.liveToday.length > 0);

    }

  });



  it("modulesWithViewId includes connection + all sidebar stubs", () => {

    const views = modulesWithViewId();

    assert.ok(views.some((v) => v.id === "dde-core-ui"));

    for (const m of SIDEBAR_STUB_MODULES) {

      assert.ok(views.some((v) => v.id === m.id));

    }

  });

});



describe("harness Mission Control profiles", () => {

  it("uses Pending certification until Core adapters exist", () => {

    for (const id of ["hermes", "claude-code", "deepseek"] as const) {

      assert.equal(HARNESS_PROFILES[id].certification, "Pending");

      assert.match(HARNESS_PROFILES[id].blockedOn, /WorkerAdapter|Gateway/);

      assert.match(HARNESS_PROFILES[id].summary, /Mission Control/i);

    }

  });

});



describe("html honesty and panel structure", () => {

  it("overviewHtml exposes all ten zones and operator actions", () => {

    const connection = readConnection(() => undefined);

    const html = overviewHtml(connection, probe);

    assert.match(html, /data-surface="overview"/);

    assert.match(html, /DDE Code — Mission Overview/);

    for (const zone of OVERVIEW_ZONES) {

      assert.match(

        html,

        new RegExp(`data-zone="${zone}"`),

        `missing overview zone ${zone}`,

      );

    }

    assert.match(html, /Truth/);

    assert.match(html, /Evidence/);

    assert.match(html, /data-cmd="startMission"/);

    assert.match(html, /data-cmd="pauseMission"/);

    assert.match(html, /data-cmd="resumeMission"/);

    assert.match(html, /data-cmd="cancelMission"/);

    assert.match(html, /data-cmd="approve"/);

    assert.match(html, /data-cmd="reject"/);

    assert.match(html, /data-cmd="refresh"/);

    assert.match(html, /Open fleet room/);

    assert.match(html, /data-cmd="openHermes"/);

    assert.match(html, /data-cmd="openClaudeCode"/);

    assert.match(html, /data-cmd="openDeepSeek"/);

    assert.match(html, /ready|Core ready/i);

    assert.doesNotMatch(html, /mission_stub|run_stub|event_stub|ERP-000421/);

    assert.match(

      html,

      /disabled[^>]*data-cmd="startMission"|data-cmd="startMission"[^>]*disabled/,

    );

    assertNoHelperCopy(html, "overview");

  });



  it("overviewHtml matches mockup information architecture", () => {

    const connection = readConnection(() => undefined);

    const html = overviewHtml(connection, probe);

    assert.match(html, /class="ov-body"/);

    assert.match(html, /class="ov-sidebar"/);

    assert.match(html, /class="ov-main"/);

    assert.match(html, /class="ov-modules"/);

    assert.match(html, /class="ov-spine"/);

    assert.match(html, /Operator actions/);

    assert.match(html, /Core ready/);

    assert.match(html, /No active missions/);

    assert.match(html, /No blocked missions/);

    assert.match(html, /No completed missions/);

    assert.match(html, /No events/);

    assert.match(html, /main dashboard/);

    assert.match(html, /Gateway pending/);

    assert.match(html, /data-cmd="openSettings"/);

    assert.match(html, /aria-label="Docs"/);

    assert.match(html, /aria-label="More"/);

    assert.match(html, /data-harness="hermes"[\s\S]*?>idle</);

    assert.match(html, /data-harness="claude-code"[\s\S]*?>idle</);

    assert.match(html, /data-harness="deepseek"[\s\S]*?>pending</);

    assert.doesNotMatch(

      html,

      /data-harness="hermes"[\s\S]*?pill warn[\s\S]*?data-harness="claude-code"/,

    );

    assert.doesNotMatch(html, /ov-footnote|Live today:/);

    assert.doesNotMatch(html, /DDE-026/);

    assert.doesNotMatch(html, /title="Needs /);

  });



  it("disabled controls use short Unavailable titles", () => {

    const connection = readConnection(() => undefined);

    const html = overviewHtml(connection, probe);

    assert.match(html, /title="Unavailable"/);

    assert.doesNotMatch(html, /title="Needs /);

  });



  it("harnessHtml with empty lists does not invent mission_stub ids", () => {

    const html = harnessHtml({

      harness: "hermes",

            missions: [],

      runs: [],

    });

    assert.doesNotMatch(html, /mission_stub/);

    assert.doesNotMatch(html, /run_stub/);

    assert.match(html, /Mission Control/);

    assert.match(html, /Pause → checkpoint/);

    assert.match(html, /data-bind="missions"/);

    assert.match(html, /data-bind="runs"/);

    assertNoHelperCopy(html, "harness hermes");

  });



  it("each harness Mission Control exposes the five capability sections", () => {

    for (const harness of ["hermes", "claude-code", "deepseek"] as const) {

      const html = harnessHtml({

        harness,

                missions: [],

        runs: [],

      });

      assert.match(html, /data-surface="mission-control"/);

      assert.match(html, new RegExp(`data-harness="${harness}"`));

      for (const section of MISSION_CONTROL_SECTIONS) {

        assert.match(

          html,

          new RegExp(`data-section="${section}"`),

          `${harness} missing section ${section}`,

        );

      }

      assert.match(html, /Status report/i);

      assert.match(html, /Activity stream/i);

      assert.match(html, /Task routing/i);

      assert.match(html, /Observability/i);

      assert.match(html, /Control room/i);

      assert.doesNotMatch(html, /mission_stub|run_stub|event_stub/);

      assert.doesNotMatch(html, /Harness catalog/i);

      assert.doesNotMatch(html, /Appendix A role identity/i);

      assert.doesNotMatch(html, /Core health|Refresh health|healthz/i);

      if (harness === "claude-code") {
        assert.match(html, /subscription/);
        assert.match(html, /data-cmd="openClaudeCodeSignIn"/);
        assert.match(html, /data-cmd="verifyClaudeCodeAuth"/);
        assert.match(html, /data-cmd="storeClaudeCodeSetupToken"/);
        assert.match(html, /data-cmd="openClaudeCodeApiKeyBackup"/);
        assert.doesNotMatch(html, /Claude Code runs on API key/i);
        assert.doesNotMatch(html, /Signed in —|login successful|oauth complete/i);
      } else {
        assert.doesNotMatch(html, /openClaudeCodeSignIn/);
      }

      assertNoHelperCopy(html, `harness ${harness}`);

    }

  });



  it("modulePanelHtml for mission shows TaskGraph empty without core health", () => {

    const mod = moduleById("dde-mission")!;

    const html = modulePanelHtml(mod);

    assert.match(html, /TaskGraph/i);

    assert.doesNotMatch(html, /Core health|healthz|Refresh health/i);

    assert.doesNotMatch(html, /mission_stub|ERP-000421/);

    assertNoHelperCopy(html, "mission panel");

  });



  it("routing panel separates hard gates from ranking", () => {

    const html = modulePanelHtml(moduleById("dde-routing")!);

    assert.match(html, /Gates 0–5/);

    assert.match(html, /Gates 6–7/);

    assertNoHelperCopy(html, "routing panel");

  });



  it("context panel lists seven coverage categories, not a fake %", () => {

    const html = modulePanelHtml(moduleById("dde-context")!);

    assert.match(html, /authoritative_requirements/);

    assert.match(html, /known_unresolved_questions/);

    assert.doesNotMatch(html, /Coverage:\s*\d+%/i);

    assert.doesNotMatch(html, /\d+%\s*of budget/i);

    assertNoHelperCopy(html, "context panel");

  });



  it("verification panel lists thirteen stages", () => {

    const html = modulePanelHtml(moduleById("dde-verification")!);

    assert.match(html, /AcceptanceOracle/);

    assert.match(html, /Independence/i);

    assertNoHelperCopy(html, "verification panel");

  });



  it("chat shell is chrome-only without Gateway essays", () => {

    const html = modulePanelHtml(moduleById("dde-chat")!);

    assert.match(html, /chat-shell|chat-thread/);

    assert.doesNotMatch(html, /Core health|Refresh health|healthz/i);

    assert.match(html, /disabled[^>]*>Send</);

    assertNoHelperCopy(html, "chat panel");

  });



  it("morningReviewHtml has structure without fake overnight data or essays", () => {

    const html = morningReviewHtml();

    assert.match(html, /Morning Review/);

    assert.match(html, /Attention debt/i);

    assert.match(html, /Overnight summary/i);

    assert.doesNotMatch(html, /mission_stub|ran overnight: \d+/i);

    assert.doesNotMatch(html, /DDE-026/);

    assert.doesNotMatch(html, /Core health|Refresh health|healthz/i);

    assertNoHelperCopy(html, "morning review");

  });



  it("approvals panel links Morning Review", () => {

    const html = modulePanelHtml(moduleById("dde-approvals")!);

    assert.match(html, /openMorningReview|Morning Review/);

    assertNoHelperCopy(html, "approvals panel");

  });

  it("approvals batch affordance is disabled until approvals read surface exists", () => {

    const html = modulePanelHtml(moduleById("dde-approvals")!);

    // One multi-select action button, verb-first, factual pending tooltip.

    assert.match(html, /data-cmd="batchApprove"/);

    assert.match(

      html,

      /disabled[^>]*title="approvals read surface pending"[^>]*>Approve selected</,

    );

    // Engine write surface is live; only the read side is missing. The
    // panel must not claim otherwise.

    assert.doesNotMatch(html, /engine surface pending/);

    assert.match(html, /data-batch="select-all"/);

    assert.match(html, /data-batch="count"/);

    assert.match(html, /0 selected/);

    // Prop-driven enablement defaults to disabled; no caller passes a
    // flag today because no read surface can populate real selections.

    const enabledHtml = modulePanelHtml(moduleById("dde-approvals")!, {

      batchApproveEnabled: true,

    });

    assert.doesNotMatch(

      enabledHtml,

      /data-cmd="batchApprove"[^>]*disabled/,

    );

    // No fabricated success state: nothing claims an approval happened.

    assert.doesNotMatch(html, /[Aa]pproved\b/);

    assertNoHelperCopy(html, "approvals batch");

  });



describe("messageBridgeScript batch ids", () => {

  it("posts ids parsed from data-batch-ids", async () => {

    const { window, document, posted, handlers } = bridgeWindow();

    document.elements.push({

      getAttribute(name: string) {

        if (name === "data-cmd") return "batchApprove";

        if (name === "data-batch-ids") {

          return JSON.stringify(["0f0e0d0c-1111-4222-8333-444455556666"]);

        }

        return null;

      },

      addEventListener(_type: string, handler: () => void) {

        handlers.push(handler);

      },

    } as unknown as BridgeElementStub);

    runBridge(window);

    await handlers[0]();

    assert.equal(posted.length, 1);

    assert.equal(posted[0].type, "batchApprove");

    assert.deepEqual(posted[0].ids, [

      "0f0e0d0c-1111-4222-8333-444455556666",

    ]);

  });



  it("ignores malformed data-batch-ids instead of posting", async () => {

    const { window, document, posted, handlers } = bridgeWindow();

    document.elements.push({

      getAttribute(name: string) {

        if (name === "data-cmd") return "batchApprove";

        if (name === "data-batch-ids") return "{not json";

        return null;

      },

      addEventListener(_type: string, handler: () => void) {

        handlers.push(handler);

      },

    } as unknown as BridgeElementStub);

    runBridge(window);

    await handlers[0]();

    assert.deepEqual(posted, []);

  });

});



  it("donor panel shows Ch.13.8 taxonomy badges", () => {

    const html = modulePanelHtml(moduleById("dde-donor")!);

    assert.match(html, /OPEN_REUSE/);

    assert.match(html, /REJECTED/);

    assertNoHelperCopy(html, "donor panel");

  });



  it("connectionHtml shows live status without helper essays", () => {

    const connection = readConnection(() => undefined);

    const auth: AuthState = { kind: "unauthenticated" };

    const html = connectionHtml(connection, probe, auth);

    assert.match(html, /ready|healthz/i);

    assert.match(html, /unauthenticated/);

    assert.match(html, /subscription/);

    assert.match(html, /data-cmd="openClaudeCodeSignIn"/);
    assert.match(html, /data-cmd="verifyClaudeCodeAuth"/);
    assert.match(html, /data-cmd="storeClaudeCodeSetupToken"/);
    assert.match(html, /data-cmd="openClaudeCodeApiKeyBackup"/);
    assert.doesNotMatch(html, /Claude Code runs on API key/i);
    assert.doesNotMatch(html, /Signed in —|login successful|oauth complete/i);

    assertNoHelperCopy(html, "connection");

  });



  it("every sidebar module panel strips helper essays", () => {

    for (const m of SIDEBAR_STUB_MODULES) {

      const html = modulePanelHtml(m);

      assertNoHelperCopy(html, m.id);

      assert.doesNotMatch(html, /mission_stub|run_stub|event_stub/);

      assert.doesNotMatch(html, /Core health|Refresh health|healthz/i);

    }

  });



  it("escapeHtml escapes markup", () => {

    assert.equal(escapeHtml(`<a "x">`), `&lt;a &quot;x&quot;&gt;`);

  });

});


describe("claude auth honesty", () => {
  it("verified Claude auth shows Signed in only with real state", () => {
    const unsigned = claudeCodeAuthBannerHtml({ kind: "none" });
    assert.doesNotMatch(unsigned, /Signed in —/i);
    assert.match(unsigned, /Sign in/);
    assert.doesNotMatch(unsigned, /installClaudeCodeCli/);

    const signed = claudeCodeAuthBannerHtml({
      kind: "verified_cli_login",
      email: "user@example.com",
      subscriptionType: "max",
      authMethod: "claude.ai",
    });
    assert.match(signed, /Signed in — user@example\.com/);
    assert.match(signed, /\(max\)/);
  });

  it("CLI missing banner offers Install Claude Code CLI", () => {
    const blocked = claudeCodeAuthBannerHtml({
      kind: "blocked",
      reason: "Claude Code CLI not found on PATH.",
      docsUrl: CLAUDE_CODE_DOCS_AUTH,
    });
    assert.match(blocked, /CLI missing/);
    assert.match(blocked, /data-cmd="installClaudeCodeCli"/);
    assert.doesNotMatch(blocked, /Signed in —/i);
  });
});
