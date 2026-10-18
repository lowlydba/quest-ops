"""Preview sprites and scenes the way GitHub's Actions log viewer draws them, for local iteration.

usage: python scripts/preview_gh.py [--out DIR] [--scale N] [monster ...]

Uses the `solid` backend (what CI picks) and paints each cell as a tall block: GitHub fills the
background over the whole ~20px line but draws glyphs in a shorter box, so a cell is one colour,
roughly 7px wide by 20px tall. Writes preview.html, and preview.png when Edge or Chrome is found.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from questops import avatar, scenes  # noqa: E402
from questops.engine import MONSTERS  # noqa: E402
from questops.pixels import SOLID  # noqa: E402
from questops.sprites import ITEM_SPRITES, SPRITES, item_icon, tier_ramps  # noqa: E402
from questops.sprites import render as render_pixels  # noqa: E402
from questops.state import CLASSES  # noqa: E402

CELL_W, CELL_H = 7.2, 20  # GitHub log font: 12px monospace on a 20px line
SGR = re.compile(r"\x1b\[([0-9;]*)m")


def xterm(n: int) -> str:
    if n >= 232:
        v = 8 + 10 * (n - 232)
        return f"rgb({v},{v},{v})"
    n -= 16
    lv = [0, 95, 135, 175, 215, 255]
    return f"rgb({lv[n // 36]},{lv[(n // 6) % 6]},{lv[n % 6]})"


def ansi_to_html(text: str) -> str:
    out, bg = [], None
    for line in text.split("\n"):
        cells, pos = [], 0
        for m in SGR.finditer(line):
            cells += [(bg, ch) for ch in line[pos:m.start()]]
            pos = m.end()
            bg = None
            for part in re.findall(r"48;5;(\d+)", m.group(1)):
                bg = int(part)
        cells += [(bg, ch) for ch in line[pos:]]
        bg = None
        out.append("".join(
            f'<i style="background:{xterm(b)}"></i>' if b is not None else "<i></i>" for b, _ in cells))
    return "\n".join(f"<div>{row}</div>" for row in out)


def pane(title: str, body: str) -> str:
    return f'<figure><figcaption>{html.escape(title)}</figcaption>{ansi_to_html(body)}</figure>'


def build_avatars(names: list[str], scale: float) -> str:
    panes = [pane(f"{n} / {cls}", render_pixels(*avatar.portrait(n, cls), SOLID, dither=0.3)) for n in names for cls in CLASSES]
    return build_page(panes, scale)


def build_items(scale: float) -> str:
    panes = [pane(cat, "\n".join(item_icon(cat, SOLID))) for cat in ITEM_SPRITES]
    return build_page(panes, scale)


def build(names: list[str], scale: float, matrix: bool = False) -> str:
    panes = []
    for name in names:
        key = name
        if matrix:  # every scene, tier 0
            for scene in scenes.SCENES:
                art = scenes.staged(scenes.suit(scene, key), SPRITES[key], tier_ramps(key, 0), SOLID, 0)
                panes.append(pane(f"{key} / {scene}", art))
            continue
        scene = scenes.pick_scene(key)
        for tier in (0, 1, 2):
            art = scenes.staged(scenes.suit(scene, key), SPRITES[key], tier_ramps(key, tier), SOLID, tier)
            panes.append(pane(f"{key} / {scene} / tier {tier}", art))
    return build_page(panes, scale)


def build_page(panes: list[str], scale: float) -> str:
    css = (f"body{{background:#0d1117;color:#c9d1d9;font:12px monospace;margin:12px}}"
           f"figure{{display:inline-block;margin:0 16px 16px 0;vertical-align:top}}"
           f"figcaption{{margin-bottom:4px}}div{{height:{CELL_H * scale}px;white-space:nowrap;display:flex}}"
           f"i{{display:inline-block;width:{CELL_W * scale}px;height:{CELL_H * scale}px}}")
    return f"<!doctype html><meta charset=utf-8><style>{css}</style>{''.join(panes)}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / ".preview"))
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--matrix", action="store_true", help="every monster in every scene (tier 0)")
    ap.add_argument("--items", action="store_true", help="every item icon")
    ap.add_argument("--avatars", action="store_true", help="hero avatars for the given names (default: a sample)")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    names = args.names or [m[1] for m in MONSTERS]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    page = out / "preview.html"
    if args.avatars:
        heroes = args.names or ["linus", "ada", "grace", "octocat", "hubot", "mona"]
        html_page = build_avatars(heroes, args.scale)
    else:
        html_page = build_items(args.scale) if args.items else build(names, args.scale, args.matrix)
    page.write_text(html_page, encoding="utf-8")
    print(page)
    browser = next((p for p in (
        shutil.which("msedge"), shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe") if p and Path(p).exists()), None)
    if browser:
        png = out / "preview.png"
        subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=1900,1400",
                        f"--screenshot={png}", page.as_uri()], check=False, capture_output=True)
        print(png)


if __name__ == "__main__":
    main()
