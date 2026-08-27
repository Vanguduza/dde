"""DDE-066 donor discovery grouping, allowlist, and fail-closed classifier."""

from __future__ import annotations

import pytest

from engine.capabilities.seed import SEED_CAPABILITIES
from engine.core.errors import BudgetExhaustedError, DdeError
from engine.donor.allowlist import allowlist_hash, assert_uri_admitted
from engine.donor.discovery import OrderedJournal, assemble_inventory, search_uri
from engine.donor.discovery_service import parse_search_body
from engine.donor.grouping import (
    ClassifierUnreachableError,
    DiscoveryHit,
    FeatureCategory,
    grouped_results_as_dict,
)
from engine.donor.quota import (
    DEFAULT_DONOR_SEARCH_MAX_QUERIES,
    assert_donor_search_quota,
    resolve_donor_search_ceiling,
)

FEATURES = (
    FeatureCategory(feature_id="feat-journals", title="Journals"),
    FeatureCategory(feature_id="feat-auth", title="Auth"),
)


def test_capability_donor_discovery_is_seeded() -> None:
    ids = {spec.capability_id for spec in SEED_CAPABILITIES}
    assert "capability.donor_discovery" in ids
    spec = next(
        item
        for item in SEED_CAPABILITIES
        if item.capability_id == "capability.donor_discovery"
    )
    assert spec.side_effect_class == "EXTERNAL_IDEMPOTENT"


def test_allowlist_admits_github_search_and_rejects_marketplace() -> None:
    assert_uri_admitted("https://api.github.com/search/repositories?q=ledger")
    with pytest.raises(DdeError) as captured:
        assert_uri_admitted("https://themeforest.net/item/foo")
    assert captured.value.error_code == "POLICY_DENIED"
    with pytest.raises(DdeError):
        assert_uri_admitted("https://example.com/search")
    assert len(allowlist_hash()) == 64


def test_journal_prepare_runs_before_fetch() -> None:
    journal = OrderedJournal()
    seen: list[str] = []

    def fetch(uri: str) -> str:
        seen.append(uri)
        journal.events.append(f"fetch:{uri}")
        return "{}"

    body = search_uri(
        uri="https://api.github.com/search/repositories?q=x",
        idempotency_key="k1",
        prepare=journal.prepare,
        fetch=fetch,
    )
    assert body == "{}"
    assert journal.events == [
        "prepare:https://api.github.com/search/repositories?q=x",
        "fetch:https://api.github.com/search/repositories?q=x",
    ]
    assert seen == ["https://api.github.com/search/repositories?q=x"]


def test_rejected_host_never_reaches_fetch() -> None:
    def fetch(_uri: str) -> str:
        raise AssertionError("fetch must not run")

    with pytest.raises(DdeError):
        search_uri(
            uri="https://themeforest.net/item/x",
            idempotency_key="k",
            prepare=lambda *_: None,
            fetch=fetch,
        )


def test_groups_by_feature_and_keeps_unmatched() -> None:
    hits = (
        DiscoveryHit(
            source_uri="https://ui.shadcn.com/r/button",
            summary="MIT licensed shadcn button",
            feature_hints=("feat-journals",),
        ),
        DiscoveryHit(
            source_uri="https://godly.site/shot/1",
            summary="gallery reference",
            feature_hints=("feat-unknown",),
        ),
        DiscoveryHit(
            source_uri="https://example.local/pin",
            summary="Apache-2.0 fixture pin",
            feature_hints=("feat-auth",),
            pin=True,
        ),
    )
    results = assemble_inventory(prd_id="prd-1", features=FEATURES, hits=hits)
    payload = grouped_results_as_dict(results)
    by_feature = {row["feature_id"]: row["hits"] for row in payload["groups"]}
    assert len(by_feature["feat-journals"]) == 1
    assert by_feature["feat-journals"][0]["source_class"] in {
        "OPEN_REUSE",
        "SOURCE_REFERENCE_ONLY",
        "CONDITIONAL_REUSE",
    }
    assert payload["unmatched"]
    assert payload["unmatched"][0]["source_uri"] == "https://godly.site/shot/1"
    pin = by_feature["feat-auth"][0]
    assert pin["adoption_state"] == "identified"


def test_unknown_is_not_usable_and_never_open_reuse() -> None:
    hits = (
        DiscoveryHit(
            source_uri="https://api.github.com/repos/acme/mystery",
            summary="",
            feature_hints=("feat-journals",),
        ),
    )
    results = assemble_inventory(prd_id="prd-1", features=FEATURES, hits=hits)
    hit = results.groups[0][1][0]
    assert hit.source_class != "OPEN_REUSE"
    assert hit.source_class != "UNKNOWN"
    assert hit.usable is False
    assert hit.taint_tags


def test_classifier_unreachable_fail_closes_empty() -> None:
    def boom(_text: str, _uri: str) -> None:
        raise RuntimeError("classifier down")

    results = assemble_inventory(
        prd_id="prd-1",
        features=FEATURES,
        hits=(
            DiscoveryHit(
                source_uri="https://ui.shadcn.com/r/x",
                summary="x",
                feature_hints=("feat-journals",),
            ),
        ),
        classifier=boom,  # type: ignore[arg-type]
    )
    assert results.groups == (
        ("feat-journals", ()),
        ("feat-auth", ()),
    )
    assert results.unmatched == ()
    assert results.refusals == ("classifier_unreachable",)
    err = ClassifierUnreachableError()
    assert err.error_code == "CONTEXT_INCOMPLETE"
    assert err.details is not None
    assert err.details["missing_artifact"] == "classifier"


def test_quota_refuses_over_ceiling_not_empty_inventory() -> None:
    assert resolve_donor_search_ceiling({}) == DEFAULT_DONOR_SEARCH_MAX_QUERIES
    with pytest.raises(BudgetExhaustedError) as captured:
        assert_donor_search_quota(ceiling=0, requested=1, already=0)
    assert captured.value.error_code == "BUDGET_EXCEEDED"


def test_parse_github_search_items_into_hits() -> None:
    body = (
        '{"items":[{"html_url":"https://github.com/acme/ledger",'
        '"description":"MIT journals","license":{"spdx_id":"MIT"}}]}'
    )
    hits = parse_search_body(
        "https://api.github.com/search/repositories?q=ledger",
        body,
        ("feat-journals",),
    )
    assert len(hits) == 1
    assert hits[0].source_uri == "https://github.com/acme/ledger"
    assert "MIT" in hits[0].summary
    assert hits[0].feature_hints == ("feat-journals",)
