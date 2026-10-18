"""One monster fight: three rounds, with fate deciding the last.

A win always ends in a finishing blow on round 3 and a loss always ends in being overwhelmed;
everything in between (spells, quirks, gear effects) is the story.
"""

from __future__ import annotations

import random
from typing import NamedTuple

from . import items, spells
from .events import Event, Narration, Round
from .state import Character

HOTFIX_BACKFIRE = 0.12  # a Hotfix is shipped without review: this often it hurts the wielder
REGEX_MISFIRE = 1 / 6  # the Staff of Regex sometimes matches too much
WEARY_ODDS = 0.5  # Jade sometimes leaves the foe Weary (flavour only)
ROUNDS = 3  # fate decides the last one

MORPHS = [i for i in items.ITEMS if i.slot == "weapon" and i.category != "staff"]


def d(rng: random.Random, n: int) -> int:
    return rng.randint(1, n)


class Swing(NamedTuple):
    hit: bool
    dmg: int
    crit: bool
    fumble: bool


class Fight:
    def __init__(self, ch: Character, rng: random.Random, win: bool, t: list[Event], name: str, mhp: int, mac: int, mhit: int, mdie: int):
        self.ch, self.rng, self.win, self.t, self.name = ch, rng, win, t, name
        self.mhp, self.mac, self.mhit, self.mdie = mhp, mac, mhit, mdie
        self.hp, self.mp = ch.hp_max, ch.mp_max
        main = items.parse(ch.main_hand)[0]
        worn = items.parse(ch.accessory)[0]
        found = items.active_set(ch.main_hand, ch.accessory)
        self.set = found.name if found else ""
        self.main = main
        self.can_cast = ch.caster and items.category(ch.main_hand) == "staff" and bool(ch.main_hand)
        self.regex = main == "Staff of Regex"
        self.merge = main == "Force Merge"
        self.ring = worn == "Ring of Retries"
        self.crown = worn == "Crown of the Main Branch"
        self.cloak = worn == "Cloak of Mild Inconvenience"
        self.locket = worn == "Lockfile Locket"
        self.charm = worn == "Dependabot Charm"
        self.shiv_used = self.merge_used = self.locket_used = self.charm_used = self.weary = False
        self.pending: items.Item | str | None = None
        self.rnd, self.final = 0, False
        self.notes: list[Event] = []

    def hurt_self(self) -> int:
        dmg = d(self.rng, 6) + self.ch.level // 2 + 1
        self.hp -= dmg
        if self.win:
            self.hp = max(self.hp, 1)
        return dmg

    def ignores_armour(self, weapon: str) -> bool:
        if self.set == "Zero Trust":
            return True
        if weapon == "Sudo Shiv" and not self.shiv_used:
            self.shiv_used = True
            return True
        return False

    def lands(self, roll: int, ignore: bool, mod: int) -> bool:
        return roll == 20 or ignore or (roll != 1 and roll + mod >= self.mac)

    def swing(self, weapon: str, bonus: int, mod: int, dice: int = 1, extra: int = 0, crit: bool = False) -> Swing:
        rng, ch = self.rng, self.ch
        roll = 20 if (crit or (self.win and self.final)) else d(rng, 20)
        ignore = self.ignores_armour(weapon)
        hit = self.lands(roll, ignore, mod)
        if not hit and self.charm and not self.charm_used:
            self.charm_used = True
            self.notes.append(Narration("  Dependabot bumps the roll."))
            roll = d(rng, 20)
            hit = self.lands(roll, ignore, mod)
        if not hit and self.merge and not self.merge_used:
            self.merge_used = True
            self.notes.append(Narration("  [Force Merge] overrides the failing check."))
            hit = True
        if not hit:
            return Swing(False, 0, False, roll == 1)
        dmg = sum(d(rng, ch.hit_die) for _ in range(dice)) + ch.level // 2 + bonus + extra
        if roll == 20:
            dmg += d(rng, ch.hit_die)
        if self.win and self.final:
            dmg = max(dmg, self.mhp)
        elif not self.win:
            dmg = min(dmg, max(self.mhp - 1, 0))
        self.mhp -= dmg
        return Swing(True, dmg, roll == 20, False)

    @staticmethod
    def describe(sw: Swing, verb: str) -> str:
        if sw.hit:
            return f"{verb} for {sw.dmg}" + (" (critical)" if sw.crit else "")
        return "fumbles" if sw.fumble else "misses"

    def pick_spell(self, forced: bool) -> spells.Spell | None:
        discount = spells.STAFF_DISCOUNT if self.regex else 0
        pool = [spells.BY_NAME["Jade"]] if (self.final or forced) else spells.unlocked(self.ch.level)
        pool = [s for s in pool if spells.cost(s, discount) <= self.mp]
        if not pool:
            return None
        spell = pool[0] if (self.final or forced) else self.rng.choice(pool)
        self.mp -= spells.cost(spell, discount)
        return spell

    def hero_turn(self) -> tuple[str, str]:
        """The hero's move: its text and the shield it raises for the foe's reply."""
        ch, rng = self.ch, self.rng
        pending, self.pending = self.pending, None
        morph = pending if isinstance(pending, items.Item) else None
        weapon, bonus = (morph.name, morph.bonus) if morph else (self.main, ch.weapon_bonus)
        if morph:
            self.notes.append(Narration(f"  The [{morph.name}] reverts to the staff."))
        spell = self.pick_spell(pending == "precommit") if self.can_cast and not morph else None
        mod = ch.gray + (1 if self.crown else 0) + (1 if self.set == "Pair Programming" and self.rnd == 1 else 0)
        if self.ring and not self.final and self.set != "Retry Loop":
            mod -= 2
        misfire = ""
        if spell and self.regex and rng.random() < REGEX_MISFIRE:
            if self.set == "Dependency Hell":
                misfire = ", but the lockfile pins it and nothing extra matches"
            else:
                misfire = f", but it matches too much and hits {ch.name} for {self.hurt_self()}"
        name = spell.name if spell else ""
        shield = ""
        if weapon == "Local Bludgeon":
            # 25% one-hit KO, otherwise the swing backfires. Fate still decides the fight:
            # a win ends in a KO by the last round, a loss never gets one.
            if self.win and (self.final or rng.random() < 0.25):
                mine = f"{ch.name} swings the [Local Bludgeon]. It works on their machine too. KO"
                self.mhp = 0
            else:
                mine = f"{ch.name} swings the [Local Bludgeon]. It backfires for {self.hurt_self()}"
        elif weapon == "Hotfix" and not (self.win and self.final) and rng.random() < HOTFIX_BACKFIRE:
            if self.set == "Hotfix Friday":
                mine = f"{ch.name} swings the [Hotfix]. Nobody reviewed it, and it backfires, but the cloak absorbs it"
            else:
                mine = f"{ch.name} swings the [Hotfix]. Nobody reviewed it, and it backfires for {self.hurt_self()}"
        elif name in ("Confuse", "Hard Block"):
            mine, shield = f"{ch.name} casts {name}", name
        elif name == "Pre-commit":
            self.pending = "precommit"
            mine = f"{ch.name} casts Pre-commit and gathers energy"
        elif name == "Refactor":
            self.pending = rng.choice(MORPHS)
            mine = f"{ch.name} casts Refactor. The staff morphs into the [{self.pending.name}]"
        elif name == "Supply Chain Attack":
            first = self.swing(weapon, bonus, mod)
            parts = [self.describe(first, "hits")]
            if not (self.win and self.mhp <= 0):
                second = self.swing(weapon, bonus, mod, extra=int(first.hit))
                parts.append(self.describe(second, "hits") + (" (+1 chain)" if first.hit and second.hit else ""))
            mine = f"{ch.name} casts Supply Chain Attack: {', then '.join(parts)}"
        else:
            sw = self.swing(weapon, bonus, mod, dice=2 if name == "Zoltraak" else 1, crit=pending == "precommit")
            mine = f"{ch.name} {self.describe(sw, f'casts {name}' if name else 'hits')}"
            if name == "Jade" and sw.hit and rng.random() < WEARY_ODDS and not self.weary:
                self.weary = True
                if self.mhp > 0:
                    self.notes.append(Narration(f"  The {self.name} looks Weary."))
        return mine + misfire, shield

    def foe_turn(self, shield: str) -> str:
        ch, rng, name = self.ch, self.rng, self.name
        doomed = not self.win and self.final
        mroll = 20 if doomed else d(rng, 20)
        if shield == "Confuse" and not doomed:
            return f"{name} stumbles in confusion"
        if shield == "Hard Block" and not doomed:
            return f"{name} strikes, but the ward absorbs it"
        if not (mroll + self.mhit >= ch.ac or mroll == 20):
            return f"{name} misses"
        if not doomed and self.locket and not self.locket_used:
            self.locket_used = True
            return f"{name} strikes first, but the lockfile blocks it"
        if not doomed and self.merge and not self.merge_used:
            self.merge_used = True
            return f"{name} strikes, but [Force Merge] overrides the failing check"
        dmg = d(rng, self.mdie) + (d(rng, self.mdie) if mroll == 20 else 0)
        if self.cloak:
            dmg = max(dmg - 1, 0)
        self.hp -= dmg
        if self.win:
            self.hp = max(self.hp, 1)
        return f"{name} strikes for {dmg}"

    def run(self) -> None:
        ch, t = self.ch, self.t
        for rnd in range(1, ROUNDS + 1):  # pragma: no branch - the final round always breaks out
            self.rnd, self.final = rnd, rnd == ROUNDS
            self.notes = []
            if self.ring and self.win and self.final:
                t.append(Narration("  The [Ring of Retries] hums and rewinds the fight. Round 3, until it goes right."))
            mine, shield = self.hero_turn()
            if self.win and self.mhp <= 0:
                t.append(Round(rnd, mine, f"The {self.name} collapses"))
                t.extend(self.notes)
                break
            t.append(Round(rnd, mine, self.foe_turn(shield)))
            t.extend(self.notes)
            if not self.win and (self.hp <= 0 or self.final):
                t.append(Narration(f"  {ch.name} is overwhelmed and drops to the floor..."))
                break
