"""Playwright browser capability (DDE-043)."""

from adapters.playwright.adapter import PlaywrightWorkerAdapter
from adapters.playwright.probe import PlaywrightBrowserProbe

__all__ = ["PlaywrightWorkerAdapter", "PlaywrightBrowserProbe"]
