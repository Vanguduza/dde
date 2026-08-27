import { escapeHtml } from "./html";
import { RadiusScalePx, SemanticColors, SpacingScalePx } from "./tokens";

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
  const action = view === "canvas"
    ? canvasAuthoringHtml()
    : commands.length
    ? `<form id="studio-command">
        <label>Mission UUID<input id="mission-id" required autocomplete="off" /></label>
        <label>Command<select id="command-type">${options}</select></label>
        <label>Structured parameters (JSON object)<textarea id="parameters" rows="8">{}</textarea></label>
        <button type="submit">Send command</button>
      </form>`
    : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <style>:root{--space-1:${SpacingScalePx.space1}px;--space-2:${SpacingScalePx.space2}px;--space-3:${SpacingScalePx.space3}px}
    body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:12px}
    nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}button,input,select,textarea{font:inherit}
    label{display:grid;gap:var(--space-1);margin:var(--space-2) 0}input,select,textarea{padding:var(--space-2);background:var(--vscode-input-background);color:var(--vscode-input-foreground);border:1px solid var(--vscode-input-border)}
    .empty{padding:var(--space-3);border:1px dashed var(--vscode-panel-border)}.status{min-height:1.5em}</style></head>
    <body data-frontend-studio-view="${view}"><h1>${copy.title}</h1>
    <nav aria-label="Frontend Studio"><span>Home</span><span>Intake</span><span>Donors</span><span>Canvas</span><span>Verify</span><span>Approvals</span></nav>
    <section class="empty" data-bind="live-results">${copy.empty}</section>${action}
    <p class="status" role="status">${escapeHtml(status)}</p>
    <script>const vscode=acquireVsCodeApi();const form=document.getElementById('studio-command');
    if(form){form.addEventListener('submit',(event)=>{event.preventDefault();let parameters;
    try{parameters=JSON.parse(document.getElementById('parameters').value);if(!parameters||Array.isArray(parameters)||typeof parameters!=='object')throw new Error();}
    catch{document.querySelector('.status').textContent='Parameters must be a JSON object.';return;}
    vscode.postMessage({type:'frontendCommand',missionId:document.getElementById('mission-id').value,
    commandType:document.getElementById('command-type').value,parameters});});}
    const palette=document.getElementById('component-palette');const drop=document.getElementById('canvas-drop-zone');let lifted='button';
    const common=()=>({workspace_id:document.getElementById('workspace-id').value,screen_file:document.getElementById('screen-file').value});
    const sendInsert=(kind)=>vscode.postMessage({type:'frontendCommand',missionId:document.getElementById('mission-id').value,
      commandType:'frontend.canvas.insert_component',parameters:{...common(),component_ref:kind,anchor_parent:'root',position_index:0,label:kind}});
    if(palette){palette.querySelectorAll('[data-component-kind]').forEach((button)=>{
      button.addEventListener('click',()=>sendInsert(button.dataset.componentKind));
      button.addEventListener('dragstart',(event)=>{lifted=button.dataset.componentKind;event.dataTransfer.setData('text/plain',lifted);});
    });}
    if(drop){drop.addEventListener('dragover',(event)=>event.preventDefault());drop.addEventListener('drop',(event)=>{event.preventDefault();sendInsert(event.dataTransfer.getData('text/plain')||lifted);});}
    const property=document.getElementById('token-property');const value=document.getElementById('token-value');
    if(property&&value){property.addEventListener('change',()=>{const values=JSON.parse(value.dataset[property.value]);value.replaceChildren(...values.map((item)=>{const option=document.createElement('option');option.value=item;option.textContent=item;return option;}));});
      document.getElementById('apply-token').addEventListener('click',()=>vscode.postMessage({type:'frontendCommand',missionId:document.getElementById('mission-id').value,
      commandType:'frontend.canvas.update_element',parameters:{...common(),element_id:document.getElementById('element-id').value,property:property.value,value:value.value}}));}</script></body></html>`;
}

function options(values: readonly string[]): string {
  return values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

function canvasAuthoringHtml(): string {
  const colors = Object.keys(SemanticColors);
  const spacing = Object.keys(SpacingScalePx);
  const radii = Object.keys(RadiusScalePx).map((item) => item.replace("--radius-", ""));
  return `<section aria-label="Canvas authoring">
    <label>Mission UUID<input id="mission-id" required autocomplete="off" /></label>
    <label>Workspace UUID<input id="workspace-id" required autocomplete="off" /></label>
    <label>Screen file<input id="screen-file" required pattern="[A-Za-z0-9._-]+\\.html" /></label>
    <div id="component-palette" aria-label="Component palette">
      ${["layout", "text", "button"].map((kind) => `<button type="button" draggable="true" data-component-kind="${kind}">Add ${kind}</button>`).join("")}
    </div>
    <div id="canvas-drop-zone" tabindex="0" role="button" aria-label="Insert selected component at root">Drop at root</div>
    <label>Selected element ID<input id="element-id" autocomplete="off" /></label>
    <label>Property<select id="token-property">${options(["color", "spacing", "radius"])}</select></label>
    <label>Token value<select id="token-value" data-color="${escapeHtml(JSON.stringify(colors))}"
      data-spacing="${escapeHtml(JSON.stringify(spacing))}" data-radius="${escapeHtml(JSON.stringify(radii))}">${options(colors)}</select></label>
    <button type="button" id="apply-token">Apply token</button>
    <p class="status" role="status"></p>
  </section>`;
}
