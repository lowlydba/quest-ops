"""Pixel-art monsters drawn with half-block characters.

Each sprite is the LEFT half of a creature, one character per pixel; the right
half is a mirror. A row shorter than the half-width is extended with its last
character toward the centre. Characters are regions, not colours:

  B body     b belly (lighter)   W wing/secondary   H horn/bone
  M mouth/void   E eyes   T teeth   L metal   F flame   . empty

Colour comes from per-region ramps (dark to bright). Lighting is computed:
lit from the top-left, a dark rim on every outer edge, and a 2x2 dither so the
gradient reads as shading instead of banding. `pixels.py` turns the pixel grid into
text: by default two pixels stack in one cell (upper half-block with fg/bg colours),
so a 22-pixel sprite is 11 text rows. With NO_COLOR, each cell becomes a shade glyph
by brightness.
"""

from __future__ import annotations

from .pixels import Backend, Px, backend_for

SPRITES = {
    "goblin": [
        "..........BBBB",
        "........BBBBBB",
        ".B.....BBBBBBB",
        ".BB..BBBBBBBBB",
        ".BBBBBBBBBBBBB",
        "..BBBBBEEBBBBB",
        "...BBBBEEBBBBB",
        "....BBBBBBBBBB",
        ".....BBBMMMMMM",
        ".....BBBTMTMTM",
        "......BBBBBBBB",
        "....BBBBBBBBBB",
        "...BBBBBbbbbbb",
        "...BBBBbbbbbbb",
        "...BBBBbbbbbbb",
        "....BBBbbbbbbb",
        "....BBBBBbbbbb",
        ".....BBBBBBBBB",
        ".....BBB..BBBB",
        ".....BBB...BBB",
        "....BBBB...BBB",
        "...BBBBB...BBB",
    ],
    "wraith": [
        "..........BBBB",
        "........BBBBBB",
        "......BBBBBBBB",
        ".....BBBBBBBBB",
        "....BBBBBBBBBB",
        "....BBBBMMMMMM",
        "...BBBBBMMMMMM",
        "...BBBBMMMEEMM",
        "...BBBBMMMEEMM",
        "...BBBBBMMMMMM",
        "..BBBBBBBMMMMM",
        "..BBBBBBBBMMMM",
        "..BBBBBBBBBBBB",
        ".BBBBBBBBBBBBB",
        ".BBBBBBBBBBBBB",
        ".BBBBBBBBBBBBB",
        "BBBBBBBBBBBBBB",
        "BBBBBBBBBBBBBB",
        "BBBBBBBBBBBBBB",
        "BB.BBB.BBBB.BB",
        "B...BB..BB...B",
        "......B...B...",
    ],
    "dragon": [
        "..H...........",
        ".HH...........",
        ".HH......BBBBB",
        "..HH...BBBBBBB",
        "..HHHBBBBBBBBB",
        "...HBBBBBBBBBB",
        "....BBBBBBBBBB",
        "....BBBEEEBBBB",
        "....BBBBEEBBBB",
        "..WWBBBBBBBBBB",
        ".WWWBBBBBBBBBB",
        ".WWW.BBBBBBBBB",
        ".WW...BBBBBBBB",
        ".W.....BBBBBBB",
        "......BBBBBMBB",
        "......BBBBBBBB",
        "......BBBMMMMM",
        "......BBTMTMTM",
        ".......BBBBBBB",
        "........BBBBBB",
        ".FF..F...BBBBB",
        "FFFFFFFF.BBBBB",
    ],    "slime": [
        "......BBBBBB",
        "....BBBBBBBB",
        "...BWBBBBBBB",
        "..BBWBBBBBBB",
        "..BBBBEEBBBB",
        ".BBBBBEEBBBB",
        ".BBBBBBBBBBB",
        ".BBBBBBBBBBB",
        "BBBBBBBBBMMM",
        "BBBBBBBBBMMM",
        "BBBBBBBBBBBB",
        "BBBBBBBBBBBB",
        "BBBBBBBBBBBB",
        "BBB.BBBBBBBB",
        "B...BB.BBBBB",
        "........B.BB",
    ],
    # The hand-drawn default: GitHub Actions' own merchant, pack mule and all.
    "merchant": [
        "......HHHH",
        "....HHHHHH",
        "..HHHHHHHH",
        "HHHHHHHHHH",
        "....SSSSSS",
        "....SSESSS",
        "....SSSSSS",
        "...WWWWWWW",
        "..WWWWWWWW",
        "HHBWWWWWWW",
        "HHBBBBGGBB",
        "HHBBBBGGBB",
        "HHBBBBBBBB",
        ".HBBBBBBBB",
        ".HBBBBBBBB",
        ".HHB....BB",
    ],
    # The old man in the cave who hands a hero their first weapon: white beard, arms held out to the sides with a
    # red cloak draped from them, and a ball of flame floating well clear of him on each side.
    "elder": [
        "..........WWWW",
        "..........WWWW",
        ".F.......WSSSS",
        ".F.......WSSSS",
        "FFF......WSESS",
        "FFF......WSESS",
        "FYF......WWWWW",
        "FYF......WWWWW",
        ".....SRRRRWWWW",
        ".....SRRRRWWWW",
        "......RRRRRRRR",
        "......RRRRRRRR",
        "......RRRRRRRR",
        "......RRRRRRRR",
        "......RRRRRRRR",
        "......RRRRRRRR",
    ],
    "mimic": [
        "....BBBBBBBBBBBB",
        "...BBBBBBBBBBBBB",
        "..BBBBBBBBBBBBBB",
        "..BBBBBBBBBBBBBB",
        "..BBBBBBBBBBBBBB",
        "..BTBBTBBTBBTBBT",
        "..MMMMMMMMMMMMMM",
        "..MMMMEEMMMMMMMM",
        "..MMMMEEMMMMMMMM",
        "..TMTMTMTMTMTMTM",
        "..BBBBBBBBBBBBBB",
        "..BBBBBBBBBBBBLL",
        "..BBBBBBBBBBBBLL",
        "..BBBBBBBBBBBBBB",
    ],
    "chest": [
        "....BBBBBBBBBBBB",
        "...BBBBBBBBBBBBB",
        "..BBBGGBBBBBBBBB",
        "..BBBGGBBBBBBBBB",
        "..GGGGGGGGGGGGGG",
        "..BBBGGBBBBBBLLL",
        "..BBBGGBBBBBBLMM",
        "..BBBGGBBBBBBLLL",
        "..GGGGGGGGGGGGGG",
        "..BBBGGBBBBBBBBB",
        "..BBBGGBBBBBBBBB",
        "..GGGGGGGGGGGGGG",
    ],
    "trap": [
        "...L...L...L",
        "...L...L...L",
        "..LL..LL..LL",
        "..LL..LL..LL",
        "BMLLMMLLMMLL",
        "BMLLMMLLMMLL",
        "BMMMMMMMMMMM",
        "BMMMMMMMMMMM",
        "BBBBBBBBBBBB",
        "BBBBBBBBBBBB",
        "BBMBBBBBMBBB",
        "BBMBBBBBMBBB",
    ],}

