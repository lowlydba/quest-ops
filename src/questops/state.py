"""Persistent character state, stored as plain JSON so any CI can sync it."""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import items

CLASSES = {  # name: (damage die, weapon, uses MP for attacks)
    "Fighter": (10, "sword", False),
    "Rogue": (8, "dagger", False),
    "Wizard": (6, "staff", True),
}

# Level-1 values and per-level growth, so classes start differently:
# Fighters are sturdy, Wizards have the mana, Rogues are sharp from the start.
CLASS_STATS = {
    "Fighter": {"hp": (20, 7), "mp": (2, 2), "gray": 0},
    "Rogue": {"hp": (15, 6), "mp": (5, 3), "gray": 2},
    "Wizard": {"hp": (11, 5), "mp": (10, 4), "gray": 1},
}


def slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-.").lower()
    return s or "adventurer"


def seed_int(*parts: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:8], "big")


# Foes that have been renamed, so older saves keep their kill counts.
RENAMED_FOES = {"Ancient Wyrm of Prod": "Ancient Wyrm of Legacy Prod"}


def _renamed(name: str) -> str:
    for old, new in RENAMED_FOES.items():
        if name.endswith(old):
            return name[: -len(old)] + new
    return name


TOH = 10_000  # 'kens in one toh ("toh 'kens", say it out loud)


def money(kens: int, unit: bool = True) -> str:
    """A purse as people read it: 12,345 becomes '1 toh 2,345 'kens'. Only balances roll up, never gains or prices."""
    toh, rest = divmod(kens, TOH)
    suffix = " 'kens" if unit else ""
    if not toh:
        return f"{kens:,}{suffix}"
    return f"{toh:,} toh" + (f" {rest:,}{suffix}" if rest else "")


def xp_for_level(level: int) -> int:
    return int(600 * (level - 1) ** 2.5)


def level_for_xp(xp: int) -> int:
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level


@dataclass
class Character:
    """Passive sheet: HP, MP and GRAY (gray hairs) are all derived from level."""

    name: str
    cls: str = "Fighter"
    level: int = 1
    xp: int = 0
    kens: int = 10
    main_hand: str = ""  # the weapon wielded (class-locked); the best usable one is equipped automatically
    accessory: str = ""  # the accessory worn (any class); likewise the best one
    inventory: list = field(default_factory=list)  # everything else
    titles: list = field(default_factory=list)
    achievements: list = field(default_factory=list)
    encounters: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0
    best_streak: int = 0
    loss_run: int = 0
    kills: dict = field(default_factory=dict)
    last_encounter: str = ""

    @property
    def hp_max(self) -> int:
        base, per = CLASS_STATS[self.cls]["hp"]
        return base + per * (self.level - 1)

    @property
    def mp_max(self) -> int:
        base, per = CLASS_STATS[self.cls]["mp"]
        return base + per * (self.level - 1)

    @property
    def gray(self) -> int:
        """Gray hairs: hard-won seniority. Adds to attack and skill rolls."""
        return self.natural_gray + CLASS_STATS[self.cls]["gray"] + items.gray_bonus(self.accessory)

    @property
    def natural_gray(self) -> int:
        """GRAY earned the hard way, from level alone. Achievements count only this."""
        return 1 + self.level

    @property
    def hit_die(self) -> int:
        return CLASSES[self.cls][0]

    @property
    def wielding(self) -> str:
        """What the hero swings: the equipped weapon, else the class's bare-bones one."""
        return items.parse(self.main_hand)[0] if self.main_hand else CLASSES[self.cls][1]

    @property
    def weapon_bonus(self) -> int:
        return items.bonus(self.main_hand) if self.main_hand else 0

    @property
    def caster(self) -> bool:
        return CLASSES[self.cls][2]

    @property
    def ac(self) -> int:
        return 10 + self.level // 3

    @property
    def next_level_xp(self) -> int:
        return xp_for_level(self.level + 1)

    @classmethod
    def create(cls, name: str) -> "Character":
        rng = random.Random(seed_int("birth", name))
        klass = rng.choice(sorted(CLASSES))
        return cls(name=name, cls=klass)

    def tidy(self) -> None:
        """Re-derive things that depend on rules which may have changed."""
        self.level = level_for_xp(self.xp)
        pool = [i for i in (self.main_hand, self.accessory) if i] + self.inventory
        for slot, attr in (("weapon", "main_hand"), ("accessory", "accessory")):
            fit = [i for i in pool if items.slot(i) == slot and items.usable(i, self.cls)]
            setattr(self, attr, "")
            if fit:
                best = fit[0]
                for it in fit[1:]:
                    if items.better(it, best):
                        best = it
                pool.remove(best)
                setattr(self, attr, best)
        self.inventory = pool

    def pick_up(self, item: str) -> str:
        """Sell a spare of something already owned; equip the item if it beats what is worn in its slot
        (and suits the class), else bag it."""
        if item in (self.main_hand, self.accessory) or item in self.inventory:
            self.kens += items.sell_price(item)
            return "sold"
        attr = "main_hand" if items.slot(item) == "weapon" else "accessory"
        current = getattr(self, attr)
        if items.usable(item, self.cls) and items.better(item, current):
            if current:
                self.inventory.append(current)
            setattr(self, attr, item)
            result = "equipped"
        else:
            self.inventory.append(item)
            result = "bag"
        self.inventory[:] = self.inventory[-30:]
        return result

    def level_up(self) -> None:
        self.level += 1

    def grant_xp(self, amount: int) -> list[int]:
        self.xp += amount
        gained = []
        while self.xp >= xp_for_level(self.level + 1):
            self.level_up()
            gained.append(self.level)
        return gained

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Character":
        d = dict(d)
        d["kills"] = {_renamed(k): v for k, v in d.get("kills", {}).items()}
        legacy = d.pop("equipped", "")  # saves from before weapon/accessory slots
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        ch = cls(**known)
        if legacy:
            ch.inventory = [legacy, *ch.inventory]
        return ch


class Store:
    """Filesystem store: characters/<slug>.json, log/quests.jsonl."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def char_path(self, name: str) -> Path:
        return self.root / "characters" / f"{slug(name)}.json"

    def load(self, name: str) -> Character:
        p = self.char_path(name)
        if p.exists():
            ch = Character.from_dict(json.loads(p.read_text(encoding="utf-8")))
            if ch.cls not in CLASSES:
                ch.cls = Character.create(name).cls
            ch.tidy()
            return ch
        return Character.create(name)

    def save(self, ch: Character) -> None:
        p = self.char_path(ch.name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ch.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def append_log(self, entry: dict) -> None:
        p = self.root / "log" / "quests.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def read_log(self) -> list[dict]:
        p = self.root / "log" / "quests.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

    def all_characters(self) -> list[Character]:
        d = self.root / "characters"
        if not d.exists():
            return []
        return [Character.from_dict(json.loads(f.read_text(encoding="utf-8"))) for f in sorted(d.glob("*.json"))]
