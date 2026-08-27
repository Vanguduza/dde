import { escapeHtml } from "./html";

export type FrontendStudioView =
  | "home"
  | "intake"
  | "donors"
  | "canvas"
  | "verify"
  | "approvals";

const COPY: Record<FrontendStudioView, { title: string; empty: string }> = {
  home: { title: "Frontend Studio", empty: "Enter a mission UUID to inspect its live status." },
  intake: { title: "Intake", empty: "No compiled generation prompt loaded." },
  donors: { title: "Donors", empty: "No grouped donor results loaded." },
  canvas: { title: "Canvas", empty: "Select a real prototype screen before authoring." },
  verify: { title: "Verify", empty: "No verification evidence loaded." },
  approvals: { title: "Approvals", empty: "No adoption or pixel-signoff requests loaded." },
};

const COMMANDS: Partial<Record<FrontendStudioView, readonly string[]>> = {
  intake: ["frontend.intake.compile_prompt"],
  donors: ["frontend.donors.run_discovery", "frontend.donors.submit_uri", "frontend.donors.request_adoption"],
  canvas: [
    "frontend.canvas.insert_component",
    "frontend.canvas.move_component",
    "frontend.canvas.update_element",
    "frontend.canvas.remove_element",
    "frontend.motion.set_animation",
    "frontend.flow.upsert_step",
  ],
  approvals: ["frontend.prototype.request_pixel_signoff"],
};

/** Honest DDE-067 shell: no sample rows and no quality verdicts. */
export function frontendStudioHtml(view: FrontendStudioView, status = ""): string {
  const copy = COPY[view];
  const commands = COMMANDS[view] ?? [];
  const options = commands.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
  const action = commands.length
    ? `<form id="studio-command">
        <label>Mission UUID<input id="mission-id" required autocomplete="off" /></label>
        <label>Command<select id="command-type">${options}</select></label>
        <label>Structured parameters (JSON object)<textarea id="parameters" rows="8">{}</textarea></label>
        <button type="submit">Send command</button>
      </form>`
    : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <style>body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:12px}
    nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}button,input,select,textarea{font:inherit}
    label{display:grid;gap:5px;margin:10px 0}input,select,textarea{padding:7px;background:var(--vscode-input-background);color:var(--vscode-input-foreground);border:1px solid var(--vscode-input-border)}
    .empty{padding:14px;border:1px dashed var(--vscode-panel-border)}.status{min-height:1.5em}</style></head>
    <body data-frontend-studio-view="${view}"><h1>${copy.title}</h1>
    <nav aria-label="Frontend Studio"><span>Home</span><span>Intake</span><span>Donors</span><span>Canvas</span><span>Verify</span><span>Approvals</span></nav>
    <section class="empty" data-bind="live-results">${copy.empty}</section>${action}
    <p class="status" role="status">${escapeHtml(status)}</p>
    <script>const vscode=acquireVsCodeApi();const form=document.getElementById('studio-command');
    if(form){form.addEventListener('submit',(event)=>{event.preventDefault();let parameters;
    try{parameters=JSON.parse(document.getElementById('parameters').value);if(!parameters||Array.isArray(parameters)||typeof parameters!=='object')throw new Error();}
    catch{document.querySelector('.status').textContent='Parameters must be a JSON object.';return;}
    vscode.postMessage({type:'frontendCommand',missionId:document.getElementById('mission-id').value,
    commandType:document.getElementById('command-type').value,parameters});});}</script></body></html>`;
}
