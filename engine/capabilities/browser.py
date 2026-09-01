"""Chapter 9 browser capability contract — no vendor SDK.

Playwright (and any other browser backend) lives in `adapters/playwright/**`.
This module is the typed seam `engine.verification` and worker adapters call
so `engine.core` never imports a browser runtime (AGENTS.md).

DDE-068 extends the existing screenshot seam with a deterministic rendered
layout snapshot. The snapshot contains geometry and computed motion facts,
not browser-vendor objects, so silhouette/density/reduced-motion gates remain
provider-neutral and reproducible inside `engine.verification`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BrowserProbeSpec:
    """One deterministic page probe.

    `url` is the page to open. `expect_text`, when set, must appear in the
    rendered `body.inner_text` for the probe to pass. Empty expect_text
    means "navigation succeeded."
    """

    url: str
    expect_text: str | None = None


@dataclass(frozen=True)
class BrowserProbeResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


@dataclass(frozen=True)
class BrowserCaptureSpec:
    """DDE-044 screenshot capture for `visual_diff`."""

    url: str
    viewport_width: int
    viewport_height: int
    expect_text: str | None = None


@dataclass(frozen=True)
class BrowserCaptureResult:
    exit_code: int
    png_bytes: bytes
    stderr: str
    duration_ms: int
    timed_out: bool


@dataclass(frozen=True)
class BrowserLayoutSpec:
    """DDE-068 rendered-layout evidence request.

    `reduced_motion=True` asks the browser context to emulate the user's
    reduced-motion preference. `settle_ms` is bounded and exists only so
    arrival animations have reached their intended end-state before geometry
    is sampled; it is not an arbitrary sleep inside verification logic.
    """

    url: str
    viewport_width: int
    viewport_height: int
    expect_text: str | None = None
    reduced_motion: bool = False
    settle_ms: int = 350


@dataclass(frozen=True)
class BrowserLayoutBlock:
    tag: str
    role: str
    text: str
    x: float
    y: float
    width: float
    height: float
    interactive: bool


@dataclass(frozen=True)
class BrowserLayoutResult:
    exit_code: int
    blocks: tuple[BrowserLayoutBlock, ...]
    body_text: str
    active_motion_count: int
    spatial_motion_count: int
    duration_ms: int
    timed_out: bool
    stderr: str = ""


class BrowserCapability(Protocol):
    """T1-brokered browser execution. Callers must hold an active
    `capability.browser` lease before invoking these methods — this protocol
    does not grant authority."""

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult: ...
    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult: ...
    async def layout(self, spec: BrowserLayoutSpec) -> BrowserLayoutResult: ...
