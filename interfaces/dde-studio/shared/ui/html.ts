import type { AuthState } from "../authTypes";
import {
  claudeCodeAuthBannerHtml,
  type ClaudeCodeAuthState,
} from "../claudeAuth";

import type { ProbeState } from "../healthClient";

import type { StudioConnection } from "../settings";

import {

  type HarnessId,

  type MissionSummary,

  type RunSummary,

} from "../stubGateway";

import type { ModuleDescriptor } from "../registry";

import {

  escapeHtml,

  messageBridgeScript,

  renderProbeHtml,

  sharedStyles,

} from "./base";

import {

  missionControlBody,

  missionControlHeader,

  missionControlStyles,

} from "./missionControl";

import { modulePanelHtml } from "./panels";



export {

  escapeHtml,

  messageBridgeScript,

  renderProbeHtml,

  sharedStyles,

} from "./base";

export { modulePanelHtml, morningReviewHtml } from "./panels";

export {

  MISSION_CONTROL_SECTIONS,

  missionControlBody,

  missionControlHeader,

} from "./missionControl";

export {

  OVERVIEW_ZONES,

  overviewHtml,

  overviewStyles,

} from "./overview";



function authBanner(auth: AuthState): string {

  if (auth.kind === "session") {

    return `<span class="pill ok">session</span>`;

  }

  return `<span class="pill">unauthenticated</span>`;

}



export function connectionHtml(

  connection: StudioConnection | undefined,

  state: ProbeState,

  auth: AuthState,

  configError?: string,

  opts?: {
    desktop?: boolean;
    applianceStatus?: string;
    /** True when shipping inside DDE-Complete-Setup (wizard + Core co-installed). */
    unifiedInstall?: boolean;
    claudeAuth?: ClaudeCodeAuthState;
  },

): string {

  const connBlock = connection

    ? `

      <table>

        <tr><th>Preferred</th><td>${escapeHtml(connection.preferredTarget)}</td></tr>

        <tr><th>Local Core</th><td><code>${escapeHtml(connection.coreUrl)}</code></td></tr>

        <tr><th>Cloud URL</th><td><code>${escapeHtml(connection.cloudUrl || "—")}</code></td></tr>

        <tr><th>Effective</th><td><code>${escapeHtml(connection.effectiveUrl)}</code></td></tr>

      </table>`

    : `<p class="muted">${escapeHtml(configError ?? "—")}</p>`;



  const applianceBlock = opts?.desktop

    ? `

  <h2>Local Core</h2>

  <div class="banner">

    <div class="muted" style="margin:0 0 8px">${escapeHtml(opts.applianceStatus ?? "—")}</div>

    <div class="row">

      <button type="button" data-cmd="runSetupWizard">Setup wizard</button>

      <button type="button" data-cmd="startLocalCore">Start local Core</button>

      <button type="button" class="secondary" data-cmd="stopLocalCore">Stop local Core</button>

    </div>

  </div>`

    : "";



  // unifiedInstall reserved for future appliance path labels

  void opts?.unifiedInstall;



  const settingsBtn = opts?.desktop

    ? `<button type="button" class="secondary" data-cmd="openSettings">Edit connection</button>`

    : `<button type="button" class="secondary" data-cmd="openSettings">Open settings</button>`;



  return `<!DOCTYPE html>

<html lang="en">

<head>

  <meta charset="UTF-8" />

  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />

  <style>${sharedStyles()}</style>

</head>

<body>

  <a class="skip-link" href="#main">Skip to content</a>

  <main id="main">

  <h1>DDE Connection</h1>



  <h2>Live status</h2>

  <div class="banner" role="status" aria-live="polite">${renderProbeHtml(state)}</div>



  <h2>Auth</h2>

  <div class="banner">${authBanner(auth)}</div>



  <h2>Claude Code</h2>
  ${claudeCodeAuthBannerHtml(opts?.claudeAuth ?? { kind: "none" })}



  <h2>Endpoints</h2>

  <div class="banner">${connBlock}</div>

  ${applianceBlock}



  <div class="row">

    <button type="button" data-cmd="refresh">Refresh health</button>

    ${settingsBtn}

    <button type="button" class="secondary" data-cmd="useLocal">Use local</button>

    <button type="button" class="secondary" data-cmd="useCloud">Use cloud</button>

    <button type="button" class="secondary" data-cmd="setSessionToken">Set session token</button>

    <button type="button" class="secondary" data-cmd="clearSessionToken">Clear session</button>

  </div>

  </main>



  <script>${messageBridgeScript()}</script>

</body>

</html>`;

}



/** Delegates to rich §4/§5 layouts in panels.ts. */

export function moduleStubHtml(

  module: ModuleDescriptor,

): string {

  return modulePanelHtml(module);

}



export function harnessHtml(opts: {
  harness: HarnessId;
  missions: MissionSummary[];
  runs: RunSummary[];
  panel?: boolean;
  claudeAuth?: ClaudeCodeAuthState;
}): string {

  return `<!DOCTYPE html>

<html lang="en">

<head>

  <meta charset="UTF-8" />

  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />

  <style>${sharedStyles()}${missionControlStyles()}</style>

</head>

<body>

  <a class="skip-link" href="#main">Skip to content</a>

  <main id="main" data-surface="mission-control" data-harness="${escapeHtml(opts.harness)}">

  ${missionControlHeader({ harness: opts.harness, panel: opts.panel, claudeAuth: opts.claudeAuth })}

  ${missionControlBody({

    missions: opts.missions,

    runs: opts.runs,

  })}

  </main>



  <script>${messageBridgeScript()}</script>

</body>

</html>`;

}



export function settingsFormHtml(connection: StudioConnection): string {

  return `<!DOCTYPE html>

<html lang="en">

<head>

  <meta charset="UTF-8" />

  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';" />

  <style>${sharedStyles()}</style>

</head>

<body>

  <a class="skip-link" href="#main">Skip to content</a>

  <main id="main">

  <h1>Connection settings</h1>

  <label class="field" for="coreUrl">Local Core URL</label>

  <input id="coreUrl" value="${escapeHtml(connection.coreUrl)}" />

  <label class="field" for="cloudUrl">Cloud URL</label>

  <input id="cloudUrl" value="${escapeHtml(connection.cloudUrl)}" />

  <label class="field" for="preferredTarget">Preferred target</label>

  <select id="preferredTarget">

    <option value="local" ${connection.preferredTarget === "local" ? "selected" : ""}>local</option>

    <option value="cloud" ${connection.preferredTarget === "cloud" ? "selected" : ""}>cloud</option>

  </select>

  <label class="field" for="pollIntervalMs">Poll interval (ms)</label>

  <input id="pollIntervalMs" type="number" min="1000" value="${connection.pollIntervalMs}" />

  <div class="row">

    <button type="button" id="save">Save</button>

    <button type="button" class="secondary" data-cmd="refresh">Cancel</button>

  </div>

  </main>

  <script>

    ${messageBridgeScript()}

    document.getElementById("save").addEventListener("click", () => {

      api.postMessage({

        type: "saveSettings",

        coreUrl: document.getElementById("coreUrl").value,

        cloudUrl: document.getElementById("cloudUrl").value,

        preferredTarget: document.getElementById("preferredTarget").value,

        pollIntervalMs: Number(document.getElementById("pollIntervalMs").value),

      });

    });

  </script>

</body>

</html>`;

}


