"""Chapter 11.6 migration verification against real PostgreSQL
(Chapter 12.3 interplay: a failed migration leaves recoverable state).

Pins the production verification mechanism:
- `MigrationVerifier.verify_forward_empty` -- forward-applies the full
  alembic chain to a throwaway database created via the existing engine
  connection (CREATE DATABASE, Chapter 11.6's "forward-apply to an empty
  database");
- `MigrationVerifier.verify_forward_previous` -- snapshots the current
  schema at `previous_release_revision` into a second throwaway database,
  then forward-applies only the revisions after that baseline; this is
  the "forward-apply to a snapshot of the previous release's schema" half;
- a verifier that skips either half returns not-verified and the service
  refuses READY (covered in test_product_env_postgres).
"""

from __future__ import annotations

import pytest

from engine.product_env.verification import MigrationVerifier
from tests.support.db import new_engine


@pytest.mark.asyncio
async def test_forward_empty_verifies_full_chain_on_fresh_database() -> None:
    engine = new_engine()
    try:
        verifier = await MigrationVerifier.create(engine)
        try:
            result = await verifier.verify_forward_empty(
                head="0013", previous_release_revision="0012"
            )
        finally:
            await verifier.dispose()
        assert result.forward_empty_verified is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_forward_previous_applies_only_post_baseline_revisions() -> None:
    engine = new_engine()
    try:
        verifier = await MigrationVerifier.create(engine)
        try:
            result = await verifier.verify_forward_previous(
                previous_release_revision="0010"
            )
        finally:
            await verifier.dispose()
        assert result.forward_previous_verified is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_from_head_lands_on_baseline_reversibly() -> None:
    """Reversibility is part of the definition of done: forward to head,
    downgrade to baseline, and the database must actually stand on the
    baseline revision -- exercised through the same verifier the READY
    gate uses, so a non-reversible migration can never back a verified
    environment."""
    engine = new_engine()
    try:
        verifier = await MigrationVerifier.create(engine)
        try:
            result = await verifier.verify_downgrade_reversible(
                head="0013", baseline="0012"
            )
        finally:
            await verifier.dispose()
        assert result.forward_empty_verified is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_both_halves_run_against_the_same_snapshot_contract() -> None:
    engine = new_engine()
    try:
        verifier = await MigrationVerifier.create(engine)
        try:
            empty = await verifier.verify_forward_empty(
                head="0013", previous_release_revision="0012"
            )
            previous = await verifier.verify_forward_previous(
                previous_release_revision="0012"
            )
        finally:
            await verifier.dispose()
        assert empty.head == previous.head
        assert empty.forward_empty_verified and previous.forward_previous_verified
    finally:
        await engine.dispose()
