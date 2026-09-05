/**
 * An in-memory bridge for tests and for the golden structural fixture.
 *
 * It is deliberately not a "mock that always succeeds": commands and reads
 * must be registered, and an unregistered one throws. A workbench test that
 * passes because the bridge invented an answer would prove nothing, and a
 * fixture that renders plausible numbers nobody wired is exactly the
 * product theatre this mission forbids.
 */

import type {
  CommandAcceptance,
  DdeCommand,
  DdeEvent,
  DdeHostBridge,
  DdeReadQuery,
  EventFilter,
  HostCapabilities,
  SourceFileRef,
  Unsubscribe,
} from "./DdeHostBridge";
import { DdeBridgeError } from "./DdeHostBridge";

export type TestReadHandler = (query: DdeReadQuery) => unknown | Promise<unknown>;
export type TestCommandHandler = (
  command: DdeCommand,
) => Record<string, unknown> | Promise<Record<string, unknown>>;

export interface TestHostBridgeOptions {
  readonly capabilities?: Partial<HostCapabilities>;
  readonly reads?: Readonly<Record<string, unknown | TestReadHandler>>;
  readonly commands?: Readonly<
    Record<string, Record<string, unknown> | TestCommandHandler>
  >;
}

const DEFAULT_CAPABILITIES: HostCapabilities = {
  canRevealFile: false,
  canOpenExternal: false,
  canNotify: false,
  canPickLocalFile: false,
  canSubscribeEvents: false,
};

export class TestHostBridge implements DdeHostBridge {
  readonly hostKind = "test" as const;

  readonly sentCommands: DdeCommand[] = [];
  readonly revealedFiles: SourceFileRef[] = [];

  private readonly capabilities: HostCapabilities;
  private readonly reads: Record<string, unknown | TestReadHandler>;
  private readonly commands: Record<
    string,
    Record<string, unknown> | TestCommandHandler
  >;
  private readonly listeners = new Set<{
    filter: EventFilter;
    onEvent: (event: DdeEvent) => void;
  }>();

  constructor(options: TestHostBridgeOptions = {}) {
    this.capabilities = { ...DEFAULT_CAPABILITIES, ...options.capabilities };
    this.reads = { ...(options.reads ?? {}) };
    this.commands = { ...(options.commands ?? {}) };
  }

  setRead(resource: string, value: unknown | TestReadHandler): void {
    this.reads[resource] = value;
  }

  setCommand(
    commandType: string,
    value: Record<string, unknown> | TestCommandHandler,
  ): void {
    this.commands[commandType] = value;
  }

  emit(event: DdeEvent): void {
    for (const listener of this.listeners) {
      if (listener.filter.types.includes(event.type)) listener.onEvent(event);
    }
  }

  async getCapabilities(): Promise<HostCapabilities> {
    return this.capabilities;
  }

  async sendCommand(command: DdeCommand): Promise<CommandAcceptance> {
    this.sentCommands.push(command);
    const registered = this.commands[command.commandType];
    if (registered === undefined) {
      throw new DdeBridgeError({
        errorCode: "FORBIDDEN",
        message: `no registered response for ${command.commandType}`,
        retryable: false,
      });
    }
    const payload =
      typeof registered === "function" ? await registered(command) : registered;
    return {
      commandId: `test-${this.sentCommands.length}`,
      status: "accepted",
      targetType: command.targetType,
      targetId: command.targetId,
      payload,
    };
  }

  async requestRead<T>(query: DdeReadQuery): Promise<T> {
    if (!(query.resource in this.reads)) {
      throw new DdeBridgeError({
        errorCode: "CONTEXT_INCOMPLETE",
        message: `no registered read for ${query.resource}`,
        retryable: false,
      });
    }
    const registered = this.reads[query.resource];
    const value =
      typeof registered === "function" ? await registered(query) : registered;
    return value as T;
  }

  subscribeEvents(
    filter: EventFilter,
    onEvent: (event: DdeEvent) => void,
  ): Unsubscribe {
    const listener = { filter, onEvent };
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async revealFile(ref: SourceFileRef): Promise<void> {
    this.revealedFiles.push(ref);
  }

  async openExternal(): Promise<void> {}

  async showNativeNotification(): Promise<void> {}
}
