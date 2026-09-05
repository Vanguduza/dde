"""Frontend Studio public package without eager application bootstrapping.

Domain submodules (tables, mutation engine, Fabric bindings) must be importable
without importing the Gateway-facing FrontendStudioService and its full graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.studio.compiler import compile_generation_prompt
from engine.studio.errors import CompileRefusedError
from engine.studio.models import (
    CompileRequest,
    FeatureSurface,
    GenerationPrompt,
    RequirementInput,
)

if TYPE_CHECKING:
    from engine.studio.frontend import FrontendStudioService

__all__ = [
    "CompileRefusedError",
    "CompileRequest",
    "FeatureSurface",
    "FrontendStudioService",
    "GenerationPrompt",
    "RequirementInput",
    "compile_generation_prompt",
]


def __getattr__(name: str) -> Any:
    if name == "FrontendStudioService":
        from engine.studio.frontend import FrontendStudioService

        return FrontendStudioService
    raise AttributeError(name)
