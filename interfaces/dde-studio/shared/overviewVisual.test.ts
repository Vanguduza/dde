/**

 * Visual / DOM structure regression for Mission Overview.

 * Pure string + class snapshot — no GUI, runs on Windows via node --test.

 *

 * Run: npm run test:visual  (also included in npm test)

 */



import assert from "node:assert/strict";

import { describe, it } from "node:test";



import { readConnection } from "./settings";

import { OVERVIEW_ZONES, overviewHtml, overviewStyles } from "./ui/overview";

import type { ProbeState } from "./healthClient";



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



/**

 * Stable structural fingerprint of overview markup (zones + key chrome classes).

 * Bump intentionally when mockup alignment changes layout — not for copy tweaks.

 */

const EXPECTED_STRUCTURE = [

  'data-surface="overview"',

  'class="ov-header"',

  'class="ov-sys',

  'data-zone="system"',

  'class="ov-actions-bar"',

  'data-bind="operator-actions"',

  'class="ov-spine"',

  'data-zone="spine"',

  'class="ov-body"',

  'class="ov-sidebar"',

  'class="ov-main"',

  'class="ov-modules"',

  'class="ov-fleet-grid"',

  'class="ov-panel ov-activity"',

  'class="ov-panel ov-attention"',

  'class="ov-empty"',

  'data-cmd="openSettings"',

  'data-cmd="refresh"',

  'data-cmd="startMission"',

  'data-harness="hermes"',

  'data-harness="claude-code"',

  'data-harness="deepseek"',

] as const;



const EXPECTED_STYLE_TOKENS = [

  "[data-surface=\"overview\"]",

  ".ov-body",

  ".ov-spine-step",

  ".ov-fleet-grid",

  ".ov-modules",

  ".ov-sys-tone-ok",

  "@media (max-width: 960px)",

] as const;



describe("overview visual structure snapshot", () => {

  it("emits expected zone + chrome class fingerprint", () => {

    const connection = readConnection(() => undefined);

    const html = overviewHtml(connection, probe);



    for (const zone of OVERVIEW_ZONES) {

      assert.match(html, new RegExp(`data-zone="${zone}"`));

    }

    for (const token of EXPECTED_STRUCTURE) {

      assert.ok(

        html.includes(token),

        `missing structure token: ${token}`,

      );

    }



    // Spine step count (1..8)

    for (let i = 1; i <= 8; i++) {

      assert.match(html, new RegExp(`class="ov-spine-index">${i}<`));

    }



    // No helper footnote / lecture blocks

    assert.doesNotMatch(html, /ov-footnote|Live today:|Activity will appear|All clear!/);

  });



  it("overviewStyles include mockup layout tokens", () => {

    const css = overviewStyles();

    for (const token of EXPECTED_STYLE_TOKENS) {

      assert.ok(css.includes(token), `missing style token: ${token}`);

    }

  });



  it("ready probe paints ok system strip tone", () => {

    const connection = readConnection(() => undefined);

    const html = overviewHtml(connection, probe);

    assert.match(html, /ov-sys-tone-ok/);

    assert.match(html, /Core ready/);

  });



  it("unreachable probe paints err system strip tone", () => {

    const connection = readConnection(() => undefined);

    const bad: ProbeState = {

      kind: "unreachable",

      url: "http://127.0.0.1:8000",

      error: "ECONNREFUSED",

      checkedAt: "2026-01-01T00:00:00.000Z",

    };

    const html = overviewHtml(connection, bad);

    assert.match(html, /ov-sys-tone-err/);

    assert.match(html, /Core unreachable/);

  });

});


