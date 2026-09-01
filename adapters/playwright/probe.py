"""Playwright page probe — vendor SDK lives only in this package.

Chapter 9.6 admission (this is an existing optional top-level dependency):
- Package: `playwright` (Apache-2.0)
- Maintenance: Microsoft-backed; named in blueprint Ch.11 and Appendix A
- Why stdlib is insufficient: Python has no browser runtime, CDP client,
  or page-automation API. urllib can fetch bytes; it cannot execute JS,
  observe a rendered DOM, or emulate reduced motion.

EDR-0008 already admitted Playwright for the Node studio visual job; this is
the Python control-plane counterpart for `capability.browser`. DDE-068 adds
`layout()` so density/silhouette/motion verdicts are based on the rendered
ProductEnvironment rather than source-code heuristics.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from engine.capabilities.browser import (
    BrowserCaptureResult,
    BrowserCaptureSpec,
    BrowserLayoutBlock,
    BrowserLayoutResult,
    BrowserLayoutSpec,
    BrowserProbeResult,
    BrowserProbeSpec,
)
from engine.core.errors import DdeError

_ALLOWED_SCHEMES = frozenset({"http", "https", "file"})
_DEFAULT_TIMEOUT_MS = 15_000
_MAX_LAYOUT_BLOCKS = 500


def _assert_allowlisted(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise DdeError(
            "POLICY_DENIED",
            "capability.browser refuses a URL scheme outside the allowlist",
            details={"url": url, "scheme": parsed.scheme or ""},
        )


def _is_timeout(exc: Exception) -> bool:
    return "timeout" in type(exc).__name__.lower() or "timeout" in str(exc).lower()


class PlaywrightBrowserProbe:
    """Real Playwright navigation, screenshot and rendered-layout capture.

    Import of `playwright` is deferred so the adapter can fail closed when
    the optional extra is not installed.
    """

    @staticmethod
    def _playwright() -> Any:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise DdeError(
                "POLICY_DENIED",
                "playwright is not installed; install the optional "
                "'browser' extra (Apache-2.0, Chapter 9.6)",
                details={"dependency": "playwright"},
            ) from exc
        return async_playwright

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        _assert_allowlisted(spec.url)
        async_playwright = self._playwright()
        started = time.monotonic()
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(
                        spec.url,
                        wait_until="domcontentloaded",
                        timeout=_DEFAULT_TIMEOUT_MS,
                    )
                    body = await page.inner_text("body")
                finally:
                    await browser.close()
        except DdeError:
            raise
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            timed_out = _is_timeout(exc)
            return BrowserProbeResult(
                exit_code=-1 if timed_out else 1,
                stdout="",
                stderr=str(exc),
                duration_ms=elapsed,
                timed_out=timed_out,
            )

        elapsed = int((time.monotonic() - started) * 1000)
        if spec.expect_text and spec.expect_text not in body:
            return BrowserProbeResult(
                exit_code=1,
                stdout=body,
                stderr=f"expected text not found: {spec.expect_text!r}",
                duration_ms=elapsed,
                timed_out=False,
            )
        return BrowserProbeResult(
            exit_code=0,
            stdout=body,
            stderr="",
            duration_ms=elapsed,
            timed_out=False,
        )

    async def screenshot(self, spec: BrowserCaptureSpec) -> BrowserCaptureResult:
        _assert_allowlisted(spec.url)
        async_playwright = self._playwright()
        started = time.monotonic()
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(
                        viewport={
                            "width": spec.viewport_width,
                            "height": spec.viewport_height,
                        }
                    )
                    await page.goto(
                        spec.url,
                        wait_until="domcontentloaded",
                        timeout=_DEFAULT_TIMEOUT_MS,
                    )
                    if spec.expect_text:
                        body = await page.inner_text("body")
                        if spec.expect_text not in body:
                            elapsed = int((time.monotonic() - started) * 1000)
                            return BrowserCaptureResult(
                                exit_code=1,
                                png_bytes=b"",
                                stderr=f"expected text not found: {spec.expect_text!r}",
                                duration_ms=elapsed,
                                timed_out=False,
                            )
                    png = await page.screenshot(type="png", full_page=False)
                finally:
                    await browser.close()
        except DdeError:
            raise
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            timed_out = _is_timeout(exc)
            return BrowserCaptureResult(
                exit_code=-1 if timed_out else 1,
                png_bytes=b"",
                stderr=str(exc),
                duration_ms=elapsed,
                timed_out=timed_out,
            )

        elapsed = int((time.monotonic() - started) * 1000)
        return BrowserCaptureResult(
            exit_code=0,
            png_bytes=png,
            stderr="",
            duration_ms=elapsed,
            timed_out=False,
        )

    async def layout(self, spec: BrowserLayoutSpec) -> BrowserLayoutResult:
        """Capture deterministic visible geometry after bounded settling.

        Geometry is clamped to the viewport and only meaningful structural,
        textual and interactive nodes are retained. The JavaScript result is
        immediately translated to DDE dataclasses so no Playwright objects
        escape the adapter boundary.
        """
        _assert_allowlisted(spec.url)
        async_playwright = self._playwright()
        started = time.monotonic()
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(
                        viewport={
                            "width": spec.viewport_width,
                            "height": spec.viewport_height,
                        },
                        reduced_motion="reduce" if spec.reduced_motion else "no-preference",
                    )
                    page = await context.new_page()
                    await page.goto(
                        spec.url,
                        wait_until="domcontentloaded",
                        timeout=_DEFAULT_TIMEOUT_MS,
                    )
                    if spec.settle_ms > 0:
                        await page.wait_for_timeout(min(spec.settle_ms, 2000))
                    body = await page.inner_text("body")
                    if spec.expect_text and spec.expect_text not in body:
                        elapsed = int((time.monotonic() - started) * 1000)
                        return BrowserLayoutResult(
                            exit_code=1,
                            blocks=(),
                            body_text=body,
                            active_motion_count=0,
                            spatial_motion_count=0,
                            duration_ms=elapsed,
                            timed_out=False,
                            stderr=f"expected text not found: {spec.expect_text!r}",
                        )
                    raw: Mapping[str, Any] = await page.evaluate(
                        """(limit) => {
                          const structural = new Set([
                            'HEADER','NAV','MAIN','SECTION','ARTICLE','ASIDE','FOOTER',
                            'FORM','TABLE','UL','OL','H1','H2','H3','H4','H5','H6',
                            'P','BUTTON','A','INPUT','SELECT','TEXTAREA'
                          ]);
                          const spatialProps = new Set([
                            'transform','translate','top','left','right','bottom',
                            'margin','margin-left','margin-right','margin-top','margin-bottom'
                          ]);
                          let activeMotion = 0;
                          let spatialMotion = 0;
                          const blocks = [];
                          const nodes = Array.from(document.body.querySelectorAll('*'));
                          for (const el of nodes) {
                            const style = getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden' ||
                                Number(style.opacity) === 0) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width < 2 || rect.height < 2) continue;
                            if (rect.bottom <= 0 || rect.right <= 0 ||
                                rect.top >= innerHeight || rect.left >= innerWidth) continue;

                            const td = style.transitionDuration.split(',').map(v => parseFloat(v) || 0);
                            const ad = style.animationDuration.split(',').map(v => parseFloat(v) || 0);
                            const hasTransition = td.some(v => v > 0);
                            const hasAnimation = ad.some(v => v > 0) && style.animationName !== 'none';
                            if (hasTransition || hasAnimation) activeMotion += 1;
                            const properties = style.transitionProperty.split(',').map(v => v.trim());
                            if ((hasTransition && properties.some(v => spatialProps.has(v) || v === 'all')) ||
                                hasAnimation) spatialMotion += 1;

                            const tag = el.tagName;
                            const role = el.getAttribute('role') || '';
                            const interactive = ['BUTTON','A','INPUT','SELECT','TEXTAREA'].includes(tag) ||
                              role === 'button' || role === 'link' || el.hasAttribute('tabindex');
                            const ownText = (el.innerText || '').replace(/\s+/g, ' ').trim();
                            const hasDdeAnchor = el.hasAttribute('data-dde-el');
                            if (!structural.has(tag) && !role && !interactive && !hasDdeAnchor) continue;
                            blocks.push({
                              tag: tag.toLowerCase(), role,
                              text: ownText.slice(0, 240),
                              x: Math.max(0, rect.left), y: Math.max(0, rect.top),
                              width: Math.min(innerWidth, rect.right) - Math.max(0, rect.left),
                              height: Math.min(innerHeight, rect.bottom) - Math.max(0, rect.top),
                              interactive
                            });
                            if (blocks.length >= limit) break;
                          }
                          return {blocks, activeMotion, spatialMotion};
                        }""",
                        _MAX_LAYOUT_BLOCKS,
                    )
                finally:
                    await browser.close()
        except DdeError:
            raise
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            timed_out = _is_timeout(exc)
            return BrowserLayoutResult(
                exit_code=-1 if timed_out else 1,
                blocks=(),
                body_text="",
                active_motion_count=0,
                spatial_motion_count=0,
                duration_ms=elapsed,
                timed_out=timed_out,
                stderr=str(exc),
            )

        raw_blocks = raw.get("blocks", []) if isinstance(raw, Mapping) else []
        blocks: list[BrowserLayoutBlock] = []
        if isinstance(raw_blocks, list):
            for item in raw_blocks:
                if not isinstance(item, Mapping):
                    continue
                blocks.append(
                    BrowserLayoutBlock(
                        tag=str(item.get("tag") or ""),
                        role=str(item.get("role") or ""),
                        text=str(item.get("text") or ""),
                        x=float(item.get("x") or 0.0),
                        y=float(item.get("y") or 0.0),
                        width=max(float(item.get("width") or 0.0), 0.0),
                        height=max(float(item.get("height") or 0.0), 0.0),
                        interactive=bool(item.get("interactive", False)),
                    )
                )
        elapsed = int((time.monotonic() - started) * 1000)
        return BrowserLayoutResult(
            exit_code=0,
            blocks=tuple(blocks),
            body_text=body,
            active_motion_count=int(raw.get("activeMotion", 0)),
            spatial_motion_count=int(raw.get("spatialMotion", 0)),
            duration_ms=elapsed,
            timed_out=False,
        )
