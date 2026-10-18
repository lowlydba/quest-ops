"""Hero avatars.

A hero's portrait is a small face drawn from the hero's class and a hash of the hero's name, so the
same name always gets the same face: a Fighter in a helm, a Rogue in a hood, a Wizard in a pointed hat
with a beard. Skin, eyes, hair and the colours of the headgear and clothes come from the hash.

Every feature is two rows tall, because the one-colour-per-cell backend merges each pair of rows;
the portrait is 12 pixels wide (mirrored from 6) and 12 tall.
"""

from __future__ import annotations

import hashlib

from .sprites import _SKINS

ROWS, HALF = 12, 6

# Six-step ramps (dark to bright, xterm-256) for headgear and clothes.
HUES = [
    [22, 28, 34, 40, 46, 83],      # green
    [17, 18, 24, 31, 38, 81],      # blue
    [53, 54, 90, 96, 132, 175],    # purple
    [52, 88, 124, 160, 196, 209],  # red
    [94, 130, 166, 172, 208, 214], # orange
    [23, 30, 37, 44, 51, 123],     # cyan
    [89, 125, 162, 168, 205, 218], # pink
    [94, 136, 142, 178, 220, 229], # gold
]
HAIRS = [
    [233, 234, 236, 238, 240, 242],      # black
    [52, 94, 130, 130, 136, 137],        # brown
    [136, 178, 184, 220, 226, 229],      # blond
    [88, 124, 160, 166, 208, 214],       # ginger
    [244, 247, 250, 252, 254, 255],      # white
]
EYES = [233, 17, 22, 94]  # black, blue, green, brown


def _pairs(*rows: str) -> list[str]:
    return [r for row in rows for r in (row, row)]


# Each class has two looks (picked by the hash), as six feature rows. S skin, E eye, M mouth or mask,
# L metal, H headgear, K hair and beard, B clothes.
LOOKS = {
    "Fighter": [
        _pairs("..LLLL", ".LLLLL", ".LSESL", ".LSSMM", "LLLSSS", "LLBBBB"),
        _pairs("...HHH", ".LLLLL", ".LSESL", ".LSSMM", "LLLSSS", "LLBBBB"),  # with a plume
    ],
    "Rogue": [
        _pairs("..HHHH", ".HHHHH", ".HSESS", ".HMMMM", "HHBBBB", "HHBBBB"),  # masked
        _pairs("..HHHH", ".HHHHH", ".HSESS", ".HSSMM", "HHBBBB", "HHBBBB"),  # bare-faced
    ],
    "Wizard": [
        _pairs("...HHH", "HHHHHH", ".KSESS", ".KKKKK", "..KKKK", "BBBBBB"),
        _pairs("....HH", "HHHHHH", ".KSESS", ".KKKKK", ".KKKKK", "BBBBBB"),  # a pointed hat and a longer beard
    ],
}


def portrait(name: str, cls: str) -> tuple[list[str], dict]:
    """Return (left-half pixel rows, ramps) for a hero, drawn by sprites.render with the monsters' lighting."""
    d = hashlib.sha256(f"face|{name}".encode()).digest()
    looks = LOOKS.get(cls, LOOKS["Fighter"])
    rows = looks[d[0] % len(looks)]
    clothes = d[1] % len(HUES)
    gear = (clothes + 1 + d[2] % (len(HUES) - 1)) % len(HUES)
    ramps = {
        "S": _SKINS[d[3] % len(_SKINS)],
        "K": HAIRS[d[4] % len(HAIRS)],
        "B": HUES[clothes],
        "H": HUES[gear],
        "eye": EYES[d[5] % len(EYES)],
    }
    return rows, ramps
