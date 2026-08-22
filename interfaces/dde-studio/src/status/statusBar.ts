import * as vscode from "vscode";
import type { ProbeState } from "../connection/healthClient";

export class CoreStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      100,
    );
    this.item.command = "dde.studio.openConnection";
    this.item.tooltip = "DDE Code connection — click for Connection view";
    this.item.show();
  }

  update(state: ProbeState): void {
    switch (state.kind) {
      case "idle":
        this.item.text = "$(debug-disconnect) DDE: idle";
        this.item.backgroundColor = undefined;
        break;
      case "checking":
        this.item.text = "$(sync~spin) DDE: checking…";
        this.item.backgroundColor = undefined;
        break;
      case "ok": {
        const ready = state.readyz.status === "ready";
        this.item.text = ready
          ? "$(pass-filled) DDE: ready"
          : "$(warning) DDE: not ready";
        this.item.backgroundColor = ready
          ? undefined
          : new vscode.ThemeColor("statusBarItem.warningBackground");
        break;
      }
      case "unreachable":
        this.item.text = "$(error) DDE: down";
        this.item.backgroundColor = new vscode.ThemeColor(
          "statusBarItem.errorBackground",
        );
        break;
      case "misconfigured":
        this.item.text = "$(gear) DDE: config";
        this.item.backgroundColor = new vscode.ThemeColor(
          "statusBarItem.warningBackground",
        );
        break;
    }
  }

  dispose(): void {
    this.item.dispose();
  }
}
