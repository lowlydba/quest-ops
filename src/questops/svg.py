"""Character cards as SVG, plus shields.io endpoint badges.

Cards are plain static files regenerated on every quest. Commit them to the data
branch and embed them anywhere with a raw URL, the same way you would a shields.io
image: the picture is always as fresh as the last quest.
"""

from __future__ import annotations

import html
import json

from . import avatar as avatar_mod
from . import items
from .art import CLASS_COLORS
from .sprites import ITEM_RAMPS, ITEM_SPRITES, _mirror, _pixel
from .state import Character, xp_for_level

RARITY_HEX = {"common": "#3fb950", "uncommon": "#e3b341", "rare": "#58a6ff", "legendary": "#a371f7"}


def xterm_hex(n: int) -> str:
    if n < 16:
        base = ["000000", "800000", "008000", "808000", "000080", "800080", "008080", "c0c0c0",
                "808080", "ff0000", "00ff00", "ffff00", "0000ff", "ff00ff", "00ffff", "ffffff"]
        return "#" + base[n]
    if n >= 232:
        v = 8 + (n - 232) * 10
        return "#%02x%02x%02x" % (v, v, v)
    n -= 16
    lv = [0, 95, 135, 175, 215, 255]
    return "#%02x%02x%02x" % (lv[n // 36], lv[(n // 6) % 6], lv[n % 6])


def pixel_rects(half_rows: list[str], ramps: dict, x0: int, y0: int, scale: int, dither: float = 0.3, rim: float = 1.6) -> str:
    """A mirrored pixel map as SVG rects, merging horizontal runs of one colour."""
    grid = _mirror(half_rows)
    out = []
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            p = _pixel(ramps, grid, x, y, dither, rim)
            if not p:
                x += 1
                continue
            end = x + 1
            while end < len(row) and (q := _pixel(ramps, grid, end, y, dither, rim)) and q[0] == p[0]:
                end += 1
            out.append(f'<rect x="{x0 + x * scale}" y="{y0 + y * scale}" width="{(end - x) * scale}" height="{scale}" fill="{xterm_hex(p[0])}"/>')
            x = end
    return "".join(out)


def _t(text, x, y, size=13, fill="#c9d1d9", weight="normal", anchor="start", style="") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" {style}'
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">{html.escape(str(text))}</text>')


def card(ch: Character) -> str:
    done = ch.xp - xp_for_level(ch.level)
    need = xp_for_level(ch.level + 1) - xp_for_level(ch.level)
    frac = max(0.0, min(1.0, done / need))
    cls_hex = xterm_hex(CLASS_COLORS.get(ch.cls, 7))
    rate = f"{100 * ch.wins // ch.encounters}%" if ch.encounters else "-"
    w, h = 560, 340

    rows, ramps = avatar_mod.portrait(ch.name, ch.cls)
    face = pixel_rects(rows, ramps, 33, 33, 7)

    # chunky pixel bar: green segments (the colour of a passing check) lit from above
    segs = 28
    on = min(segs, max(1 if done > 0 else 0, round(frac * segs)))
    xp_bar = ""
    for i in range(segs):
        sx = 140 + i * 14
        if i < on:
            xp_bar += (f'<rect x="{sx}" y="98" width="12" height="10" fill="#196c2e"/>'
                       f'<rect x="{sx}" y="98" width="12" height="7" fill="#2ea043"/>'
                       f'<rect x="{sx}" y="98" width="12" height="3" fill="#56d364"/>')
        else:
            xp_bar += f'<rect x="{sx}" y="98" width="12" height="10" fill="#21262d"/>'

    chips = [("HP", ch.hp_max), ("MP", ch.mp_max), ("GRAY", ch.gray)]
    chip_svg = ""
    for i, (label, value) in enumerate(chips):
        cx = 140 + i * 134
        chip_svg += (f'<rect x="{cx}" y="118" width="124" height="30" rx="6" fill="#161b22" stroke="#30363d"/>'
                     + _t(label, cx + 10, 138, 11, "#8b949e") + _t(value, cx + 114, 138, 14, "#e6edf3", "bold", "end"))

    gear = ""
    for n, (item, slot_name) in enumerate([(ch.main_hand, "weapon"), (ch.accessory, "accessory")]):
        top = 192 + n * 44
        if not item:
            gear += _t(f"No {slot_name} equipped", 30, top + 20, 12, "#6e7681")
            continue
        name, rarity = items.parse(item)
        rc = RARITY_HEX.get(rarity, "#c9d1d9")
        icon = pixel_rects(ITEM_SPRITES[items.category(item)], ITEM_RAMPS, 30, top, 4, rim=0.6)
        gear += icon + _t(name, 112, top + 12, 14, rc, "bold") + _t(f"{rarity}  \u00b7  {slot_name}", 112, top + 30, 11, "#8b949e", style='font-style="italic" ')

    bag = _t(f"bag: {len(ch.inventory)} item{'s' if len(ch.inventory) != 1 else ''}", w - 24, 204, 11, "#8b949e", anchor="end")
    active = items.active_set(ch.main_hand, ch.accessory)
    if active:
        gear += _t(f"\u2726 Set: {active.name}", w - 24, 248, 11, "#e3b341", "bold", "end")
    pills, px = "", 30
    for name in ch.achievements[:4]:
        label = name.split(" (")[0]
        pw = int((len(label) + 2) * 7.4) + 20
        if px + pw > w - 70:
            break
        pills += (f'<rect x="{px}' + f'" y="296" width="{pw}" height="22" rx="11" fill="#161b22" stroke="#30363d"/>'
                  + _t("\u2605", px + 10, 311, 11, "#e3b341") + _t(label, px + 25, 311, 11, "#c9d1d9"))
        px += pw + 8
    if not ch.achievements:
        pills = _t("No achievements yet", 30, 311, 11, "#484f58")
    elif len(ch.achievements) > 4 or px > w - 100:
        pills += _t(f"+{max(len(ch.achievements) - pills.count('<rect'), 0)}", px + 2, 311, 11, "#8b949e")
    ach = bag + pills

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges" role="img" aria-label="{html.escape(ch.name)}, level {ch.level} {ch.cls}">
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="#0d1117" stroke="#30363d"/>
<rect x="24" y="24" width="102" height="102" rx="8" fill="#161b22" stroke="#30363d"/>{face}
{_t(ch.name, 140, 50, 24, "#e6edf3", "bold")}
{_t(f"Level {ch.level} {ch.cls}", 140, 72, 14, cls_hex, "bold")}
{xp_bar}
{_t(f"{done:,} / {need:,} XP", w - 28, 92, 11, "#8b949e", anchor="end")}
{chip_svg}
<circle cx="150" cy="172" r="7" fill="#e3b341" stroke="#9e6a03"/>{_t("'", 150, 176, 10, "#9e6a03", "bold", "middle")}
{_t(f"{ch.kens:,} 'kens", 164, 177, 14, "#e3b341", "bold")}
{_t(f"streak {ch.streak}", 300, 177, 14, "#39d0d8" if ch.streak else "#8b949e", "bold")}
{_t(f"{ch.wins}W / {ch.losses}L  ({rate})", 420, 177, 13, "#c9d1d9")}
<line x1="24" y1="184" x2="{w - 24}" y2="184" stroke="#21262d"/>
{gear}{ach}
<a href="https://github.com/lowlysre/questops">{_t("github.com/lowlysre/questops", w - 24, 330, 10, "#6e7681", anchor="end")}</a>
</svg>
"""


def badges(ch: Character) -> dict[str, dict]:
    """shields.io endpoint payloads, one per file:
    https://img.shields.io/endpoint?url=<raw url of the json>"""

    def b(label: str, message: str, color: str) -> dict:
        return {"schemaVersion": 1, "label": label, "message": message, "color": color}

    return {
        "level": b("level", f"{ch.level} {ch.cls}", "blueviolet"),
        "kens": b("'kens", f"{ch.kens:,}", "yellow"),
        "streak": b("streak", str(ch.streak), "brightgreen" if ch.streak else "lightgrey"),
        "record": b("record", f"{ch.wins}W / {ch.losses}L", "blue"),
    }


def badges_json(ch: Character) -> dict[str, str]:
    return {name: json.dumps(payload) + "\n" for name, payload in badges(ch).items()}


def title_svg(scale: int = 10) -> str:
    """The pixel-art title as an SVG, identical to the one in the console."""
    from .title import _pixels

    grid = _pixels()
    w, h = len(grid[0]) * scale, len(grid) * scale
    out = []
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            c = row[x]
            if c is None:
                x += 1
                continue
            end = x + 1
            while end < len(row) and row[end] == c:
                end += 1
            out.append(f'<rect x="{x * scale}" y="{y * scale}" width="{(end - x) * scale}" height="{scale}" fill="{xterm_hex(c)}"/>')
            x = end
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges" role="img" aria-label="QuestOps">{"".join(out)}</svg>\n')
