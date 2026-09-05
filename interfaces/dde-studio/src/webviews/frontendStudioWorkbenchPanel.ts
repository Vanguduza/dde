import { randomUUID } from "node:crypto";
import * as path from "node:path";
import * as vscode from "vscode";
import { StudioGatewayService } from "../connection/studioGateway";

interface BridgeEnvelope {
  readonly kind?: string;
  readonly correlationId?: string;
  readonly payload?: unknown;
}

interface BridgeCommand {
  readonly commandId?: string;
  readonly commandType: string;
  readonly targetType: string;
  readonly targetId: string;
  readonly parameters: Record<string, unknown>;
  readonly idempotencyKey: string;
}

interface ReadQuery {
  readonly resource: string;
  readonly parameters?: Readonly<Record<string, unknown>>;
}

interface BridgeFailure {
  readonly errorCode: string;
  readonly message: string;
  readonly retryable: boolean;
  readonly details?: Readonly<Record<string, unknown>>;
}

/**
 * Canonical DDE-069 VS Code host for the full React workbench.
 *
 * The six contributed Frontend Studio sidebar WebviewViews are migration
 * shims. This panel is the central editor surface required by
 * FRONTEND_STUDIO_REV3 section 5.3. Feature code still only knows
 * DdeHostBridge; Gateway/session/VS Code APIs terminate here.
 */
