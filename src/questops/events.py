"""Typed encounter events: what a transcript is made of.

The engine records them; the terminal transcript and the job summary decide how
(and whether) to show each one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Art:
    """A scene prop; the terminal draws its sprite, markdown skips it."""

    key: str
    tier: int = 0

    text = ""


@dataclass(frozen=True)
class Narration:
    text: str


@dataclass(frozen=True)
class Round:
    """One exchange: the hero's move, then the foe's reply."""

    number: int
    hero: str
    foe: str

    @property
    def text(self) -> str:
        return f"  R{self.number}: {self.hero}. {self.foe}."


@dataclass(frozen=True)
class Retreat:
    """Bookkeeping after a loss; only meaningful when the run is saved."""

    lost: int
    hero: str
    streak: int = 0

    @property
    def text(self) -> str:
        loss = f", dropping {self.lost:,} 'kens" if self.lost else ""
        return f"{self.hero} retreats{loss}." + (" The streak is broken." if self.streak else "")


Event = Art | Narration | Round | Retreat
