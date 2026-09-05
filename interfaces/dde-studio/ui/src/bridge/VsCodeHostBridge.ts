/**
 * The one module in the workbench allowed to touch the VS Code webview API.
 *
 * Everything else goes through `DdeHostBridge`, so a VS Code assumption
 * cannot leak into a feature component that Electron then has to work
 * around (FS-GAP-002).
 */

import type {
  CommandAcceptance,
  DdeCommand,
  DdeEvent,
  DdeHostBridge,
  DdeReadQuery,
  EventFilter,
  HostCapabilities,
  PickedFileUploadRequest,
  PickedLocalFile,
  SourceFileRef,
  Unsubscribe,
} from "./DdeHostBridge";
import { DdeBridgeError } from "./DdeHostBridge";

interface VsCodeApi {
  postMessage(message: unknown): void;
}

declare function acquireVsCodeApi(): VsCodeApi;

interface PendingCall {
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}

export class VsCodeHostBridge implements DdeHostBridge {
  readonly hostKind = "vscode" as const;

  private readonly api: VsCodeApi;
  private readonly pending = new Map<string, PendingCall>();
  private readonly listeners = new Set<{
    filter: EventFilter;
    onEvent: (event: DdeEvent) => void;
  }>();
  private nextId = 0;

  constructor(api: VsCodeApi = acquireVsCodeApi()) {
    this.api = api;
    window.addEventListener("message", (event) => this.receive(event.data));
  }

  private receive(message: unknown): void {
    if (typeof message !== "object" || message === null) return;
    const envelope = message as {
      correlationId?: string;
      error?: { errorCode: string; message: string; retryable: boolean };
      result?: unknown;
      event?: DdeEvent;
    };
    if (envelope.event) {
      for (const listener of this.listeners) {
        if (listener.filter.types.includes(envelope.event.type)) {
          listener.onEvent(envelope.event);
        }
      }
      return;
    }
    if (!envelope.correlationId) return;
    const call = this.pending.get(envelope.correlationId);
    if (!call) return;
    this.pending.delete(envelope.correlationId);
    if (envelope.error) {
      call.reject(new DdeBridgeError(envelope.error));
      return;
    }
    call.resolve(envelope.result);
  }

  private call<T>(kind: string, payload: unknown): Promise<T> {
    const correlationId = `c${this.nextId++}`;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(correlationId, {
        resolve: resolve as (value: unknown) => void,
        reject,
      });
      this.api.postMessage({ kind, correlationId, payload });
    });
  }

  getCapabilities(): Promise<HostCapabilities> {
    return this.call<HostCapabilities>("capabilities", {});
  }

  sendCommand(command: DdeCommand): Promise<CommandAcceptance> {
    return this.call<CommandAcceptance>("command", command);
  }

  requestRead<T>(query: DdeReadQuery): Promise<T> {
    return this.call<T>("read", query);
  }

  subscribeEvents(
    filter: EventFilter,
    onEvent: (event: DdeEvent) => void,
  ): Unsubscribe {
    const listener = { filter, onEvent };
    this.listeners.add(listener);
    this.api.postMessage({ kind: "subscribe", payload: filter });
    return () => {
      this.listeners.delete(listener);
    };
  }

  revealFile(ref: SourceFileRef): Promise<void> {
    return this.call<void>("revealFile", ref);
  }

  openExternal(target: string): Promise<void> {
    return this.call<void>("openExternal", { target });
  }

  showNativeNotification(message: string): Promise<void> {
    return this.call<void>("notify", { message });
  }

  pickLocalFile(): Promise<PickedLocalFile | null> {
    return this.call<PickedLocalFile | null>("pickLocalFile", {});
  }

  uploadPickedFile(
    request: PickedFileUploadRequest,
  ): Promise<Record<string, unknown>> {
    return this.call<Record<string, unknown>>("uploadPickedFile", request);
  }
}
