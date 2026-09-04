/**
 * DDE-069 host bridge contract (FS-GAP-002).
 *
 * Feature code never calls `acquireVsCodeApi()` or any other host API. It
 * calls this interface, and exactly one module per host implements it. That
 * is what lets the same Frontend Studio run inside VS Code, inside the
 * Electron DDE Code shell and inside a test harness without the feature
 * layer knowing which it is — and what stops a VS Code assumption leaking
 * into a component that Electron then has to work around.
 */

/** A command sent through the Gateway. Mirrors the `/v1/commands` body. */
export interface DdeCommand {
  readonly commandType: string;
  readonly targetType: "mission" | "project" | "device";
  readonly targetId: string;
  readonly parameters: Readonly<Record<string, unknown>>;
  /**
   * Supplied by the caller so a retry replays rather than duplicating.
   * The bridge never invents one: an idempotency key chosen by the
   * transport would make two distinct user actions collide.
   */
  readonly idempotencyKey: string;
}

export interface CommandAcceptance {
  readonly commandId: string;
  readonly status: "accepted";
  readonly targetType: string;
  readonly targetId: string;
  readonly payload: Readonly<Record<string, unknown>>;
}

/** A typed refusal. Mirrors DDE's canonical error contract. */
export interface DdeErrorPayload {
  readonly errorCode: string;
  readonly message: string;
  readonly retryable: boolean;
  readonly details?: Readonly<Record<string, unknown>>;
}

export interface DdeReadQuery {
  readonly resource: string;
  readonly parameters?: Readonly<Record<string, unknown>>;
}

export interface DdeEvent {
  readonly type: string;
  readonly payload: Readonly<Record<string, unknown>>;
}

export interface EventFilter {
  readonly types: readonly string[];
}

export type Unsubscribe = () => void;

export interface SourceFileRef {
  readonly path: string;
  readonly line?: number;
}

/**
 * What this host can actually do. Feature code must branch on these rather
 * than assume: an action the host cannot perform is rendered disabled with
 * a reason, never rendered as though it will work.
 */
export interface HostCapabilities {
  readonly canRevealFile: boolean;
  readonly canOpenExternal: boolean;
  readonly canNotify: boolean;
  readonly canPickLocalFile: boolean;
  /**
   * Whether the host can deliver server events. When false the studio
   * polls and says so, rather than showing a live badge it cannot back.
   */
  readonly canSubscribeEvents: boolean;
}

export interface DdeHostBridge {
  readonly hostKind: "vscode" | "electron" | "test";
  getCapabilities(): Promise<HostCapabilities>;
  sendCommand(command: DdeCommand): Promise<CommandAcceptance>;
  requestRead<T>(query: DdeReadQuery): Promise<T>;
  subscribeEvents(
    filter: EventFilter,
    onEvent: (event: DdeEvent) => void,
  ): Unsubscribe;
  revealFile(ref: SourceFileRef): Promise<void>;
  openExternal(target: string): Promise<void>;
  showNativeNotification(message: string): Promise<void>;
  pickLocalFile?(): Promise<string | null>;
}

/** Raised when a bridge call is refused by DDE rather than by transport. */
export class DdeBridgeError extends Error {
  readonly errorCode: string;
  readonly retryable: boolean;
  readonly details: Readonly<Record<string, unknown>>;

  constructor(payload: DdeErrorPayload) {
    super(payload.message);
    this.name = "DdeBridgeError";
    this.errorCode = payload.errorCode;
    this.retryable = payload.retryable;
    this.details = payload.details ?? {};
  }
}