# region ramps, dark -> bright (xterm-256 colour numbers)
_METAL = [238, 241, 244, 247, 250, 253]
_BONE = [58, 101, 144, 187, 230, 231]
_VOID = [232, 233, 234, 235, 236, 237]
_TEETH = [248, 250, 252, 255, 255, 255]
_FLAME = [88, 124, 160, 202, 208, 220]

MONSTER_RAMPS = {
    "goblin": {"B": [22, 28, 34, 40, 46, 83], "b": [58, 100, 142, 148, 154, 190], "eye": 226},
    "wraith": {"B": [17, 18, 24, 31, 38, 81], "eye": 51},
    "dragon": {"B": [52, 88, 124, 160, 196, 209], "W": [53, 89, 90, 126, 162, 168], "eye": 214},
    "mimic": {"B": [94, 130, 136, 172, 178, 220], "eye": 226},
    "merchant": {
        "B": [53, 54, 90, 96, 132, 175],
        "H": [52, 94, 130, 130, 136, 137],
        "S": [137, 173, 180, 216, 223, 224],
        "W": [250, 252, 254, 255, 255, 255],
        "G": [94, 136, 178, 220, 226, 229],
        "eye": 232,
    },
    "elder": {"Y": [226, 226, 227, 227, 228, 229], "F": [202, 208, 208, 214, 214, 220], "R": [52, 88, 124, 160, 196, 209], "W": [250, 252, 254, 255, 255, 255], "S": [137, 173, 180, 216, 223, 224], "eye": 232},
    "slime": {"B": [23, 30, 37, 44, 50, 86], "W": [109, 152, 195, 231, 231, 231], "eye": 232},
    "chest": {"B": [94, 94, 130, 130, 136, 136], "G": [94, 136, 178, 220, 226, 229], "eye": 226},
    "trap": {"B": [235, 238, 241, 244, 247, 250], "eye": 196},
}
_SHARED = {"H": _BONE, "M": _VOID, "T": _TEETH, "L": _METAL, "F": _FLAME}
_BAYER = [[0.0, 0.5], [0.75, 0.25]]


