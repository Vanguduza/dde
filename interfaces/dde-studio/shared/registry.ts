/**
 * Module map for the DDE Code suite (planning doc §7).
 * Shared by VS Code extension and Electron desktop shell.
 *
 * status meanings:
 * - exists — live client surface against a real Core endpoint today
 * - stub — UI shell with honest empty / blocked copy (no fake data)
 * - planned — not contributed to the sidebar yet
 */

export type ModuleId =
  | "dde-core-ui"
  | "dde-mission"
  | "dde-integration"
  | "dde-context"
  | "dde-routing"
  | "dde-workers"
  | "dde-verification"
  | "dde-approvals"
  | "dde-chat"
  | "dde-donor"
  | "dde-knowledge"
  | "dde-evaluation"
  | "dde-debug"
  | "product-environment";

export type ModuleStage = "S1" | "S3" | "S4" | "S5" | "S7";

export interface ModuleDescriptor {
  id: ModuleId;
  title: string;
  viewId?: string;
  earliestStage: ModuleStage;
  chapters: string;
  status: "exists" | "stub" | "planned";
  summary: string;
  /** What this view can show today without inventing Core APIs. */
  liveToday: string;
}

/**
 * Full research module list from planning doc §7 (order preserved).
 * Tests assert MODULE_REGISTRY covers every id here.
 */
export const RESEARCH_MODULE_IDS: readonly ModuleId[] = [
  "dde-core-ui",
  "dde-chat",
  "dde-mission",
  "dde-integration",
  "dde-context",
  "dde-routing",
  "dde-workers",
  "dde-verification",
  "dde-approvals",
  "dde-donor",
  "dde-knowledge",
  "dde-evaluation",
  "dde-debug",
  "product-environment",
] as const;

/** Sidebar / activity webview stubs (not Connection, not harness worker tabs). */
export const SIDEBAR_STUB_MODULES: readonly ModuleDescriptor[] = [
  {    id: "dde-mission",
    title: "Mission",
    viewId: "dde.studio.mission",
    earliestStage: "S1",
    chapters: "Ch.4",
    status: "stub",
    summary:
      "Mission / Tasks tree and TaskGraph state. Blocked on DDE-015 CLI --json or Gateway GET /v1/missions.",
    liveToday: "None — mission/TaskGraph APIs not exposed yet.",
  },
  {
    id: "dde-integration",
    title: "Integration",
    viewId: "dde.studio.integration",
    earliestStage: "S1",
    chapters: "Ch.10",
    status: "stub",
    summary:
      "Branch / merge-queue awareness. Blocked on DDE-013 service exposure + client transport.",
    liveToday: "None — empty until merge-queue API exists.",
  },
  {
    id: "dde-context",
    title: "Context",
    viewId: "dde.studio.context",
    earliestStage: "S1",
    chapters: "Ch.5",
    status: "stub",
    summary:
      "Coverage contract (seven categories) + index lag — not invented percentages (§5.2).",
    liveToday: "None — empty until context compile API / CLI exists.",
  },
  {
    id: "dde-routing",
    title: "Routing",
    viewId: "dde.studio.routing",
    earliestStage: "S1",
    chapters: "Ch.6",
    status: "stub",
    summary:
      "Gates 0–5 elimination vs gates 6–7 ranking. Override only among ranked survivors (§5.1).",
    liveToday: "None — empty until route evaluate API / CLI exists.",
  },
  {
    id: "dde-verification",
    title: "Verification",
    viewId: "dde.studio.verification",
    earliestStage: "S1",
    chapters: "Ch.9, Ch.11",
    status: "stub",
    summary:
      "Full verification chain + generator/verifier independence badge (§5.3).",
    liveToday: "None — empty until verification APIs exist.",
  },
  {
    id: "dde-approvals",
    title: "Approvals",
    viewId: "dde.studio.approvals",
    earliestStage: "S3",
    chapters: "Ch.13",
    status: "stub",
    summary:
      "Approval queue, StandingApproval, attention debt, Morning Review (§4.1). Needs Gateway + DDE-026.",
    liveToday: "None — DDE-026 not in Core yet; Morning Review shell is informational only.",
  },
  {
    id: "dde-chat",
    title: "Chat",
    viewId: "dde.studio.chat",
    earliestStage: "S3",
    chapters: "Ch.15, §3.3",
    status: "stub",
    summary:
      "Webview-first chat shell. No Chat Participant registration (Cursor defect §3.3). Blocked on Gateway sessions (S3).",
    liveToday: "None — session + message APIs not exposed.",
  },
  {
    id: "dde-donor",
    title: "Donors",
    viewId: "dde.studio.donor",
    earliestStage: "S5",
    chapters: "Ch.13.8",
    status: "stub",
    summary: "Donor Lab + reuse classification badges (OPEN_REUSE … REJECTED).",
    liveToday: "None — Donor Lab (DDE-046/047) not in Core yet.",
  },
  {
    id: "dde-knowledge",
    title: "Knowledge",
    viewId: "dde.studio.knowledge",
    earliestStage: "S4",
    chapters: "Ch.5.10",
    status: "stub",
    summary: "Knowledge graph (derived / asserted).",
    liveToday: "None — knowledge graph (DDE-033) not exposed.",
  },
  {
    id: "dde-evaluation",
    title: "Evaluate",
    viewId: "dde.studio.evaluation",
    earliestStage: "S4",
    chapters: "Ch.5.13, Ch.6.9",
    status: "stub",
    summary: "Eval corpus and learning promotion gates.",
    liveToday: "None — eval corpus / promotion APIs not exposed.",
  },
  {
    id: "dde-debug",
    title: "Debug",
    viewId: "dde.studio.debug",
    earliestStage: "S1",
    chapters: "Ch.16",
    status: "stub",
    summary: "Raw event / trace inspection.",
    liveToday: "None — event stream API not exposed yet.",
  },
];

