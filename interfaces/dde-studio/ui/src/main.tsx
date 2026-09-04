/** VS Code / Electron entry point. The only place a host bridge is chosen. */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DdeStudioApp } from "./app/DdeStudioApp";
import { VsCodeHostBridge } from "./bridge/VsCodeHostBridge";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/panels.css";

const container = document.getElementById("dde-root");
if (container) {
  createRoot(container).render(
    <StrictMode>
      <DdeStudioApp bridge={new VsCodeHostBridge()} />
    </StrictMode>,
  );
}
