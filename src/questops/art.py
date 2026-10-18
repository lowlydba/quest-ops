"""Shared drawing helpers: colour, bars, boxes, and the title banner.

The pixel-art title lives in title.py and the monsters in sprites.py.
"""

from __future__ import annotations

import os
import re
import sys

from .pixels import Backend

CLASS_COLORS = {"Fighter": 167, "Rogue": 71, "Wizard": 105}
XP_FILLED, XP_EMPTY = 71, 240

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("QUESTOPS_COLOR") == "0":
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("QUESTOPS_COLOR") == "1":
        return True
    # GitHub and GitLab log viewers render ANSI colour.
    return bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("GITLAB_CI") or sys.stdout.isatty())


def _c(text: str, code: int) -> str:
    return f"\x1b[38;5;{code}m{text}\x1b[0m" if text.strip() else text


def banner(color: bool | Backend = False) -> str:
    from .title import title

    return title(color)


BANNER = banner(False)


def paint(text: str, code: int, accents: dict | None = None) -> str:
    """Colour a line: a base colour, with optional per-glyph accents."""
    accents = accents or {}
    out = []
    for ln in text.split("\n"):
        if not ln.strip():
            out.append(ln)
            continue
        cur, buf, parts = None, "", []
        for ch in ln:
            col = accents.get(ch, code) if ch != " " else cur
            if col != cur and buf:
                parts.append(_c(buf, cur) if cur is not None else buf)
                buf = ""
            cur = col
            buf += ch
        parts.append(_c(buf, cur) if cur is not None else buf)
        out.append("".join(parts))
    return "\n".join(out)


def visible_len(s: str) -> int:
    return len(_ANSI.sub("", s))


def center_block(text: str, width: int = 62) -> str:
    """Centre a multi-line block as a unit (keeps its internal shape)."""
    lines = text.split("\n")
    pad = max((width - max(visible_len(ln) for ln in lines)) // 2, 0)
    return "\n".join(" " * pad + ln if ln.strip() else ln for ln in lines)


def hp_bar(cur: int, mx: int, width: int = 20) -> str:
    mx = max(mx, 1)
    cur = max(0, min(cur, mx))
    filled = round(width * cur / mx)
    return "[" + "#" * filled + "." * (width - filled) + f"] {cur:,}/{mx:,}"


def xp_bar(cur: int, mx: int, width: int = 20, color: bool = False) -> str:
    mx = max(mx, 1)
    cur = max(0, min(cur, mx))
    filled = round(width * cur / mx)
    if not color:
        return "[" + "=" * filled + "-" * (width - filled) + f"] {cur:,}/{mx:,}"
    full = _c("=" * filled, XP_FILLED) if filled else ""
    empty = _c("-" * (width - filled), XP_EMPTY) if filled < width else ""
    return f"[{full}{empty}] {cur:,}/{mx:,}"


def box(lines, width: int = 62) -> str:
    inner = width - 4
    out = ["+" + "-" * (width - 2) + "+"]
    for ln in lines:
        if visible_len(ln) > inner:
            ln = _ANSI.sub("", ln)[: inner - 1] + "\u2026"  # too long: drop colour rather than split an escape
        out.append("| " + ln + " " * (inner - visible_len(ln)) + " |")
    out.append("+" + "-" * (width - 2) + "+")
    return "\n".join(out)
