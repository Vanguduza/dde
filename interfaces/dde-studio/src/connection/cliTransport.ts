/**
 * S1 transport bridge (planning doc §3.1a).
 *
 * Until Gateway (DDE-027, S3) or CLI --json (DDE-015) exists, this remains
 * a non-operational seam. Do not invent REST shapes from the client.
 */

export class CliTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CliTransportError";
  }
}

export interface CliJsonTransport {
  /** Run `dde <args…>` and parse stdout as JSON. */
  runJson<T>(args: readonly string[]): Promise<T>;
}

/**
 * Placeholder. Confirm `--json` on mission/task/route/worker commands when
 * DDE-015 is scoped (planning §8.2).
 */
export class StubCliJsonTransport implements CliJsonTransport {
  async runJson<T>(_args: readonly string[]): Promise<T> {
    throw new CliTransportError(
      "CLI-JSON bridge waiting on DDE-015 (`dde … --json`). " +
        "Client stays on /healthz+/readyz until CLI or Gateway mission APIs exist.",
    );
  }
}
