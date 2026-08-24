"""Playwright page probe — vendor SDK lives only in this package.

Chapter 9.6 admission (this is a new optional top-level dependency):
- Package: `playwright` (Apache-2.0)
- Maintenance: Microsoft-backed; named in blueprint Ch.11 and Appendix A
- Why stdlib is insufficient: Python has no browser runtime, CDP client,
  or page-automation API. urllib can fetch bytes; it cannot execute JS
  or observe a rendered DOM.

EDR-0008 already admitted Playwright for the Node studio visual job;
this is the Python control-plane counterpart for `capability.browser`.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from engine.capabilities.browser import BrowserProbeResult, BrowserProbeSpec
from engine.core.errors import DdeError

_ALLOWED_SCHEMES = frozenset({"http", "https", "file"})
_DEFAULT_TIMEOUT_MS = 15_000


def _assert_allowlisted(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise DdeError(
            "POLICY_DENIED",
            "capability.browser refuses a URL scheme outside the allowlist",
            details={"url": url, "scheme": parsed.scheme or ""},
        )


class PlaywrightBrowserProbe:
    """Real Playwright navigation. Import of `playwright` is deferred so
    the adapter can fail closed when the optional extra is not installed."""

    async def probe(self, spec: BrowserProbeSpec) -> BrowserProbeResult:
        _assert_allowlisted(spec.url)
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise DdeError(
                "POLICY_DENIED",
                "playwright is not installed; install the optional "
                "'browser' extra (Apache-2.0, Chapter 9.6)",
                details={"dependency": "playwright"},
            ) from exc

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
            timed_out = "timeout" in type(exc).__name__.lower() or "Timeout" in str(exc)
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
