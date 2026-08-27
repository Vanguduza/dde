"""Frontend Studio compiler (DDE-065). Offline generation-prompt assembly."""

from engine.studio.compiler import compile_generation_prompt
from engine.studio.errors import CompileRefusedError
from engine.studio.frontend import FrontendStudioService
from engine.studio.models import (
    CompileRequest,
    FeatureSurface,
    GenerationPrompt,
    RequirementInput,
)

__all__ = [
    "CompileRefusedError",
    "CompileRequest",
    "FeatureSurface",
    "FrontendStudioService",
    "GenerationPrompt",
    "RequirementInput",
    "compile_generation_prompt",
]
