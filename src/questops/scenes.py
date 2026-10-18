"""Background scenes that a sprite stands in: a corridor, a torch-lit wall, a staircase and a raycaster castle.

Each backdrop is computed in RGB (perspective, light falloff, flame glow), ordered-dithered
and snapped to the xterm-256 palette, so it stays within the 256-colour rule. A sprite is
composited on top with a one-pixel dark outline and a soft shadow on the floor where its
feet land. Colourless output skips the backdrop: shade glyphs cannot draw a room.
"""

from __future__ import annotations

import math
from functools import lru_cache

from .pixels import Backend, Px, Rows, backend_for
from .sprites import _mirror, _pixel
from .state import seed_int

W, H = 44, 26  # scene size in pixels (half backend: 60 columns x 16 rows)
FLOOR = 23  # the row a sprite's feet stand on
SCENES = ("corridor", "torches", "stairs", "castle")

RGB = tuple[float, float, float]
_BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
_STONE = (78, 76, 84)
_MORTAR = (26, 24, 30)
_VOID = (6, 6, 9)
_FIRE = (255, 150, 60)
_FLAGSTONE = (150, 144, 134)  # pale, worn floor stone, well above the walls' brightness


@lru_cache(maxsize=1)
def _palette() -> list[tuple[int, int, int, int]]:
    # 16-231 (colour cube) and 232-255 (greys); 0-15 follow the terminal theme, so never use them
    lv = [0, 95, 135, 175, 215, 255]
    cube = [(16 + i, lv[i // 36], lv[(i // 6) % 6], lv[i % 6]) for i in range(216)]
    greys = [(232 + i, 8 + 10 * i, 8 + 10 * i, 8 + 10 * i) for i in range(24)]
    return cube + greys


@lru_cache(maxsize=4096)
def _nearest(r: int, g: int, b: int) -> int:
    return min(_palette(), key=lambda p: (p[1] - r) ** 2 * 3 + (p[2] - g) ** 2 * 4 + (p[3] - b) ** 2 * 2)[0]


def quantize(rgb: RGB, x: int, y: int, spread: float = 18.0) -> int:
    """The xterm-256 colour for an RGB value, with 4x4 ordered dither so gradients do not band."""
    d = (_BAYER4[y % 4][x % 4] / 16 - 0.5) * spread
    r, g, b = (max(0, min(255, round(c + d))) for c in rgb)
    return _nearest(r, g, b)


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _scale(c: RGB, k: float) -> RGB:
    return (c[0] * k, c[1] * k, c[2] * k)


def _add(c: RGB, d: RGB, k: float) -> RGB:
    return (c[0] + d[0] * k, c[1] + d[1] * k, c[2] + d[2] * k)


def _bricks(u: float, v: float, length: float = 1.0, height: float = 0.5, joint: float = 0.12) -> tuple[bool, float]:
    """Running-bond brickwork at (u, v): (is mortar, a per-brick tint in -1..1)."""
    row = math.floor(v / height)
    uu = u / length + (0.5 if row % 2 else 0.0)
    col = math.floor(uu)
    mortar = (v / height - row) < joint * 2 or (uu - col) < joint
    tint = ((col * 73 + row * 151) % 7) / 3 - 1
    return mortar, tint


def _stone(mortar: bool, tint: float, light: float) -> RGB:
    return _MORTAR if mortar else _scale(_STONE, light * (1 + 0.1 * tint))


def _tunnel(cy: float, hx: float, hy: float, floor, far, light_of) -> list[list[RGB]]:
    """A passage in one-point perspective centred on (W/2, cy) whose far end is hx by hy on screen.
    `floor(dx, z, s)` and `far(dx, dy)` colour those regions; `light_of(z)` lights walls and ceiling."""
    cx = W / 2
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            s = max(abs(dx) / hx, abs(dy) / hy)
            if s <= 1:
                row.append(far(dx, dy))
                continue
            z = 8.0 / s  # distance into the passage; 8 at the far end
            light = light_of(z)
            if abs(dx) / hx >= abs(dy) / hy:  # side walls
                mortar, tint = _bricks(z, dy / s / hy * 3 + 3, 1.1, 0.55)
                row.append(_stone(mortar, tint, light * 0.9))
            elif dy > 0:
                row.append(floor(dx, z, s, light))
            else:  # ceiling with timber beams
                beam = (z * 1.3) % 1 < 0.22
                row.append(_scale((60, 40, 26) if beam else (40, 38, 44), light * 0.7))
        out.append(row)
    return out


def corridor() -> list[list[RGB]]:
    """A stone corridor, lit from behind the hero and fading into the dark."""
    hx = 7.0

    def floor(dx: float, z: float, s: float, light: float) -> RGB:
        u = abs(dx / s / hx)  # 0 down the middle, 1 at the walls
        if u < 0.6:  # a long runner down the middle: red, gold trim, a diamond every stride
            if 0.48 <= u < 0.54:
                return _scale((170, 130, 50), light)
            diamond = u + abs((z * 1.2) % 1 - 0.5) * 0.6 < 0.2
            return _scale((150, 110, 50) if diamond else (120, 24, 30), light * (0.85 if u >= 0.54 else 1))
        mortar, tint = _bricks(dx / s / hx * 2, z, 0.9, 0.9, 0.08)
        return _scale(_MORTAR if mortar else (104, 80, 62), light * (1 + 0.08 * tint))

    def far(dx: float, dy: float) -> RGB:  # the dark at the end of the passage
        return (0, 0, 0)

    return _tunnel(11.0, hx, 4.5, floor, far, lambda z: max(0.0, min(1.25, 2.2 / z) ** 1.3 - 0.1) * 1.1)


# What shows through the stair-top doorway (14 x 9): bare trees in silhouette on a dim hillside.
_OUTSIDE = [
    "..............",
    "..t.t.........",
    "t..tt..t......",
    ".t..t.t.......",
    "..t.ttt.......",
    "....tt........",
    "....t.........",
    "hhhhthhhhh....",
    "hhhhhhhhhhhhhh",
]
_OUTSIDE_COLOURS = {"t": (40, 28, 30), "h": (84, 58, 48)}


def stairs() -> list[list[RGB]]:
    """A landing partway up a stair: the flight climbs behind it to an arched, daylit doorway."""
    cx, door_w, door_h, landing = W / 2, 7.0, 9, 22
    door = (255, 214, 150)
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            dx = x + 0.5 - cx
            up = 1 - y / landing  # 1 at the doorway, 0 at the landing
            if y >= landing:  # the landing: worn flagstones, the front edge dropping away
                if y == landing:
                    col = (28, 26, 30)  # where the bottom riser meets the landing
                else:
                    mortar, tint = _bricks(dx / (5 + (y - landing) * 1.5), (y - landing) ** 0.5 * 1.4, 1, 1, 0.12)
                    col = _scale(_MORTAR if mortar else _FLAGSTONE, 0.85 + 0.02 * (y - landing) + 0.06 * tint)
            elif y < door_h and abs(dx) < door_w + 1:  # the doorway in a stone frame, with a low arch
                spring = 2
                arch = y < spring and dx**2 + ((spring - y) * 3.5) ** 2 > door_w**2
                if abs(dx) >= door_w or arch:
                    col = (96, 88, 84) if not (y < spring and dx**2 + ((spring - y) * 3.5) ** 2 > (door_w + 1) ** 2) else (34, 30, 32)
                else:  # daylight, with dead trees on the far hillside
                    mark = _OUTSIDE[y][int(x - (cx - door_w))]
                    col = _OUTSIDE_COLOURS.get(mark) or _mix((255, 240, 200), (225, 155, 85), y / door_h)
            elif y >= door_h and abs(dx) < door_w + (y - door_h) * 1.1:  # the flight, widening toward us
                half = door_w + (y - door_h) * 1.1
                f = ((y - door_h) / 2.5) % 1  # each step: lit lip, shadow, riser
                light = 0.45 + 0.6 * up**2
                if half - abs(dx) < 1:  # the lit edge of the stone stringer
                    col = _scale((110, 104, 100), light)
                elif f < 0.4:  # the worn lip of the tread catches the light
                    col = _add(_scale((136, 126, 116), light), door, 0.25 * up)
                elif f < 0.6:
                    col = _scale(_MORTAR, light)
                else:
                    col = _scale((58, 54, 58), light * 0.85)
            else:  # walls, warmed near the doorway, with a stained-glass window either side
                mortar, tint = _bricks(x / 8, y / 4, 1, 0.75, 0.1)
                col = _stone(mortar, tint, 0.32 + 0.1 * up)
                col = _add(col, door, 0.25 / (1 + (dx**2 + (y - door_h / 2) ** 2) / 60))
                col = _window(x, y, col)
            row.append(col)
        out.append(row)
    return out


_GLASS = [(200, 40, 50), (50, 90, 210), (230, 180, 50), (40, 150, 90), (140, 60, 180)]
_VANISH = (W / 2, 4.0)  # where the side walls recede to, behind the doorway


def _window(x: int, y: int, wall: RGB) -> RGB:
    """A pointed stained-glass window on each side wall, seen at an angle: its near edge tall, its far edge
    shrinking toward the vanishing point, panes foreshortened. It glows faintly on the wall around it."""
    vx, vy = _VANISH
    near, far, top0, bottom0 = 4.5, 12.5, 3.5, 18.0  # distance from the screen edge; outer edge's top and bottom
    dist = abs(x + 0.5 - vx)
    d0, d1 = vx - near, vx - far
    if d1 <= dist <= d0:
        k = dist / d0  # 1 at the near edge, shrinking inward
        u = (d0 / dist - 1) / (d0 / d1 - 1)  # across the window in wall space (perspective-correct)
        top, bottom = vy + (top0 - vy) * k, vy + (bottom0 - vy) * k
        v = (y + 0.5 - top) / (bottom - top)
        arch = 0.3
        if 0 <= v <= 1 and (v >= arch or abs(u - 0.5) * 2 <= v / arch):
            if u < 0.1 or u > 0.9 or v > 0.95 or (v < arch and abs(u - 0.5) * 2 > v / arch - 0.35):
                return _scale((104, 96, 92), 0.6 + 0.4 * k)  # the stone frame, darker as it recedes
            if abs(u - 0.5) < 0.06 or (v - arch) % 0.3 < 0.05:
                return (24, 20, 24)  # the lead
            side = x > vx
            pane = _GLASS[(int(u > 0.5) * 3 + int(max(v - arch, 0) / 0.3) + side) % len(_GLASS)]
            return _scale(pane, 0.6 + 0.4 * k)
    glow = sum(1 / (1 + ((x - wx) ** 2 + (y - 9) ** 2) / 20) for wx in (8, W - 9))
    return _add(wall, (150, 110, 170), 0.15 * glow)


_BRICK = ((150, 30, 24), (184, 36, 28), (104, 16, 14))  # brick faces: base, highlight, shadow
_BRICK_MORTAR = (128, 128, 128)
_BLUE_BRICK = ((0, 0, 175), (70, 70, 225), (0, 0, 120))  # saturated dark blue stone, as in the raycaster's dungeon cells
_BLUE_MORTAR = (58, 58, 70)


def _red_brick(u: float, v: float, shade: float, bricks=_BRICK, mortar=_BRICK_MORTAR) -> RGB:
    """Castle brick: a running bond in grey mortar, each brick lit on top and shadowed below, some darker."""
    row = math.floor(v * 4)
    uu = u * 0.7 + (0.5 if row % 2 else 0.0)
    col = math.floor(uu)
    fu, fv = uu % 1, (v * 4) % 1
    if fu < 0.06 or fv < 0.12:
        return mortar
    base, hi, lo = bricks
    face = hi if fv < 0.24 else lo if fv > 0.88 else base
    dark = 0.8 if (col * 7 + row * 3) % 5 == 0 else 1.0
    return _scale(face, shade * dark)


def _steel_door(t: float, v: float, y: int) -> RGB:
    """A teal steel door at (t across, v down), both 0..1: a riveted border, a panel lit from the top left
    and a lock plate on the latch side."""
    if t < 0.14 or t > 0.86 or v < 0.05 or v > 0.96:
        return (150, 215, 215) if y % 3 == 0 and 0.05 <= v <= 0.96 else (34, 104, 112)  # rivets on the border
    if 0.62 < t < 0.8 and 0.46 < v < 0.56:
        return (40, 40, 40) if 0.49 < v < 0.53 and t > 0.7 else (176, 168, 96)  # the lock plate and keyhole
    return _mix((130, 220, 220), (64, 160, 170), (t + v) / 2)


def castle(bricks=_BRICK, mortar=_BRICK_MORTAR) -> list[list[RGB]]:
    """An homage to a 1992 raycaster: flat grey ceiling and floor, red brick walls with no distance falloff
    (only the side walls shaded darker), a steel door in the right wall, a passage that ends in black and a lamp hanging from the ceiling."""
    cx, cy, hx, hy = W / 2, 14.0, 9.0, 7.0
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            s = max(abs(dx) / hx, 1.0)
            if abs(dy) > hy * s:
                row.append((56, 56, 56) if dy < 0 else (112, 112, 112))  # flat ceiling and floor
            elif s > 1:  # side walls, in perspective, with a steel door set into the right one
                z, v = 8.0 / s, dy / (hy * s) / 2 + 0.5
                if dx > 0 and 2.6 < z < 3.9 and v > 0.18:
                    row.append(_steel_door((z - 2.6) / 1.3, (v - 0.18) / 0.82, y))
                else:
                    row.append(_red_brick(z, v, 0.72, bricks, mortar))
            elif abs(dx) < 5 and dy > -hy + 2:  # the passage fades to black at the end
                row.append((0, 0, 0))
            else:  # the far wall, face on
                row.append(_red_brick(dx / hx * 2, dy / hy / 2 + 0.5, 1.0, bricks, mortar))
        out.append(row)
    for dy, line in enumerate(_LAMP):  # a hanging lamp, centred on the ceiling
        for dx, ch in enumerate(line):
            if ch != ".":
                out[dy][int(cx) - 3 + dx] = _LAMP_COLOURS[ch]
    return out


_LAMP = [
    "...c..",
    "...c..",
    ".gGGg.",
    "gGGGGg",
    "..yy..",
]
_LAMP_COLOURS = {"c": (40, 40, 40), "g": (40, 120, 60), "G": (80, 180, 90), "y": (255, 240, 150)}


_SCONCES = ((6, 12), (W - 7, 12))  # flame tip column and row


def _glow(x: float, y: float) -> float:
    """Warm light at (x, y) from both torches."""
    return sum(1.0 / (1 + ((x - fx) ** 2 + (y - fy - 2) ** 2) / 70) for fx, fy in _SCONCES)


def torches() -> list[list[RGB]]:
    """A brick wall with a burning sconce on either side, the floor catching the light."""
    wall_end = 24
    out: list[list[RGB]] = []
    for y in range(H):
        row = []
        for x in range(W):
            g = _glow(x + 0.5, y + 0.5)
            if y < wall_end:
                mortar, tint = _bricks(x / 8, y / 4 + 0.25, 1, 0.75, 0.1)
                base = _stone(mortar, tint, 0.45 + 0.1 * y / wall_end)
            elif y == wall_end:
                base = (30, 28, 32)  # the skirting shadow where wall meets floor
            else:
                depth = (y - wall_end) / (H - wall_end)
                lines = 1 + depth * 3
                mortar = ((x - W / 2) / (6 + depth * 10)) % 1 < 0.1 or (math.sqrt(y - wall_end) * 1.6) % 1 < 0.18
                base = _scale(_MORTAR if mortar else _FLAGSTONE, 0.7 + 0.25 * depth * lines / 4)
            row.append(_add(base, _FIRE, (0.5 if y < wall_end else 0.12) * g))  # pale floor stone shows less glow
        out.append(row)
    for fx, fy in _SCONCES:
        for dy, line in enumerate(_TORCH):
            for dx, ch in enumerate(line):
                if ch != ".":
                    out[fy - 4 + dy][fx - 2 + dx] = _TORCH_COLOURS[ch]
    return out


# A sconce, its flame tip at (2, 4): white-hot core, yellow, orange, red tips, then the iron cup and wall bracket.
_TORCH = [
    "..r..",
    ".r.r.",
    ".ror.",
    "royor",
    "oywyo",
    "oywyo",
    ".oyo.",
    "IIIII",
    ".iIi.",
    "..i..",
    "..i..",
    ".iii.",
]
_TORCH_COLOURS = {
    "r": (190, 50, 20), "o": (240, 120, 30), "y": (255, 200, 70), "w": (255, 250, 210),
    "I": (96, 84, 76), "i": (52, 46, 46),
}


def bluestone() -> list[list[RGB]]:
    """The castle in dark blue stone, for monsters whose colours fight red brick."""
    return castle(_BLUE_BRICK, _BLUE_MORTAR)


BACKDROPS = {"corridor": corridor, "torches": torches, "stairs": stairs, "castle": castle, "bluestone": bluestone}
CRISP = {"castle", "bluestone"}  # flat-shaded like its source: no dither
BLUESTONE_FOES = {"slime", "dragon"}  # their cyan and red clash with red brick


def suit(scene: str, key: str) -> str:
    """The scene as it is drawn for a monster: the castle goes blue behind foes that clash with red brick."""
    return "bluestone" if scene == "castle" and key in BLUESTONE_FOES else scene


# Lighting per monster tier (base, Senior, Skip Level): an RGB multiplier and a coloured ambient for the
# stone. Saturated things (flames, stained glass, the runner) keep their colour, so they still stand out.
TIER_LIGHT: list[tuple[RGB, RGB]] = [
    ((1.0, 1.0, 1.0), (0, 0, 0)),
    ((0.72, 0.95, 1.55), (0, 10, 30)),  # Senior: cold, after-hours blue
    ((1.35, 0.68, 1.12), (22, 0, 16)),  # Skip Level: an ominous red-violet
]


def light(c: RGB, tint: tuple[RGB, RGB]) -> RGB:
    """`c` under coloured light, applied in full to greys and fading out as colour gets more saturated."""
    mul, amb = tint
    hi, lo = max(c), min(c)
    k = 1 - (hi - lo) / hi if hi else 1.0
    return tuple(v * (1 + (m - 1) * k) + a * k for v, m, a in zip(c, mul, amb))  # type: ignore[return-value]


@lru_cache(maxsize=None)
def backdrop(name: str, tier: int = 0, solid: bool = False) -> tuple[tuple[int, ...], ...]:
    """A scene's background as xterm-256 colour numbers, lit for a monster tier. `solid` is for backends that
    draw one colour per text cell: each pair of rows is averaged before it snaps to the palette, so thin lines
    blend into texture instead of aliasing."""
    rgb, tint = BACKDROPS[name](), TIER_LIGHT[tier]
    if solid:
        rgb = [row for a, b in zip(rgb[::2], rgb[1::2]) for row in [[_mix(p, q, 0.5) for p, q in zip(a, b)]] * 2]
    spread = 0.0 if name in CRISP else 8.0
    return tuple(tuple(quantize(light(c, tint), x, y - y % 2 if solid else y, spread) for x, c in enumerate(row)) for y, row in enumerate(rgb))


def compose(name: str, half_rows: list[str], ramps: dict, tier: int = 0, solid: bool = False, dither: float = 0.9, rim: float = 1.6) -> Rows:
    """A sprite (left-half pixel map, mirrored) standing in a scene lit for its tier, as a pixel grid."""
    grid = _mirror(half_rows)
    sh, sw = len(grid), len(grid[0])
    while sh and not grid[sh - 1].strip("."):
        sh -= 1  # stand on the lowest drawn row, not the even-height padding
    ox, oy = (W - sw) // 2, FLOOR - sh + 1
    bg = backdrop(name, tier, solid)
    rows: Rows = [[Px(c, 0, "G") for c in row] for row in bg]
    solid = {(x, y) for y in range(sh) for x in range(sw) if grid[y][x] != "."}

    # a soft contact shadow under the feet
    c = ox + (sw - 1) / 2
    for y in range(FLOOR - 1, min(H, FLOOR + 3)):
        for x in range(W):
            d = ((x - c) / (sw / 2 + 2)) ** 2 + ((y - FLOOR - 0.5) / 2.2) ** 2
            if d < 1:
                rows[y][x] = Px(_darker(bg[y][x], 0.35 + 0.5 * d), 0, "S")
    for x, y in solid:  # outline so the sprite reads against any wall
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in solid and 0 <= ox + nx < W and 0 <= oy + ny < H:
                rows[oy + ny][ox + nx] = Px(16, 0, "O")
    for x, y in solid:
        rows[oy + y][ox + x] = _pixel(ramps, grid, x, y, dither, rim)
    return rows


def _darker(colour: int, k: float) -> int:
    p = {i: (r, g, b) for i, r, g, b in _palette()}[colour]
    return _nearest(*(round(v * k) for v in p))


def staged(name: str, half_rows: list[str], ramps: dict, color: bool | Backend, tier: int = 0) -> str:
    """The sprite in a scene lit for its tier, drawn through a pixel backend."""
    backend = backend_for(color)
    return "\n".join(backend.draw(compose(name, half_rows, ramps, tier, backend.name == "solid")))


def pick_scene(key: str) -> str:
    """The scene for an encounter, from its own hash of the seed so the dice are untouched."""
    return SCENES[seed_int("scene", key) % len(SCENES)]
