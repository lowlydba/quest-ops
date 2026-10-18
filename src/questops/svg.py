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
from .state import TOH, Character, money, xp_for_level

# Dark card colours and their light-mode twins. A colour in here gets a class, and a `prefers-color-scheme: light`
# rule swaps it, so the one SVG follows the viewer's theme; the plain attribute is the dark fallback.
THEME = {
    "#0d1117": "#ffffff", "#161b22": "#f6f8fa", "#21262d": "#eaeef2", "#30363d": "#d0d7de",
    "#e6edf3": "#1f2328", "#c9d1d9": "#24292f", "#8b949e": "#59636e", "#6e7681": "#6e7781", "#484f58": "#8c959f",
    "#e3b341": "#9a6700", "#3fb950": "#1a7f37", "#58a6ff": "#0969da", "#a371f7": "#8250df", "#39d0d8": "#0e7c86",
    "#c0c0c0": "#7a838c", "#7d7d7d": "#5c656d", "#cd7f32": "#a15c14", "#8a5a1f": "#6b3f0c",
}
_KEY = {dark: i for i, dark in enumerate(THEME)}


def _paint(fill: str | None = None, stroke: str | None = None, klass: str = "") -> str:
    """fill/stroke attributes plus the classes that retheme them in light mode."""
    attrs, classes = "", [klass] if klass else []
    for attr, colour, prefix in (("fill", fill, "f"), ("stroke", stroke, "s")):
        if colour:
            attrs += f' {attr}="{colour}"'
            if colour in _KEY:
                classes.append(f"{prefix}{_KEY[colour]}")
    return attrs + (f' class="{" ".join(classes)}"' if classes else "")


def _darken(hex_colour: str, k: float = 0.62) -> str:
    return "#" + "".join(f"{round(int(hex_colour[i:i + 2], 16) * k):02x}" for i in (1, 3, 5))


def _theme_css(cls_hex: str) -> str:
    rules = "".join(f".f{i}{{fill:{light}}}.s{i}{{stroke:{light}}}" for i, light in enumerate(THEME.values()))
    return f"<style>@media (prefers-color-scheme:light){{{rules}.cls{{fill:{_darken(cls_hex)}}}}}</style>"


RARITY_HEX = {"common": "#3fb950", "uncommon": "#e3b341", "rare": "#58a6ff", "legendary": "#a371f7"}
PROJECT_REPO = "lowlydba/quest-ops"


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


def _t(text, x, y, size=13, fill="#c9d1d9", weight="normal", anchor="start", style="", klass="") -> str:
    return (f'<text x="{x}" y="{y}"{_paint(fill, klass=klass)} font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" {style}'
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">{html.escape(str(text))}</text>')


def _purse(kens: int) -> str:
    """The card's balance, one coin per denomination: silver for toh, bronze for 'kens."""
    toh, rest = divmod(kens, TOH)
    out, x = "", 146
    for text, fill, stroke in ([(f"{toh:,} toh", "#c0c0c0", "#7d7d7d")] if toh else []) + ([(f"{rest:,} 'kens", "#cd7f32", "#8a5a1f")] if rest or not toh else []):
        out += f'<circle cx="{x}" cy="172" r="5"{_paint(fill, stroke)}/>' + _t(text, x + 9, 177, 13, fill, "bold")
        x += 9 + round(len(text) * 7.8) + 8
    return out


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
            xp_bar += f'<rect x="{sx}" y="98" width="12" height="10"{_paint("#21262d")}/>'

    chips = [("HP", ch.hp_max), ("MP", ch.mp_max), ("GRAY", ch.gray)]
    chip_svg = ""
    for i, (label, value) in enumerate(chips):
        cx = 140 + i * 134
        chip_svg += (f'<rect x="{cx}" y="118" width="124" height="30" rx="6"{_paint("#161b22", "#30363d")}/>'
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
        pills += (f'<rect x="{px}' + f'" y="296" width="{pw}" height="22" rx="11"{_paint("#161b22", "#30363d")}/>'
                  + _t("\u2605", px + 10, 311, 11, "#e3b341") + _t(label, px + 25, 311, 11, "#c9d1d9"))
        px += pw + 8
    if not ch.achievements:
        pills = _t("No achievements yet", 30, 311, 11, "#484f58")
    elif len(ch.achievements) > 4 or px > w - 100:
        pills += _t(f"+{max(len(ch.achievements) - pills.count('<rect'), 0)}", px + 2, 311, 11, "#8b949e")
    ach = bag + pills

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges" role="img" aria-label="{html.escape(ch.name)}, level {ch.level} {ch.cls}">
{_theme_css(cls_hex)}
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14"{_paint("#0d1117", "#30363d")}/>
<rect x="24" y="24" width="102" height="102" rx="8"{_paint("#161b22", "#30363d")}/>{face}
{_t(ch.name, 140, 50, 24, "#e6edf3", "bold")}
{_t(f"Level {ch.level} {ch.cls}", 140, 72, 14, cls_hex, "bold", klass="cls")}
{xp_bar}
{_t(f"{done:,} / {need:,} XP", w - 28, 92, 11, "#8b949e", anchor="end")}
{chip_svg}
{_purse(ch.kens)}
{_t(f"streak {ch.streak}", 316, 177, 14, "#39d0d8" if ch.streak else "#8b949e", "bold")}
{_t(f"{ch.wins}W / {ch.losses}L  ({rate})", 430, 177, 13, "#c9d1d9")}
<line x1="24" y1="184" x2="{w - 24}" y2="184"{_paint(stroke="#21262d")}/>
{gear}{ach}
<a href="https://github.com/{PROJECT_REPO}">{_t(f"github.com/{PROJECT_REPO}", w - 24, 330, 10, "#6e7681", anchor="end")}</a>
</svg>
"""


def badges(ch: Character) -> dict[str, dict]:
    """shields.io endpoint payloads, one per file:
    https://img.shields.io/endpoint?url=<raw url of the json>"""

    def b(label: str, message: str, color: str) -> dict:
        return {"schemaVersion": 1, "label": label, "message": message, "color": color}

    return {
        "hero": b(ch.name, f"Lv {ch.level} {ch.cls} \u00b7 {money(ch.kens)}", "blueviolet"),
        "level": b("level", f"{ch.level} {ch.cls}", "blueviolet"),
        "kens": b("'kens", money(ch.kens, False), "orange"),
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
