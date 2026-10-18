"""The traveling merchant: what bot runs do instead of playing.

Bots (the Actions bot, Dependabot, ...) are not heroes. Almost always their run
does nothing, but now and then a merchant bumps into a random hero and buys some of
the things in their bag (never what they have equipped) for 'kens. A hero with nothing at all gets a gift
instead: a basic weapon for their class.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

from . import items
from .state import Character, Store, seed_int

MERCHANT_ODDS = 0.05
DIE = 20
STARTER_WEAPON = {"Fighter": "Squeaky Mallet [common]", "Rogue": "Rusty Dagger [common]", "Wizard": "Intern's Staff [common]"}


@dataclass
class Visit:
    hero: str
    sold: list[tuple[str, int]]  # (item label, 'kens paid)
    kens_before: int
    gift: str = ""  # the weapon given to a hero with empty hands, instead of a sale

    @property
    def total(self) -> int:
        return sum(price for _, price in self.sold)


@dataclass
class Meeting:
    """A bot run's d20: the roll, what it needed, and the sale if the merchant turned up and found a buyer."""

    roll: int
    need: int
    found: tuple[Character, Visit] | None = None

    @property
    def summoned(self) -> bool:
        return self.roll >= self.need


def odds() -> float:
    try:
        return float(os.environ.get("QUESTOPS_MERCHANT_ODDS", MERCHANT_ODDS))
    except ValueError:
        return MERCHANT_ODDS


def threshold(chance: float) -> int:
    """The lowest d20 roll that summons the merchant: a natural 20 for 5%, any roll for 100%, none for 0%."""
    if chance >= 1:
        return 1
    if chance <= 0:
        return DIE + 1
    return DIE + 1 - max(round(chance * DIE), 1)


def forced_roll() -> int | None:
    """`QUESTOPS_MERCHANT_ROLL` fixes the d20 (a test hook, so CI can show a natural 20)."""
    try:
        roll = int(os.environ.get("QUESTOPS_MERCHANT_ROLL", ""))
    except ValueError:
        return None
    return min(max(roll, 1), DIE)


def visit(store: Store, key: str, chance: float | None = None) -> Meeting:
    """Roll a d20 and maybe sell some of one hero's bag. The roll is seeded by the commit or run,
    so re-running the same bot workflow gives the same answer."""
    need = threshold(odds() if chance is None else chance)
    rng = random.Random(seed_int("merchant", key)) if key else random.Random()
    roll = rng.randint(1, DIE)
    meeting = Meeting(forced_roll() or roll, need)
    if not meeting.summoned:
        return meeting
    # A hero is a customer with something in the bag, or a gift with nothing on them at all.
    heroes = sorted((c for c in store.all_characters() if c.inventory or (c.cls in STARTER_WEAPON and not (c.main_hand or c.accessory))), key=lambda c: c.name)
    if not heroes:
        return meeting
    ch = rng.choice(heroes)
    if not (ch.inventory or ch.main_hand or ch.accessory):
        ch.main_hand = STARTER_WEAPON[ch.cls]
        meeting.found = (ch, Visit(hero=ch.name, sold=[], kens_before=ch.kens, gift=ch.main_hand))
        return meeting
    count = rng.randint(1, min(3, len(ch.inventory)))
    picked = sorted(rng.sample(range(len(ch.inventory)), count), reverse=True)
    sold = []
    for i in picked:
        item = ch.inventory.pop(i)
        sold.append((item, items.sell_price(item)))
    sold.reverse()
    v = Visit(hero=ch.name, sold=sold, kens_before=ch.kens)
    ch.kens += v.total
    meeting.found = (ch, v)
    return meeting
