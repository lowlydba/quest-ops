"""The title card, drawn as pixel art to match the sprites.

The SVG banner uses a 5x7 pixel font spelling QUES-sword-OPS (the sword stands in
for the 't') with a purple-to-cyan gradient, a bright top edge and a drop shadow.
In text, the title uses a 5x5 font at one pixel per cell, each cell a single colour,
so no log viewer can smear it.
"""

from __future__ import annotations

from .pixels import Backend, backend_for, emit

FONT = {
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    # the 't': a sword. b blade, g guard, h grip, p pommel
    "!": ["..b..", "..b..", "..b..", "..b..", "ggggg", "..h..", "..p.."],
}
WORD = "QUES!OPS"
GRADIENT = [141, 105, 69, 75, 81, 87, 123]  # row 0..6, purple to cyan
SWORD = {"b": 255, "g": 220, "h": 130, "p": 220}
SHADOW = 234
HIGHLIGHT = 231

# The text title is drawn at text resolution (one pixel per cell), so it gets its own 5x5 font.
TEXT_FONT = {
    "Q": [".###.", "#...#", "#...#", "#..#.", ".##.#"],
    "U": ["#...#", "#...#", "#...#", "#...#", ".###."],
    "E": ["#####", "#....", "####.", "#....", "#####"],
    "S": [".####", "#....", ".###.", "....#", "####."],
    "O": [".###.", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "####.", "#....", "#...."],
    "!": ["..b..", "..b..", "..b..", "ggggg", "..h.."],
}
TEXT_GRADIENT = [141, 105, 75, 81, 123]


def _pixels() -> list[list[int | None]]:
    """The detailed 5x7 title, one entry per pixel: the SVG banner draws every one of them."""
    cols = []
    for ch in WORD:
        glyph = FONT[ch]
        for x in range(5):
            cols.append([(glyph[y][x]) for y in range(7)])
        cols.append([".", ".", ".", ".", ".", ".", "."])  # letter spacing
    cols.pop()
    w, h = len(cols), 8
    # +1 for the drop shadow offset
    grid: list[list[int | None]] = [[None] * (w + 1) for _ in range(h + 1)]
    for x, col in enumerate(cols):
        for y, c in enumerate(col):
            if c != ".":
                grid[y + 1][x + 1] = SHADOW if grid[y + 1][x + 1] is None else grid[y + 1][x + 1]
    for x, col in enumerate(cols):
        for y, c in enumerate(col):
            if c == ".":
                continue
            if c == "#":
                grid[y][x] = HIGHLIGHT if y == 0 else GRADIENT[y]
            else:
                grid[y][x] = SWORD[c]
    return grid


def _cells() -> list[list[int | None]]:
    """The 5x5 text title: one colour per text cell, letters over a one-cell drop shadow."""
    cols = []
    for ch in WORD:
        for x in range(5):
            cols.append([TEXT_FONT[ch][y][x] for y in range(5)])
        cols.append(["."] * 5)
    cols.pop()
    grid: list[list[int | None]] = [[None] * (len(cols) + 1) for _ in range(6)]
    for x, col in enumerate(cols):
        for y, c in enumerate(col):
            if c != ".":
                grid[y + 1][x + 1] = SHADOW
    for x, col in enumerate(cols):
        for y, c in enumerate(col):
            if c != ".":
                grid[y][x] = TEXT_GRADIENT[y] if c == "#" else SWORD[c]
    return grid


def title(color: bool | Backend) -> str:
    """The title in text: each cell one colour (fg=bg on a half block), so no log viewer can smear it."""
    backend = backend_for(color)
    grid = _cells()
    if not backend.colored:
        return "\n".join("".join(" " if c is None else "\u2591" if c == SHADOW else "\u2588" for c in row).rstrip() for row in grid)
    return "\n".join(emit([(c, c, "\u2580") if c is not None else (None, None, " ") for c in row]) for row in grid)
