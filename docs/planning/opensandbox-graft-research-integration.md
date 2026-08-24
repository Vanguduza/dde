# OpenSandbox/Graft Research Integration — containment and context-layer priors

**Date:** 2026-08-24. **Nature:** docs-only integration of completed web research into
planning; no engine code changes, no Project Truth rows, no new dependency. The adopted
patterns below are design inputs **and** acceptance-criteria seeds for the EDR-0011
decision memo, the Ch.5.2 structural retriever, and the DDE-059 charter; recorded in
`docs/planning/gap-closure-record.md §6.8`.

**Orientation anchors:** `AGENTS.md` (Ch.9.6 dependency admission; patterns-not-packages);
`docs/blueprint/REV_2_0.md` Ch.7.2 (T2 enforcement tiers; T2 rule 2 egress proxy),
Ch.7.4 (provisioning economics), Ch.5.2 retrievers, Ch.5.4 index lifecycle, Ch.5.13
eval corpus and promotion gates; `docs/truth/edr/EDR-0011-t2-network-egress-and-container-containment.md`,
`docs/truth/edr/EDR-0002-semantic-retriever-default-gating.md`.

---

## 1. Disambiguation — which products

Both referents are real, current (2026), and frequently conflated with same-named projects:

1. **OpenSandbox** ([github.com/opensandbox-group/OpenSandbox](https://github.com/opensandbox-group/OpenSandbox),
   redirects from `alibaba/OpenSandbox`) — Alibaba's open-source general-purpose sandbox
   platform for AI agents. This is the relevant containment candidate. Beware unrelated
   sandboxes sharing the name.
2. **Graft** ([github.com/NanoNets/Graft](https://github.com/NanoNets/Graft)) — NanoNets'
   context layer for coding agents ("up to 4× cheaper / 3× faster", no embeddings).
   Two **unrelated** repos share the name and must not be cited as this one:
   [flyingrobots/graft](https://github.com/flyingrobots/graft) (a read-policy "context
   governor") and [amaar-mc/graft](https://github.com/amaar-mc/graft) (tree-sitter +
   personalized PageRank via MCP). The clip's tagline matches only NanoNets/Graft.

### Repo cards

| | OpenSandbox | Graft |
|---|---|---|
| Licence | Apache-2.0 | MIT |
| Stars / forks | ~14.6K / ~1.3K | ~4.7K / ~400 |
| Created | 2025-12-17 (public launch 2026-03-03) | 2026-07-03 (**≈7 weeks old**) |
| Languages | Python (FastAPI control plane), Go (`execd`, egress, ingress) | TypeScript (npm `@nanonets/graft`) |
| Activity | Pushed daily; 158 open issues; OSEP process | Very active since launch; 54 open issues |
| Docs/blog | [open-sandbox.ai](https://open-sandbox.ai), [architecture doc](https://github.com/alibaba/OpenSandbox/blob/main/docs/architecture.md); coverage largely press-release derivatives ([MarkTechPost](https://www.marktechpost.com/2026/03/03/alibaba-releases-opensandbox-to-provide-software-developers-with-a-unified-secure-and-scalable-api-for-autonomous-ai-agent-execution/), [Tekai](https://tekai.dev/references/2026-04-03-alibaba-opensandbox)) | [README benchmarks](https://github.com/NanoNets/Graft#benchmark), [TELEMETRY.md](https://github.com/NanoNets/Graft/blob/main/TELEMETRY.md); no independent coverage yet |

## 2. Adopted patterns — design priors with acceptance-criteria language

### Pattern 1 — Egress sidecar as donor design for EDR-0011 Option B

OpenSandbox independently shipped, in production form, almost exactly what EDR-0011
Option B sketches: a dedicated egress sidecar enforcing FQDN/wildcard allow-deny rules,
a `dns` mode pinning resolution to a filtering resolver, a `dns+nft` mode adding
nftables enforcement of resolved IPs/CIDRs, a runtime policy API (`GET/PATCH /policy`),
platform-enforced always-allow/deny overlays, and a **credential vault that injects
outbound credentials at the sidecar so real secrets never enter sandbox environment
variables, commands, files, or logs** ([architecture doc §5.4](https://github.com/alibaba/OpenSandbox/blob/main/docs/architecture.md);
[Python SDK README](https://github.com/alibaba/OpenSandbox/blob/main/sdks/sandbox/python/README.md)).
Their K8s posture strips `NET_ADMIN` from the main sandbox container so only the
sidecar mutates network rules — the structural-not-advisory property Option B wants.

- **Maps to:** EDR-0011 Option B (per-run namespace/proxy admission): DDE-owned DNS
  resolver + allowlist proxy deriving entries from the ExecutionPlan capability set
  (Ch.7.2 rule 2 verbatim). Their credential-vault pattern is also the strongest known
  implementation of Ch.7.2 rule 1 (zero ambient credentials) for T2 workers — stronger
  than env-var filtering alone.
- **Known limitation they document themselves:** under gVisor the `dns+nft` nftables
  path does not work (no `nat` table in the user-space kernel); Kata-class runtimes are
  required ([secure-runtime guide](https://open-sandbox.ai/guides/secure-container)).
  Isolation-tier choice and egress-enforcement mechanism interact — the EDR-0011 memo
  must not treat them as independent axes.
- **Acceptance-criteria language for the EDR-0011 decision memo:** when EDR-0011
  acceptance is decided, the memo MUST evaluate this reference implementation of the
  hard parts — nftables IP enforcement, NET_ADMIN stripping, runtime policy mutation,
  secrets-injected-at-boundary — before specifying DDE's own proxy/resolver component;
  any divergence from it must be justified in the memo, not silent.

### Pattern 2 — Isolation tier as configuration, not architecture

The same platform runs runc (default), gVisor, Kata/QEMU, Kata-Firecracker, and
Kata-CLH behind one config key — Docker OCI runtime setting or Kubernetes `RuntimeClass`
— with published startup/memory overheads per tier (~10–50ms/~50MB gVisor; ~125ms/~5MB
Kata-FC) and server-start validation that the configured runtime exists.

- **Maps to:** EDR-0011 Option A ("container policies first"). It confirms Option A's
  mechanism table is industry-standard practice rather than an exotic position, and
  that `isolation_level enum(process, container, gvisor, microvm)` (Ch.7.3) is exactly
  the right shape: the tier is admission-checked config over a shared substrate, not a
  rewrite per tier.
- **Trigger:** same as Pattern 1 — the EDR-0011 decision memo evaluates both options
  against these reference designs together, since Patterns 1 and 2 interact.

### Pattern 3 — Deterministic symbol-graph retrieval as structural-retriever donors

Graft's query-time retrieval never calls a model: tree-sitter builds `wiring.json`
(every function/class/call edge) with scope-aware cross-file call/import resolution;
method calls bind through receiver types (constructor assignments, annotations), not
call-site names; ranking is in-edge coupling (hub/hotspot scoring à la PageRank on
in-degree); monorepos rank per sub-project scope and fuse so large packages cannot
drown small ones; every query stats the working tree against a build fingerprint
(~3ms when unchanged) and rebuilds structurally before answering, including uncommitted
edits ([README](https://github.com/NanoNets/Graft#how-the-graph-gets-built)). An
opt-in LSP tier adds compiler-grade edges when rust-analyzer/clangd/gopls/pyright/tsserver
are installed.

- **Maps to:** Ch.5.2 structural retriever (already tree-sitter-based) and the Ch.5.4
  staleness gate (their fingerprint-freshness check is a cheap prior for DDE's
  `index_lag_commits` machinery). Donor mechanisms worth evaluating: receiver-type
  method binding, per-scope monorepo ranking/fusion, in-degree-coupled ranking as a
  fusion weight, content-hash incremental rebuild.
- **Acceptance-criteria language:** the next mission touching the structural retriever,
  and the DDE-059 charter, MUST evaluate these candidate improvements **on the Ch.5.13
  eval corpus** against the certified lexical+structural baseline — adopt-or-drop on
  measured uplift, never wired by default without that measurement.

### Pattern 4 — Index-time LLM summarization as the embedding-free alternative path

Graft's second graph spends model budget at **index time**: each file summarized once,
summaries grouped into curated markdown concept nodes with typed links, everything
cached by content/body hash, rebuilt only when source bytes change. Query time stays
deterministic and free. No embeddings anywhere.

- **Maps to:** EDR-0002's open question ("whether the hashing-trick embedding should be
  replaced before or after Chapter 5.13's eval corpus exists") and the Ch.5.2 rule that
  semantic retrieval must demonstrate uplift against a lexical+structural baseline
  before default-on. Graft is existence proof that a third path exists between "fake
  embedding stand-in" and "real pgvector embeddings": cached LLM-written summaries
  consumed by deterministic retrieval.
- **Acceptance-criteria language:** any mission proposing to enable semantic retrieval
  by default (the EDR-0002/EDR-0003 promotion-gate path) MUST first A/B a Graft-class
  structural+cached-summary approach against the proposed semantic retriever on the
  Ch.5.13 eval corpus; semantic default-on requires beating **both** the lexical+
  structural baseline and this alternative, not merely the former.

### Pattern 5 — Push-vs-pull benchmark methodology for DDE-059

Graft's controlled sweep ran three variants of the same agent with the same tools —
cold baseline, **push** (context bundle injected up front), **pull** (retrieval tools,
pay-as-needed) — cache-aware cost accounting (reads ≈0.1×), plus a two-arm SWE-bench
Verified run graded by the official harness with no judge-model subjectivity
([README](https://github.com/NanoNets/Graft#benchmark)). Their headline findings:
push wins speed (−60% latency), pull won correctness (+5pts).

- **Maps to:** DDE-059 (adaptive context policy with promotion gates). The push/pull
  axis is precisely a context-policy decision DDE-059 should learn, and their protocol
  is directly reusable: same agent, same tools, only the retriever/policy differs,
  graded against the certified baseline on identical windows — mirroring Ch.5.13's
  no-regression gate and Ch.6.9's holdout-uplift style.
- **Acceptance-criteria language:** DDE-059's evaluation harness supports push vs pull
  variants of a candidate policy as first-class arms; adoption decisions cite measured
  cost/correctness deltas from those arms, and vendor-published numbers are treated as
  priors to replicate locally, never as evidence.

## 3. Explicitly not adopted (with reasons)

| Item | Reason |
|---|---|
| OpenSandbox as a dependency | No Kubernetes/container substrate in DDE today (that is precisely EDR-0011's open question); adopting it drags FastAPI/K8s/controller machinery into `adapters/**`. Revisit only after EDR-0011 acceptance authorizes a container backend. |
| Graft as a dependency | ≈7-week-old TypeScript repo fails the Ch.9.6 maintenance/maturity bar; telemetry default-on (configurable off); npm toolchain vs DDE Python. Patterns only. |
| OpenSandbox BatchSandbox pool pre-warming / pause-resume rootfs snapshots | Ch.7.4 warm-pool territory (DDE-029 lineage); meaningful only once a non-local execution substrate exists at all. Later, behind EDR-0011. |
| Graft MCP-server tool shape | DDE's capability contract and Ch.15 MCP surface already cover the equivalent shape; nothing new to admit. |

## 4. Source-quality caveats

- All Graft performance claims (−42% tokens, −46% tool calls, SWE-bench 54%→66%,
  "up to 4× cheaper / 3× faster") are **vendor-run, methodologically documented,
  unreplicated**: small instance counts, vendor-chosen repos, best-case headline
  numbers (PocketBase aggregate was −21% cost, not 4×). Methodology is the adoption;
  numbers are not evidence until replicated on DDE's own corpus.
- OpenSandbox coverage is press-release-heavy; no independent security audit, no
  independent benchmarks as of 2026-08-24. Production-oriented, not production-proven.
  Alibaba's strategic interest (on-ramp to its cloud) noted per Ch.13.8 donor caution.
- TikTok-level claims flattened nuance: Graft's "no telemetry" means telemetry exists
  and is configurable-off (daily batched ping + version check, `DO_NOT_TRACK=1` to
  disable, off in CI/source builds); "runs 100% local" holds only for the structural
  half — LLM node summaries call your configured provider unless pointed at a local
  model.
