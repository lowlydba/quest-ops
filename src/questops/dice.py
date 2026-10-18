"""The merchant's d20, drawn as pixel art like the monsters.

The die is the classic front view of an icosahedron: a hexagon split into ten
triangular faces around a central one, lit from the top left. Faces are told apart
by shading alone (thin edge lines break up in CI log viewers), and the roll is real
bold text on the bright central face, so it stays readable at any line height and
without colour.
"""

from __future__ import annotations

from .pixels import Backend, Label, Px, Rows, backend_for

W, H = 21, 18
# The top and bottom points sit just outside the grid, so they're clipped into short flat edges:
# a one-pixel tip reads as a spinning top once a log viewer stretches pixels tall.
TOP, BOTTOM = (W / 2, -0.14 * H), (W / 2, 1.14 * H)
UL, UR, LL, LR = (0.0, 0.24 * H), (float(W), 0.24 * H), (0.0, 0.76 * H), (float(W), 0.76 * H)
APEX, BL, BR = (W / 2, 0.08 * H), (0.12 * W, 0.78 * H), (0.88 * W, 0.78 * H)

# (face corners, brightness step 0-5): the central face is brightest, the rest fall away from the top-left light.
FACES = [
    ((APEX, BL, BR), 5),
    ((TOP, APEX, UL), 4),
    ((TOP, APEX, UR), 3),
    ((UL, APEX, BL), 3),
    ((UR, APEX, BR), 2),
    ((UL, BL, LL), 2),
    ((UR, BR, LR), 1),
    ((LL, BL, BOTTOM), 1),
    ((LR, BR, BOTTOM), 0),
    ((BL, BR, BOTTOM), 1),
]

RAMPS = {
    "gold": [94, 130, 136, 172, 214, 222],
    "red": [52, 88, 124, 160, 196, 210],
    "green": [22, 28, 34, 70, 77, 114],
}
EDGE = 234
INK = 232
NUMBER_ROW = 10  # an even pixel row, so the number fills one text row on the central face


def _side(p, a, b) -> float:
    return (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])


def _inside(p, tri) -> bool:
    d = [_side(p, tri[i], tri[(i + 1) % 3]) for i in range(3)]
    return not (min(d) < 0 < max(d))


def _face(x: int, y: int) -> int | None:
    p = (x + 0.5, y + 0.5)
    return next((i for i, (tri, _) in enumerate(FACES) if _inside(p, tri)), None)


def ramp_for(roll: int, sides: int = 20) -> list[int]:
    """Gold, except a natural 1 (red) and the top face (green)."""
    return RAMPS["red"] if roll == 1 else RAMPS["green"] if roll == sides else RAMPS["gold"]


def grid(roll: int, sides: int = 20) -> Rows:
    """The die as a pixel grid: shaded faces inside a dark outline."""
    ramp = ramp_for(roll, sides)
    faces = [[_face(x, y) for x in range(W)] for y in range(H)]
    rows: Rows = []
    for y in range(H):
        row: list[Px | None] = []
        for x in range(W):
            f = faces[y][x]
            if f is None:
                row.append(None)
                continue
            around = [faces[y + dy][x + dx] if 0 <= x + dx < W and 0 <= y + dy < H else None for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            level = FACES[f][1]
            row.append(Px(EDGE, 0, "S") if None in around else Px(ramp[level], level))
        rows.append(row)
    return rows


def label(roll: int) -> Label:
    text = str(roll)
    return Label(NUMBER_ROW, (W - len(text) + 1) // 2, text, INK)


def d20(roll: int, color: bool | Backend, sides: int = 20) -> str:
    return "\n".join(backend_for(color).draw(grid(roll, sides), labels=(label(roll),)))
