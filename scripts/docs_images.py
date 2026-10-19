"""Render the README's images from the game itself, so the product page never drifts from the game.

usage: python scripts/docs_images.py   (writes docs/img/)

The encounter image is a real quest transcript with colour on, drawn the way a terminal draws it:
each half-block cell becomes two square pixels, and text keeps its colours.
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from questops import svg  # noqa: E402
from questops.engine import ACHIEVEMENTS, MONSTERS, Result  # noqa: E402
from questops.pages import merchant_svg, sprite_svg  # noqa: E402
from questops.scenes import pick_scene  # noqa: E402
from questops.state import Character, Store, slug  # noqa: E402

OUT = ROOT / "docs" / "img"
HERO = "linus"
CONTEXT = "your-org/app / ci"
FG, BG = "#c9d1d9", "#0d1117"
CELL_W, CELL_H, FONT = 9, 18, 14.5
ROW_FILL = 1.0  # share of a text row that backgrounds cover
GLYPH_FILL = 1.0  # share of a text row that block glyphs cover; GitHub's log draws them in a shorter glyph box
SGR = re.compile(r"\x1b\[([0-9;]*)m")


def seasoned_hero(store: Store) -> Character:
    ch = store.load(HERO)
    ch.level, ch.xp = 4, 13000
    ch.wins, ch.losses, ch.encounters, ch.streak, ch.best_streak = 41, 6, 47, 7, 12
    ch.kens = 12345  # shows off a toh
    ch.kills = {"Lint Goblin": 19, "Cache Slime": 14, "Wraith of the Flaky Test": 5}
    ch.main_hand, ch.accessory = "Staff of Regex [rare]", "Lockfile Locket [rare]"
    ch.inventory = ["Intern's Staff [common]", "Lucky Rubber Duck [common]"]
    # A veteran has already earned what their record says, so a fresh win does not unlock old news (like Lint Roller mid-wraith).
    blank = Result("combat", "", True)
    ch.achievements = [label for label, test in ACHIEVEMENTS.values() if test(ch, blank)]
    return ch


def encounter_ansi() -> tuple[str, Character]:
    """Play seeded quests with a seasoned hero until one is a won fight with spells; return its coloured transcript."""
    for n in range(500):
        if pick_scene(f"docs-{n}") == "stairs":  # its stained glass is busy behind the foe; pick a calmer room
            continue
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.save(seasoned_hero(store))
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "QUESTOPS_COLOR": "1", "QUESTOPS_PIXELS": "solid", "PYTHONUTF8": "1"}
            for k in ("NO_COLOR", "GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_SHA", "GITHUB_RUN_ID"):
                env.pop(k, None)
            cmd = [sys.executable, "-m", "questops", "quest", "--outcome", "success", "--player", HERO,
                   "--seed", f"docs-{n}", "--kind", "combat", "--context", CONTEXT, "--data-dir", tmp]
            out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, check=True).stdout
            if "VICTORY" in out and "Slew" in out and "casts" in out and "Weary" in out:
                return out, Store(Path(tmp)).load(HERO)
    raise SystemExit("no winning fight in 500 seeds")


def cells(line: str) -> list[tuple[str, str | None, str | None, bool]]:
    """Decode one ANSI line into (glyph, fg, bg, bold) cells."""
    out, fg, bg, bold, pos = [], None, None, False, 0
    for m in list(SGR.finditer(line)) + [None]:
        end = m.start() if m else len(line)
        out += [(ch, fg, bg, bold) for ch in line[pos:end]]
        if not m:
            break
        pos = m.end()
        params = [int(p) for p in m.group(1).split(";") if p] or [0]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                fg, bg, bold = None, None, False
            elif p == 1:
                bold = True
            elif p in (38, 48) and i + 2 < len(params) and params[i + 1] == 5:
                colour = svg.xterm_hex(params[i + 2])
                fg, bg = (colour, bg) if p == 38 else (fg, colour)
                i += 2
            i += 1
    return out


def terminal_svg(ansi: str) -> str:
    lines = ansi.rstrip("\n").split("\n")
    rows = [cells(ln) for ln in lines]
    pad, bar = 20, 30
    cols = max(len(r) for r in rows)
    w, h = cols * CELL_W + 2 * pad, len(rows) * CELL_H + 2 * pad + bar
    parts = [
        f'<rect width="{w}" height="{h}" rx="10" fill="{BG}" stroke="#30363d"/>',
        *(f'<circle cx="{20 + i * 18}" cy="15" r="5.5" fill="{c}"/>' for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840"))),
    ]
    for y, row in enumerate(rows):
        top = pad + bar + y * CELL_H
        x = 0
        fill = CELL_H * ROW_FILL
        inset = (CELL_H - fill) / 2
        while x < len(row):
            ch, fg, bg, bold = row[x]
            left = pad + x * CELL_W
            if bg:
                parts.append(f'<rect x="{left}" y="{top + inset:.1f}" width="{CELL_W}" height="{fill:.1f}" fill="{bg}"/>')
            if ch in "\u2580\u2584\u2588":
                g = CELL_H * GLYPH_FILL
                g0 = top + (CELL_H - g) / 2
                y0, hh = (g0, g / 2) if ch == "\u2580" else (g0 + g / 2, g / 2) if ch == "\u2584" else (g0, g)
                parts.append(f'<rect x="{left}" y="{y0:.1f}" width="{CELL_W}" height="{hh:.1f}" fill="{fg or FG}"/>')
                x += 1
                continue
            if ch == " ":
                x += 1
                continue
            end = x
            while end < len(row) and row[end][0] not in "\u2580\u2584\u2588" and row[end][1:] == (fg, bg, bold):
                end += 1
            text = "".join(c[0] for c in row[x:end]).rstrip()
            if bg and end - x > 1:
                parts.append(f'<rect x="{left + CELL_W}" y="{top + inset:.1f}" width="{(end - x - 1) * CELL_W}" height="{fill:.1f}" fill="{bg}"/>')
            weight = ' font-weight="bold"' if bold else ""
            parts.append(
                f'<text x="{left}" y="{top + CELL_H / 2 + FONT * 0.35:.1f}" textLength="{len(text) * CELL_W}" lengthAdjust="spacingAndGlyphs" '
                f'fill="{fg or FG}"{weight} xml:space="preserve">{html.escape(text)}</text>'
            )
            x = end
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="{FONT}" role="img" '
        f'aria-label="A QuestOps encounter in a CI log">{"".join(parts)}</svg>\n'
    )


def write(rel: str, content: str) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    write("banner.svg", svg.title_svg())
    ansi, hero = encounter_ansi()
    write("encounter.svg", terminal_svg(ansi))
    write("card.svg", svg.card(hero))
    for name, key, *_ in MONSTERS:
        write(f"monsters/{slug(name)}.svg", sprite_svg("monster", key))
    write("monsters/traveling-merchant.svg", merchant_svg("github-actions[bot]"))


if __name__ == "__main__":
    main()
