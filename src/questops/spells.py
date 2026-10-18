"""The spellbook: what a Wizard can cast, unlocked by hero level. Casting needs a staff in the main hand."""

from __future__ import annotations

from typing import NamedTuple


class Spell(NamedTuple):
    name: str
    level: int  # hero level that unlocks it
    mp: int
    effect: str


SPELLS = [
    Spell("Jade", 1, 2, "A plain bolt of damage. About half the time it leaves the foe Weary, which changes nothing."),
    Spell("Confuse", 2, 2, "No damage. The foe stumbles and its reply misses."),
    Spell("Hard Block", 3, 2, "No damage. A ward absorbs the foe's reply."),
    Spell("Refactor", 4, 3, "No attack this round: the staff morphs into a random other weapon. Next round you attack with it, quirks included, then it reverts. Rounds 1-2 only."),
    Spell("Supply Chain Attack", 5, 4, "Two hits in one round. The second hits for +1 per link that landed before it."),
    Spell("Pre-commit", 6, 5, "No attack this round: you gather energy. Next round's attack is a guaranteed critical hit. Rounds 1-2 only."),
    Spell("Zoltraak", 7, 4, "One big hit: about double a normal hit's damage dice."),
]
BY_NAME = {s.name: s for s in SPELLS}
STAFF_DISCOUNT = 1  # the Staff of Regex
CHEAPEST = 1


def unlocked(level: int) -> list[Spell]:
    return [s for s in SPELLS if s.level <= level]


def cost(spell: Spell, discount: int = 0) -> int:
    return max(spell.mp - discount, CHEAPEST)
