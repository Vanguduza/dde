"""UUIDv7 identity generation as required by Chapter 3.4."""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """Return an RFC 9562 UUIDv7 generated in-process."""
    unix_ts_ms = int(time.time() * 1000)
    buf = bytearray(16)
    buf[0] = (unix_ts_ms >> 40) & 0xFF
    buf[1] = (unix_ts_ms >> 32) & 0xFF
    buf[2] = (unix_ts_ms >> 24) & 0xFF
    buf[3] = (unix_ts_ms >> 16) & 0xFF
    buf[4] = (unix_ts_ms >> 8) & 0xFF
    buf[5] = unix_ts_ms & 0xFF
    buf[6:] = os.urandom(10)
    buf[6] = (buf[6] & 0x0F) | 0x70
    buf[8] = (buf[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(buf))