export const MODULE_REGISTRY: readonly ModuleDescriptor[] = [
  {
    id: "dde-core-ui",
    title: "Connection",
    viewId: "dde.studio.connection",
    earliestStage: "S1",
    chapters: "Ch.15 / Ch.17.3",
    status: "exists",
    summary: "Shell, Mission Overview (primary home), connection settings, SecretStorage auth seam, live health polling.",
    liveToday: "GET /healthz and GET /readyz against configured Core URL; Overview shows live System zone.",
  },
  {
    id: "product-environment",
    title: "Preview",
    viewId: "dde.studio.preview",
    earliestStage: "S4",
    chapters: "Ch.11.6, playbook §5.0 P2",
    status: "exists",
    summary:
      "Prototype Gallery: live read-only stream of the workspace prototypes/ directory during authoring missions. ProductEnvironment ephemeral_preview link + TTL remains future scope.",
    liveToday:
      "Live gallery over workspace prototypes/: screens list with state suffixes, flows.json table when present, sandboxed srcdoc previews, file-watch auto-refresh, reduced-motion toggle. ProductEnvironment lifecycle (DDE-038) not exposed.",
  },
  ...SIDEBAR_STUB_MODULES,
  {
    id: "dde-workers",
    title: "Workers / Mission Control",
    earliestStage: "S1",
    chapters: "Ch.8",
    status: "stub",
    summary:
      "Hermes / Claude Code / DeepSeek are fleet Mission Control rooms (status, activity, routing, observability, control) for Appendix A roles — not thin catalog cards. Panels bind when Core certifies adapters and exposes Gateway/CLI.",
    liveToday:
      "Empty Mission Control chrome; missions/runs/events stay empty until Gateway/CLI (no fake stub rows).",
  },
];

export function moduleById(id: ModuleId): ModuleDescriptor | undefined {
  return MODULE_REGISTRY.find((m) => m.id === id);
}

export function modulesWithViewId(): readonly ModuleDescriptor[] {
  return MODULE_REGISTRY.filter((m) => m.viewId);
}