def _mirror(rows: list[str]) -> list[str]:
    half = max(len(r) for r in rows)
    full = []
    for r in rows:
        r = r.ljust(half, r[-1])
        full.append(r + r[::-1])
    if len(full) % 2:
        full.append("." * len(full[0]))
    return full


def _level(grid: list[str], x: int, y: int, n: int, dither: float, rim: float) -> int:
    h, w = len(grid), len(grid[0])
    t = 0.5 * (1 - x / w) + 0.5 * (1 - y / h)
    lv = t * (n - 1) + (_BAYER[y % 2][x % 2] - 0.5) * dither
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < w and 0 <= ny < h) or grid[ny][nx] == ".":
            lv -= rim
            break
    return max(0, min(n - 1, round(lv)))


def _pixel(ramps: dict, grid: list[str], x: int, y: int, dither: float = 0.9, rim: float = 1.6) -> Px | None:
    """The lit pixel at (x, y), or None if empty."""
    ch = grid[y][x]
    if ch == ".":
        return None
    if ch == "E":
        return Px(ramps["eye"], 5, ch)
    ramp = ramps.get(ch) or _SHARED.get(ch) or ramps["B"]
    lv = _level(grid, x, y, len(ramp), dither, rim)
    return Px(ramp[lv], lv, ch)


def sprite(key: str, color: bool | Backend, tier: int = 0) -> str:
    return render(SPRITES[key], tier_ramps(key, tier), color)


# Palette swaps for the Senior (1) and Skip Level (2) tiers; only listed regions change.
MONSTER_TIERS = {
    "goblin": {
        1: {"B": [17, 18, 24, 27, 33, 75], "b": [60, 66, 102, 108, 144, 150]},
        2: {"B": [53, 54, 90, 96, 132, 175], "b": [89, 125, 132, 168, 175, 218], "eye": 196},
    },
    "wraith": {
        1: {"B": [53, 54, 90, 96, 132, 175], "eye": 226},
        2: {"B": [236, 240, 244, 248, 252, 255], "eye": 196},
    },
    "slime": {
        1: {"B": [89, 125, 162, 168, 205, 218]},
        2: {"B": [17, 53, 54, 91, 97, 133], "W": [97, 133, 139, 175, 218, 225], "eye": 196},
    },
    # the mimic keeps its colours; only the eyes get angrier
    "mimic": {1: {"eye": 208}, 2: {"eye": 196}},
    "dragon": {
        1: {"B": [17, 24, 31, 38, 44, 87]},
        2: {"B": [232, 234, 236, 238, 240, 244], "W": [52, 88, 124, 160, 196, 202], "eye": 196},
    },
}