export class FrontendStudioWorkbenchPanel implements vscode.Disposable {
  private panel?: vscode.WebviewPanel;
  private readonly pickedFiles = new Map<string, vscode.Uri>();

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly gateway: () => StudioGatewayService | undefined,
    private readonly missionId: () => string | null,
  ) {}

  show(): void {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Active, false);
      return;
    }
    const uiRoot = vscode.Uri.joinPath(this.context.extensionUri, "ui", "dist");
    this.panel = vscode.window.createWebviewPanel(
      "dde.frontendStudio.workbench",
      "DDE · Frontend Studio",
      vscode.ViewColumn.Active,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [uiRoot],
      },
    );
    this.panel.onDidDispose(() => {
      this.panel = undefined;
    });
    this.panel.webview.onDidReceiveMessage((message: BridgeEnvelope) => {
      void this.handle(message);
    });
    this.panel.webview.html = this.html(this.panel.webview, uiRoot);
  }

  dispose(): void {
    this.panel?.dispose();
    this.panel = undefined;
  }

  private async handle(message: BridgeEnvelope): Promise<void> {
    if (!this.panel) return;
    if (message.kind === "subscribe") return;
    const correlationId = message.correlationId;
    if (!correlationId) return;
    try {
      const result = await this.execute(message.kind ?? "", message.payload);
      await this.panel.webview.postMessage({ correlationId, result });
    } catch (error) {
      await this.panel.webview.postMessage({
        correlationId,
        error: failure(error),
      });
    }
  }

  private async execute(kind: string, payload: unknown): Promise<unknown> {
    switch (kind) {
      case "capabilities":
        return {
          canRevealFile: Boolean(vscode.workspace.workspaceFolders?.length),
          canOpenExternal: false,
          canNotify: true,
          canPickLocalFile: true,
          canSubscribeEvents: false,
        };
      case "read":
        return this.read(payload as ReadQuery);
      case "pickLocalFile":
        return this.pickLocalFile();
      case "uploadPickedFile":
        return this.uploadPickedFile(payload);
      case "command":
        return this.command(payload as BridgeCommand);
      case "revealFile":
        return this.revealFile(payload);
      case "notify":
        return this.notify(payload);
      case "openExternal":
        throw bridgeError(
          "FORBIDDEN",
          "External navigation is not admitted for the Frontend Studio host yet.",
        );
      default:
        throw bridgeError("FORBIDDEN", `Unsupported host bridge operation: ${kind}`);
    }
  }

  private requireContext(): { gateway: StudioGatewayService; missionId: string } {
    const gateway = this.gateway();
    if (!gateway) {
      throw bridgeError(
        "CONTEXT_INCOMPLETE",
        "Frontend Studio needs a configured, reachable DDE Gateway session.",
        true,
      );
    }
    const missionId = this.missionId();
    if (!missionId) {
      throw bridgeError(
        "CONTEXT_INCOMPLETE",
        "Set dde.studio.frontendMissionId to the DDE mission UUID for this workbench.",
      );
    }
    return { gateway, missionId };
  }

  private async read(query: ReadQuery): Promise<unknown> {
    if (!query || typeof query.resource !== "string") {
      throw bridgeError("VALIDATION_FAILED", "A Frontend Studio read resource is required.");
    }
    const { gateway, missionId } = this.requireContext();
    if (query.resource === "frontend.host.context") {
      const result = await gateway.readMission(missionId);
      if (!result.ok || !result.mission) {
        throw bridgeError("CONTEXT_INCOMPLETE", result.reason ?? "Mission read unavailable.");
      }
      return {
        missionId,
        projectId: result.mission.project_id,
        projectName: result.mission.title,
      };
    }
    if (query.resource === "frontend.studio.snapshot") {
      return camelizeResult(await gateway.readFrontendSnapshot(missionId));
    }
    if (query.resource === "frontend.chat.thread") {
      return camelizeResult(await gateway.readFrontendChat(missionId));
    }
    if (query.resource === "frontend.chat.conversations") {
      return camelizeResult(
        await gateway.readFrontendChats(missionId, {
          query: optionalParameter(query, "query"),
          includeArchived: query.parameters?.includeArchived === true,
        }),
      );
    }
    if (query.resource === "frontend.chat.thread.by_id") {
      const conversationId = requiredParameter(query, "conversationId");
      return camelizeResult(await gateway.readFrontendChatById(missionId, conversationId));
    }
    if (
      ["frontend.chat.attachments", "frontend.chat.plans", "frontend.chat.activities",
       "frontend.chat.checkpoints", "frontend.chat.changes"].includes(query.resource)
    ) {
      const conversationId = requiredParameter(query, "conversationId");
      const resource = query.resource.split(".").at(-1) as
        | "attachments" | "plans" | "activities" | "checkpoints" | "changes";
      return camelizeResult(
        await gateway.readFrontendChatSubresource(missionId, conversationId, resource),
      );
    }
    if (query.resource === "frontend.chat.models") {
      return camelizeResult(await gateway.readFrontendChatModels(missionId));
    }
    if (query.resource === "frontend.chat.context") {
      const conversationId = requiredParameter(query, "conversationId");
      const refs = stringArrayParameter(query, "refs");
      const budget = query.parameters?.budgetTokens;
      return camelizeResult(
        await gateway.readFrontendChatContext(
          missionId, conversationId, refs, typeof budget === "number" ? budget : 24_000,
        ),
      );
    }
    if (query.resource === "frontend.preview.document") {
      const previewSessionId = requiredParameter(query, "previewSessionId");
      return camelizeResult(
        await gateway.readFrontendPreview(missionId, previewSessionId),
      );
    }
    if (query.resource === "frontend.inspector.describe") {
      const candidateId = requiredParameter(query, "candidateId");
      const pxgKey = requiredParameter(query, "pxgKey");
      return camelizeResult(
        await gateway.readFrontendInspector(missionId, candidateId, pxgKey),
      );
    }
    throw bridgeError("FORBIDDEN", `Unsupported Frontend Studio read: ${query.resource}`);
  }

  private async command(command: BridgeCommand): Promise<unknown> {
    if (!command || typeof command.commandType !== "string") {
      throw bridgeError("VALIDATION_FAILED", "A Frontend Studio command is required.");
    }
    const { gateway, missionId } = this.requireContext();
    if (command.targetType !== "mission" || command.targetId !== missionId) {
      throw bridgeError(
        "TENANT_SCOPE_VIOLATION",
        "Workbench commands may address only the configured Frontend Studio mission.",
      );
    }
    const result = await gateway.sendFrontendCommand(
      command.commandType,
      missionId,
      command.parameters ?? {},
      command.idempotencyKey,
      command.commandId,
    );
    if (!result.ok || !result.acceptance) {
      throw bridgeError("POLICY_DENIED", result.reason ?? "Gateway command refused.");
    }
    return deepCamelize(result.acceptance);
  }

  private async revealFile(payload: unknown): Promise<void> {
    const ref = payload as { path?: unknown; line?: unknown };
    if (typeof ref?.path !== "string" || !ref.path) {
      throw bridgeError("VALIDATION_FAILED", "SourceFileRef.path is required.");
    }
    if (path.isAbsolute(ref.path) || ref.path.split(/[\\/]/).includes("..")) {
      throw bridgeError("POLICY_DENIED", "Source path must stay inside the open workspace.");
    }
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
      throw bridgeError("CONTEXT_INCOMPLETE", "No VS Code workspace is open.");
    }
    const uri = vscode.Uri.joinPath(folder.uri, ...ref.path.split(/[\\/]/));
    const document = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(document, { preview: true });
    if (typeof ref.line === "number" && ref.line > 0) {
      const line = Math.max(0, Math.min(document.lineCount - 1, ref.line - 1));
      const position = new vscode.Position(line, 0);
      editor.selection = new vscode.Selection(position, position);
      editor.revealRange(new vscode.Range(position, position));
    }
  }

  private async pickLocalFile(): Promise<{
    token: string; filename: string; mediaType: string; sizeBytes: number
  } | null> {
    const selected = await vscode.window.showOpenDialog({
      canSelectFiles: true,
      canSelectFolders: false,
      canSelectMany: false,
      openLabel: "Attach to DDE Chat",
    });
    const uri = selected?.[0];
    if (!uri) return null;
    const stat = await vscode.workspace.fs.stat(uri);
    const token = randomUUID();
    this.pickedFiles.set(token, uri);
    return {
      token,
      filename: path.basename(uri.fsPath || uri.path),
      mediaType: mediaTypeFor(uri.path),
      sizeBytes: stat.size,
    };
  }

  private async uploadPickedFile(payload: unknown): Promise<unknown> {
    const request = payload as {
      token?: unknown; conversationId?: unknown; attachmentId?: unknown; idempotencyKey?: unknown
    };
    if (
      typeof request.token !== "string" || typeof request.conversationId !== "string" ||
      typeof request.attachmentId !== "string" || typeof request.idempotencyKey !== "string"
    ) {
      throw bridgeError("VALIDATION_FAILED", "Picked-file upload request is incomplete.");
    }
    const uri = this.pickedFiles.get(request.token);
    if (!uri) throw bridgeError("CONTEXT_INCOMPLETE", "Picked-file token expired.");
    const { gateway, missionId } = this.requireContext();
    const bytes = await vscode.workspace.fs.readFile(uri);
    const result = await gateway.uploadFrontendChatAttachment(
      missionId, request.conversationId, request.attachmentId, bytes, request.idempotencyKey,
    );
    if (!result.ok || !result.value) {
      throw bridgeError("POLICY_DENIED", result.reason ?? "Attachment upload refused.");
    }
    this.pickedFiles.delete(request.token);
    return deepCamelize(result.value);
  }

  private async notify(payload: unknown): Promise<void> {
    const message = (payload as { message?: unknown })?.message;
    if (typeof message !== "string" || !message) {
      throw bridgeError("VALIDATION_FAILED", "Notification message is required.");
    }
    await vscode.window.showInformationMessage(message);
  }

  private html(webview: vscode.Webview, uiRoot: vscode.Uri): string {
    const script = webview.asWebviewUri(
      vscode.Uri.joinPath(uiRoot, "assets", "dde-studio.js"),
    );
    const style = webview.asWebviewUri(
      vscode.Uri.joinPath(uiRoot, "assets", "dde-studio.css"),
    );
    const nonce = nonceValue();
    return `<!doctype html>
<html lang="en" data-dde-theme="light">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; img-src ${webview.cspSource} data: blob:; script-src 'nonce-${nonce}' 'unsafe-inline'; frame-src 'self' data: blob:;" />
<link rel="stylesheet" href="${style}" />
<title>DDE Frontend Studio</title>
</head>
<body><div id="dde-root"></div><script nonce="${nonce}" type="module" src="${script}"></script></body>
</html>`;
  }
}


