"""Optional preview catalog emitted from the product's own token sheet.

T1.4: gallery HTML comes from the compiled art-direction + pinned tokens,
never from a third-party DESIGN.md pack.
"""

from __future__ import annotations

from typing import Any

from engine.studio.tokens_pin import TokenSheet


def render_preview_catalog(
    art_direction: dict[str, Any],
    sheet: TokenSheet,
) -> str:
    roles = art_direction["palette_roles"]
    pairing = art_direction["type_pairing"]
    dials = art_direction["dials"]
    role_rows = "\n".join(
        f"<tr><th>{_escape(name)}</th><td>{_escape(str(alias))}</td></tr>"
        for name, alias in sorted(roles.items())
    )
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>Preview {_escape(str(art_direction['record_id']))}</title>"
        "</head><body>"
        f"<p>record {_escape(str(art_direction['record_id']))}</p>"
        f"<p>tokens v{sheet.version}</p>"
        f"<p>display {_escape(str(pairing['display']))} / "
        f"body {_escape(str(pairing['body']))}</p>"
        f"<p>DESIGN_VARIANCE {dials['DESIGN_VARIANCE']} "
        f"MOTION_INTENSITY {dials['MOTION_INTENSITY']} "
        f"VISUAL_DENSITY {dials['VISUAL_DENSITY']}</p>"
        f"<table>{role_rows}</table>"
        "</body></html>\n"
    )


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
