"""Termux / POSIX device edge client (DDE-054)."""

from __future__ import annotations

__all__ = ["OfflineQueue", "DeviceClient"]

from interfaces.termux.device_client import DeviceClient
from interfaces.termux.offline_queue import OfflineQueue