def tier_ramps(key: str, tier: int) -> dict:
    return {**MONSTER_RAMPS[key], **MONSTER_TIERS.get(key, {}).get(tier, {})}


def render(half_rows: list[str], ramps: dict, color: bool | Backend, dither: float = 0.9, rim: float = 1.6) -> str:
    """Draw a left-half pixel map (mirrored) through a pixel backend."""
    grid = _mirror(half_rows)
    rows = [[_pixel(ramps, grid, x, y, dither, rim) for x in range(len(grid[0]))] for y in range(len(grid))]
    return "\n".join(backend_for(color).draw(rows))


def shadow(width: int, color: bool | Backend) -> str:
    """A soft ground shadow `width` pixels wide and two pixels tall, darkest in the middle."""
    w = max(width, 8)
    c = (w - 1) / 2
    top_row: list[Px | None] = []
    bottom_row: list[Px | None] = []
    for x in range(w):
        d = abs(x - c) / c  # always <= 1, so every column has a bottom pixel
        top_row.append(Px(236 if d < 0.45 else 238, kind="S") if d <= 0.7 else None)
        bottom_row.append(Px(234 if d < 0.5 else 236 if d < 0.8 else 238, kind="S"))
    return "\n".join(backend_for(color).draw([top_row, bottom_row], plain="block"))


# Item icons: small symmetric sprites, one per loot category (half-width 6; mirrored to 12 wide). Each
# feature is drawn two rows tall, because the one-colour-per-cell backend merges every pair of rows.
def _pairs(*rows: str) -> list[str]:
    return [r for row in rows for r in (row, row)]


ITEM_SPRITES = {
    "dagger": _pairs(".....L", "....LL", "....LL", "..GGGG", "....HH"),
    "staff": _pairs("....JJ", "...JJJ", "...GGG", ".....H", ".....H"),
    "mallet": _pairs(".OOOOO", ".OOOOO", ".....H", ".....H", "....PP"),
    "bludgeon": _pairs("...LLL", "..LLJL", "...LLL", ".....H", "....PP"),
    "ring": _pairs("....JJ", "..GGGG", ".GG...", ".GG...", "..GGGG"),
    "crown": _pairs("G..G.G", "GGGGGG", "GJGGJG", "GGGGGG", "......"),
    "cloak": _pairs("..CCCC", ".CCCCG", "CCCCCC", "CCCCCC", "CC.CC."),
    "locket": _pairs(".G....", "..GG..", "....GG", "..GJJJ", "...GGG"),
    "charm": _pairs("...YYY", "..YYEY", "...YOO", ".YYYYY", "YYYYYY"),
}
_GOLD = [94, 136, 178, 220, 226, 229]
ITEM_RAMPS = {
    "B": _GOLD,
    "G": _GOLD,
    "P": _GOLD,
    "H": [52, 94, 130, 130, 136, 136],
    "J": [24, 31, 38, 45, 51, 123],
    "C": [53, 54, 90, 96, 132, 175],
    "Y": [136, 178, 178, 220, 226, 227],
    "O": [130, 166, 172, 208, 214, 214],
    "eye": 233,
}


def item_icon(category: str, color: bool | Backend) -> list[str]:
    rows = ITEM_SPRITES.get(category, ITEM_SPRITES["charm"])
    return render(rows, ITEM_RAMPS, color, dither=0.3, rim=0.6).split("\n")


