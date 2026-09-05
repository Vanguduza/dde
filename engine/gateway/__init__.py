"""Gateway package boundary.

Transport objects are loaded lazily so importing authority metadata such as
``engine.gateway.scopes`` never boots FastAPI or Studio services. This keeps
domain services free of a package-initialization cycle.
"""

from __future__ import annotations

from typing import Any

__all__ = ["app", "create_app"]


def __getattr__(name: str) -> Any:
    if name == "app":
        from engine.gateway.app import app

        return app
    if name == "create_app":
        from engine.gateway.app import create_app

        return create_app
    raise AttributeError(name)
