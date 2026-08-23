"""Chapter 11.6 ProductEnvironment lifecycle (DDE-038).

Owner of `product_environments` and `seed_datasets` per Chapter 3.8
(owner module `verification`; this subpackage is the verification domain's
product-environment unit). Public surface:

- :mod:`engine.product_env.states` — the explicit transition table;
- :class:`engine.product_env.service.ProductEnvironmentService` — the
  lifecycle mutations, TTL sweep and seed binding;
- :class:`engine.product_env.seeds.SeedRegistry` — versioned,
  content-hashed seed dataset registration;
- :class:`engine.product_env.verification.MigrationVerifier` — the two
  mandatory forward-applies (empty database + previous release snapshot).
"""

from __future__ import annotations

from engine.product_env.states import (
    PRODUCT_ENV_TRANSITIONS,
    TERMINAL_PRODUCT_ENV_STATES,
)

__all__ = [
    "PRODUCT_ENV_TRANSITIONS",
    "TERMINAL_PRODUCT_ENV_STATES",
]