# Every other bot gets its own merchant, generated from its name. They always wear a hat and a
# beard, so they never look like the abstract portraits players get.
DEFAULT_MERCHANT_BOTS = {"github-actions[bot]", "github-actions"}
_HATS = [
    ["......HHHH", "....HHHHHH", "..HHHHHHHH", "HHHHHHHHHH"],  # wide brim
    ["........HH", "......HHHH", "....HHHHHH", "..HHHHHHHH"],  # pointed
    ["......HHHH", "....HHHHHH", "...HHHHHHH", "...HHHHHHH"],  # cap
]
_NO_PACK = ["..BWWWWWWW", ".BBBBBGGBB", ".BBBBBGGBB", ".BBBBBBBBB", ".BBBBBBBBB", ".BBBBBBBBB", ".HHB....BB"]
_ROBES = [
    [22, 28, 34, 40, 46, 83],      # green
    [17, 18, 24, 31, 38, 81],      # blue
    [52, 88, 124, 160, 196, 209],  # red
    [23, 30, 37, 44, 50, 86],      # teal
    [94, 130, 166, 172, 208, 214], # orange
    [89, 125, 162, 168, 205, 218], # pink
]
_SKINS = [
    [137, 173, 180, 216, 223, 224],
    [94, 130, 137, 173, 180, 181],
    [52, 88, 94, 95, 131, 137],
    [52, 52, 88, 94, 95, 131],
    [235, 237, 52, 95, 131, 137],  # the deepest the 256-colour cube gets: no real dark brown exists in it
]
_BEARDS = [
    [250, 252, 254, 255, 255, 255],
    [240, 243, 246, 249, 252, 254],
    [52, 94, 130, 130, 136, 137],
    [130, 166, 172, 208, 214, 215],
]
_HAT_COLOURS = [
    [52, 94, 130, 130, 136, 137],
    [22, 28, 34, 40, 46, 83],
    [88, 124, 160, 196, 202, 209],
    [17, 18, 24, 31, 38, 81],
]


_HAT_NAMES = ["wide-brim hat", "pointed hat", "cap"]
_ROBE_NAMES = ["green", "blue", "red", "teal", "orange", "pink"]
_BEARD_NAMES = ["white", "grey", "brown", "ginger"]
_HAT_COLOUR_NAMES = ["brown", "green", "red", "blue"]


def _parts(bot: str) -> tuple[int, int, int, int, int, int]:
    import hashlib

    d = hashlib.sha256(f"npc|{bot.strip().lower()}".encode()).digest()
    return (d[0] % len(_HATS), d[1] % len(_ROBES), d[2] % len(_SKINS), d[3] % len(_BEARDS), d[4] % 2, d[5] % len(_HAT_COLOURS))


def merchant_look(bot: str) -> tuple[list[str], dict]:
    """(half-width rows, ramps) for the traveling merchant a given bot sends."""
    if bot.strip().lower() in DEFAULT_MERCHANT_BOTS:
        return SPRITES["merchant"], MONSTER_RAMPS["merchant"]
    hat, robe, skin, beard, no_pack, hat_colour = _parts(bot)
    rows = list(SPRITES["merchant"])
    rows[0:4] = _HATS[hat]
    if no_pack:
        rows[9:16] = _NO_PACK
    ramps = {
        **MONSTER_RAMPS["merchant"],
        "B": _ROBES[robe],
        "S": _SKINS[skin],
        "W": _BEARDS[beard],
        "H": _HAT_COLOURS[hat_colour],
    }
    return rows, ramps


def gift_sprite(color: bool | Backend) -> str:
    """The old man who gives an empty-handed hero a weapon, instead of the merchant's usual look."""
    return render(SPRITES["elder"], MONSTER_RAMPS["elder"], color)


def merchant_describe(bot: str) -> str:
    """The look in words, for the lore tables."""
    if bot.strip().lower() in DEFAULT_MERCHANT_BOTS:
        return "hand-drawn: wide-brim hat, white beard, purple robe, pack on both sides"
    hat, robe, _skin, beard, no_pack, hat_colour = _parts(bot)
    pack = "no pack" if no_pack else "pack on both sides"
    return f"{_HAT_COLOUR_NAMES[hat_colour]} {_HAT_NAMES[hat]}, {_BEARD_NAMES[beard]} beard, {_ROBE_NAMES[robe]} robe, {pack}"


def merchant_sprite(bot: str, color: bool | Backend) -> str:
    rows, ramps = merchant_look(bot)
    return render(rows, ramps, color)