function optionalParameter(query: ReadQuery, name: string): string | undefined {
  const value = query.parameters?.[name];
  return typeof value === "string" && value ? value : undefined;
}

function stringArrayParameter(query: ReadQuery, name: string): string[] {
  const value = query.parameters?.[name];
  if (value === undefined) return [];
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw bridgeError("VALIDATION_FAILED", `Read parameter ${name} must be a string array.`);
  }
  return value;
}

function mediaTypeFor(value: string): string {
  const lower = value.toLowerCase();
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".json")) return "application/json";
  if (lower.endsWith(".md") || lower.endsWith(".txt") || lower.endsWith(".ts") ||
      lower.endsWith(".tsx") || lower.endsWith(".js") || lower.endsWith(".jsx") ||
      lower.endsWith(".py") || lower.endsWith(".css") || lower.endsWith(".html")) {
    return "text/plain";
  }
  return "application/octet-stream";
}

function requiredParameter(query: ReadQuery, name: string): string {
  const value = query.parameters?.[name];
  if (typeof value !== "string" || !value) {
    throw bridgeError("VALIDATION_FAILED", `Read parameter ${name} is required.`);
  }
  return value;
}

function camelizeResult(result: {
  ok: boolean;
  value?: Record<string, unknown>;
  reason?: string;
}): unknown {
  if (!result.ok || !result.value) {
    throw bridgeError("CONTEXT_INCOMPLETE", result.reason ?? "Frontend read unavailable.");
  }
  return deepCamelize(result.value);
}

function deepCamelize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(deepCamelize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => [
      key.replace(/_([a-z])/g, (_match, letter: string) => letter.toUpperCase()),
      deepCamelize(item),
    ]),
  );
}

function bridgeError(
  errorCode: string,
  message: string,
  retryable = false,
  details?: Readonly<Record<string, unknown>>,
): BridgeFailure {
  return { errorCode, message, retryable, details };
}

function failure(error: unknown): BridgeFailure {
  if (
    error &&
    typeof error === "object" &&
    "errorCode" in error &&
    "message" in error
  ) {
    return error as BridgeFailure;
  }
  return bridgeError(
    "CONTEXT_INCOMPLETE",
    error instanceof Error ? error.message : String(error),
  );
}

function nonceValue(): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let value = "";
  for (let index = 0; index < 32; index += 1) {
    value += alphabet.charAt(Math.floor(Math.random() * alphabet.length));
  }
  return value;
}
