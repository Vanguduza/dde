/** Auth state shape shared by extension and Electron (no vscode imports). */

export type AuthState =
  | { kind: "unauthenticated" }
  | { kind: "session"; hasToken: true };
