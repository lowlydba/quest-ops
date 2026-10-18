"""Pixel grids and the swappable cell backends that turn them into text.

Sprites, shadows, the title and avatars all build a grid (rows of `Px` or None)
and hand it to a backend:

  half    two pixels per text cell: an upper/lower half block with fg and bg colours
  solid   two pixels per text cell, but one colour each (fg=bg on a half block):
          the default in GitHub Actions, whose log viewer smears two-colour cells
  square  one text row per pixel row, each pixel `cell_width` columns of a block
          glyph whose fg and bg are both the pixel colour (never a bare space: log
          viewers drop the background of whitespace-only text)
  plain   no colour: shade glyphs by brightness (or block glyphs for the title)

Runs of cells that share the same colours are emitted as one escape sequence, one
reset and the repeated glyphs, so log viewers draw them as a single span. A `Label`
puts real (bold) text over a grid: unlike pixels, text stays crisp at any line height.
`QUESTOPS_PIXELS=half|solid|square|plain` picks the backend when colour is on; with
colour off the plain backend is always used.
"""

from __future__ import annotations

import os
from itertools import groupby
from typing import NamedTuple

SHADE = "░░▒▒▓█"  # plain fallback by brightness level


class Px(NamedTuple):
    color: int  # xterm-256 colour
    level: int = 0  # brightness step within its ramp, for the shade fallback
    kind: str = ""  # region marker: E eyes, T teeth, M void, S shadow


class Label(NamedTuple):
    """Real text drawn over a grid, so it stays crisp at any line height: starts at pixel (y, x)."""

    y: int
    x: int
    text: str
    ink: int


Rows = list[list[Px | None]]
Cell = tuple  # (fg, bg, glyph) or (fg, bg, glyph, bold)


def emit(cells: list[Cell]) -> str:
    """Join cells, wrapping each run of identical colours in a single escape pair."""
    out = []
    for (fg, bg, bold), run in groupby(cells, key=lambda c: (c[0], c[1], len(c) > 3 and c[3])):
        text = "".join(c[2] for c in run)
        if fg is None and bg is None:
            out.append(text)
            continue
        params = ("1" if bold else None, None if fg is None else f"38;5;{fg}", None if bg is None else f"48;5;{bg}")
        out.append(f"\x1b[{';'.join(p for p in params if p)}m{text}\x1b[0m")
    return "".join(out)


def _label_cells(cells: list[Cell], rows: Rows, label: Label, cell_width: int = 1) -> None:
    """Write a label's characters into a text row's cells, one per pixel column, on the colour beneath."""
    for i, ch in enumerate(label.text):
        under = rows[label.y][label.x + i]
        cells[(label.x + i) * cell_width] = (label.ink, under.color if under else None, ch, True)


def _even(rows: Rows) -> Rows:
    return rows + [[None] * len(rows[0])] if len(rows) % 2 else rows


def _half(top: Px | None, bot: Px | None) -> Cell:
    if top and bot:
        return top.color, bot.color, "\u2580"
    if top:
        return top.color, None, "\u2580"
    if bot:
        return bot.color, None, "\u2584"
    return None, None, " "


def _solid(top: Px | None, bot: Px | None) -> Cell:
    """One colour per cell, painted as fg=bg on a half block so the background fills the whole line.
    GitHub's log viewer paints backgrounds over the full line but glyphs over a shorter box, so a
    cell with two colours smears and a glyph-only cell leaves a gap. Features win a shared cell
    cell (eyes, then teeth, then dark void such as a mouth), then sprite pixels, then scene outlines
    and backdrop, and anything beats a ground shadow."""
    cells = [p for p in (top, bot) if p]
    if not cells:
        return None, None, " "
    rank = {"E": 0, "T": 1, "M": 2, "": 3, "O": 4, "G": 4, "S": 5}
    keep = min(cells, key=lambda p: (rank.get(p.kind, 3), cells.index(p)))
    return keep.color, keep.color, "\u2580"


def _shade(top: Px | None, bot: Px | None) -> str:
    cells = [p for p in (top, bot) if p]
    kinds = {p.kind for p in cells}
    if not cells or kinds == {"M"}:
        return " "
    if "E" in kinds:
        return "@"
    if "T" in kinds:
        return "v"
    cells = [p for p in cells if p.kind != "M"]
    return SHADE[round(sum(p.level for p in cells) / len(cells))]


def _block(top: Px | None, bot: Px | None) -> str:
    solid_t, solid_b = bool(top) and top.kind != "S", bool(bot) and bot.kind != "S"
    if solid_t and solid_b:
        return "\u2588"
    if solid_t:
        return "\u2580"
    if solid_b:
        return "\u2584"
    return "\u2591" if top or bot else " "


class Backend:
    name = ""
    cell_width = 1  # text columns per pixel column
    colored = True
    width: int | None = 62  # fixed layout width, or None to size layouts from their content

    def draw(self, rows: Rows, plain: str = "shade", labels: tuple[Label, ...] = ()) -> list[str]:
        """Text lines for a grid. `plain` picks the colourless glyph set: 'shade' or 'block'."""
        raise NotImplementedError  # pragma: no cover


class Half(Backend):
    name = "half"
    cell = staticmethod(_half)

    def draw(self, rows: Rows, plain: str = "shade", labels: tuple[Label, ...] = ()) -> list[str]:
        rows = _even(rows)
        lines = []
        for y in range(0, len(rows), 2):
            cells = [self.cell(t, b) for t, b in zip(rows[y], rows[y + 1])]
            for label in labels:
                if label.y // 2 == y // 2:
                    _label_cells(cells, rows, label)
            lines.append(emit(cells))
        return lines


class Solid(Half):
    """Two pixels per text cell like `half`, but one colour each, so nothing smears in CI logs."""

    name = "solid"
    cell = staticmethod(_solid)


class Square(Backend):
    name = "square"
    width = None

    def __init__(self, cell_width: int = 2):
        self.cell_width = cell_width

    def draw(self, rows: Rows, plain: str = "shade", labels: tuple[Label, ...] = ()) -> list[str]:
        lines = []
        for y, row in enumerate(rows):
            cells = [(p.color, p.color, "\u2580") if p else (None, None, " ") for p in row for _ in range(self.cell_width)]
            for label in labels:
                if label.y == y:
                    _label_cells(cells, rows, label, self.cell_width)
            lines.append(emit(cells))
        return lines


class Plain(Backend):
    name = "plain"
    colored = False

    def draw(self, rows: Rows, plain: str = "shade", labels: tuple[Label, ...] = ()) -> list[str]:
        rows = _even(rows)
        glyph = _shade if plain == "shade" else _block
        lines = []
        for y in range(0, len(rows), 2):
            chars = [glyph(t, b) for t, b in zip(rows[y], rows[y + 1])]
            for label in labels:
                if label.y // 2 == y // 2:
                    chars[label.x : label.x + len(label.text)] = label.text
            lines.append("".join(chars))
        return lines


HALF, SOLID, SQUARE, PLAIN = Half(), Solid(), Square(), Plain()
BACKENDS = {b.name: b for b in (HALF, SOLID, SQUARE, PLAIN)}


def backend_for(color: bool | Backend) -> Backend:
    """The backend for a colour flag (or a backend, passed through). GitHub Actions logs get
    `solid`, since they smear two-colour cells; terminals get `half`."""
    if isinstance(color, Backend):
        return color
    if not color:
        return PLAIN
    default = SOLID if os.environ.get("GITHUB_ACTIONS") else HALF
    return BACKENDS.get(os.environ.get("QUESTOPS_PIXELS", "").strip().lower(), default)
