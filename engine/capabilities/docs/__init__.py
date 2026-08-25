"""Chapter 9 documentation/context-provider capability contract (DDE-050).

Serves version-pinned external documentation (Chapter 5.2's Documentation
retriever, Ch.5.5's freshness classes). Content is rank-9 external
evidence: it informs workers but can never satisfy a current-state
coverage requirement, and prompt-injection screening runs at read time so
injected instructions stay hypotheses (Ch.14.5 invariant 6).
"""

from engine.capabilities.docs.provider import (
    DocContent,
    DocSource,
    DocsProvider,
    InProcessDocsProvider,
)

__all__ = [
    "DocContent",
    "DocSource",
    "DocsProvider",
    "InProcessDocsProvider",
]
