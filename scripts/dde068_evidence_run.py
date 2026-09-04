"""DDE-068 end-to-end evidence run — real render, real critic, real verdict.

Drives the complete visual-verification chain against real candidates with
no stand-ins anywhere in the path:

    real HTML candidate
      -> real Playwright render + screenshot (`capability.browser`)
      -> deterministic layer: silhouette fingerprint + density evidence
      -> real multimodal critique (`capability.visual_critique`)
      -> schema-validated structured verdict
      -> deterministic pass/fail policy (playbook section 8)
      -> bounded-revision decision
      -> promotion decision

Run against both candidates under `docs/evidence/dde-068/candidates/`: one
deliberately carrying the playbook's named generic tells and placeholder
filler, one a real DDE-shaped operator surface. The point is to show the
chain rejecting the first and admitting the second on real pixels, not to
show that the modules import.

**This spends real model quota.** Each critique is one live invocation
against the operator's own rate-limited pool (see EDR-0017's resource
governance note), so this is an explicitly budgeted operator step, never
something a verification loop performs casually. Invoke deliberately:

    uv run python -m scripts.dde068_evidence_run

Writes screenshots and a JSON evidence record under
`docs/evidence/dde-068/` for the chapter-gate record.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from adapters.playwright.probe import PlaywrightBrowserProbe
from adapters.visual_critic.adapter import LocalMultimodalVisualCritic
from engine.capabilities.browser import BrowserCaptureSpec
from engine.capabilities.visual_critic import VisualCritiqueRequest
from engine.core.errors import DdeError
from engine.verification.silhouette import (
    compute_density_evidence,
    compute_fingerprint,
    evaluate_silhouette,
)
from engine.verification.visual_critique import (
    decide_revision_action,
    evaluate_verdict,
    load_rubric,
    parse_verdict,
)

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "dde-068"
CANDIDATES = (
    ("good-candidate", "expected to pass"),
    ("poor-candidate", "expected to be rejected"),
)
VIEWPORT = (1280, 720)


def _prior_critique(name: str, cycle: int) -> dict[str, object] | None:
    """Load the previous cycle's verdict for a bounded re-evaluation, so the
    critic judges whether the blocking defects were actually repaired
    rather than assuming they were."""
    if cycle <= 0:
        return None
    source = EVIDENCE_DIR / "evidence-run.json"
    if not source.is_file():
        raise DdeError(
            "POLICY_DENIED",
            "a revision cycle needs the prior cycle's recorded critique",
            details={"expected": str(source)},
        )
    previous = json.loads(source.read_text(encoding="utf-8"))
    for item in previous.get("candidates", []):
        if item.get("candidate") == name:
            return {
                "verdict": item["verdict"],
                "failing_dimensions": item["failing_dimensions"],
                "blocking_defects": item["blocking_defects"],
                "repair_instructions": item["repair_instructions"],
            }
    raise DdeError(
        "POLICY_DENIED",
        "no prior critique recorded for this candidate",
        details={"candidate": name},
    )


async def _run_candidate(
    name: str, expectation: str, *, cycle: int = 0
) -> dict[str, object]:
    candidate_path = EVIDENCE_DIR / "candidates" / f"{name}.html"
    url = candidate_path.as_uri()
    print(f"\n=== {name} ({expectation}) ===")
    print(f"rendering {url}")

    capture = await PlaywrightBrowserProbe().screenshot(
        BrowserCaptureSpec(
            url=url, viewport_width=VIEWPORT[0], viewport_height=VIEWPORT[1]
        )
    )
    if capture.exit_code != 0:
        raise DdeError(
            "POLICY_DENIED",
            "evidence run could not render the candidate",
            details={"candidate": name, "stderr": capture.stderr[:400]},
        )
    shot_path = EVIDENCE_DIR / f"{name}.png"
    shot_path.write_bytes(capture.png_bytes)
    print(f"screenshot: {shot_path.name} ({len(capture.png_bytes)} bytes)")

    silhouette = evaluate_silhouette(capture.png_bytes)
    density = compute_density_evidence(compute_fingerprint(capture.png_bytes))
    print(
        f"deterministic: silhouette blocked={silhouette.blocked} "
        f"({silhouette.detail}); occupancy={density.occupancy_ratio:.2f}"
    )

    rubric_version = str(load_rubric()["rubric_version"])
    deterministic_evidence = {
        "silhouette": {
            "fingerprint_hash": silhouette.fingerprint.fingerprint_hash,
            "matched_template": silhouette.matched_template,
            "similarity": silhouette.similarity,
            "blocked": silhouette.blocked,
        },
        "density": asdict(density),
    }

    print("invoking the live visual critic (real model quota) ...")
    critique = await LocalMultimodalVisualCritic().critique(
        VisualCritiqueRequest(
            screenshot_png=capture.png_bytes,
            rubric_version=rubric_version,
            candidate_ref=f"evidence:{name}",
            viewport_width=VIEWPORT[0],
            viewport_height=VIEWPORT[1],
            deterministic_evidence=deterministic_evidence,
            prior_critique=_prior_critique(name, cycle),
        )
    )
    if critique.exit_code != 0 or critique.timed_out:
        raise DdeError(
            "VALIDATION_FAILED",
            "live critic did not return a verdict",
            details={"candidate": name, "stderr": critique.stderr[:400]},
        )

    verdict = parse_verdict(
        critique.verdict_json,
        rubric_version=rubric_version,
        model=critique.model,
        cost_usd=critique.cost_usd,
    )
    assessment = evaluate_verdict(verdict)
    decision = decide_revision_action(assessment=assessment, completed_cycles=cycle)

    print(f"critic verdict: {verdict.verdict} (confidence {verdict.confidence})")
    print(f"scores: {verdict.dimension_scores}")
    print(f"policy: passed={assessment.passed} -- {assessment.detail}")
    print(f"bounded revision: {decision.action} -- {decision.detail}")
    print(f"promotion: {'ELIGIBLE' if assessment.passed else 'DENIED'}")
    print(f"measured cost: {critique.cost_usd} model: {critique.model}")

    return {
        "candidate": name,
        "expectation": expectation,
        "cycle": cycle,
        "url": url,
        "screenshot": shot_path.name,
        "screenshot_bytes": len(capture.png_bytes),
        "deterministic": deterministic_evidence,
        "rubric_version": rubric_version,
        "critic_model": critique.model,
        "critic_cost_usd": critique.cost_usd,
        "critic_duration_ms": critique.duration_ms,
        "verdict": verdict.verdict,
        "confidence": verdict.confidence,
        "dimension_scores": verdict.dimension_scores,
        "blocking_defects": [asdict(item) for item in verdict.blocking_defects],
        "non_blocking_defects": [asdict(item) for item in verdict.non_blocking_defects],
        "repair_instructions": list(verdict.repair_instructions),
        "summary": verdict.summary,
        "policy_passed": assessment.passed,
        "failing_dimensions": list(assessment.failing_dimensions),
        "policy_detail": assessment.detail,
        "revision_action": decision.action,
        "promotion": "ELIGIBLE" if assessment.passed else "DENIED",
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="run just this candidate")
    parser.add_argument(
        "--cycle",
        type=int,
        default=0,
        help="revision cycle index; >0 feeds the prior critique back in",
    )
    args = parser.parse_args()

    selected = [
        (name, note)
        for name, note in CANDIDATES
        if args.only is None or name == args.only
    ]
    if not selected:
        raise SystemExit(f"unknown candidate: {args.only}")
    records = [
        await _run_candidate(name, note, cycle=args.cycle) for name, note in selected
    ]
    record = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "chain": [
            "render",
            "screenshot",
            "silhouette",
            "density_evidence",
            "multimodal_critique",
            "structured_verdict",
            "deterministic_policy",
            "bounded_revision_decision",
            "promotion_decision",
        ],
        "candidates": records,
        "total_cost_usd": sum(
            float(item["critic_cost_usd"] or 0.0) for item in records
        ),
    }
    suffix = f"-cycle{args.cycle}" if args.cycle else ""
    scope = f"-{args.only}" if args.only else ""
    out = EVIDENCE_DIR / f"evidence-run{scope}{suffix}.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nevidence written: {out}")
    print(f"total measured cost: ${record['total_cost_usd']:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
