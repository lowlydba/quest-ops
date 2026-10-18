"""Encounter generation and resolution.

The workflow outcome is fate: success always ends in victory, failure always
ends in defeat. The dice decide the *story* (damage, loot, close calls).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import items
from .events import Art, Event, Narration, Retreat
from .fight import Fight, d
from .items import ITEMS, RARITY_WEIGHT, label
from .state import Character

# name, art, min_level, hp, ac, to_hit, dmg_die, xp, kens, taunts (base, Senior, Skip Level)
MONSTERS = [
    ("Lint Goblin", "goblin", 1, 14, 11, 4, 6, 50, 12, (
        "Mmm, trailing whitespace.",
        "I wrote half your style guide. The other half is a TODO.",
        "Let's align on tabs versus spaces. Offline. Forever.",
    )),
    ("Cache Slime", "slime", 1, 18, 9, 3, 5, 45, 10, (
        "Never invalidated, always persisted.",
        "I've been warm since the last migration.",
        "Let's circle back once I expire. I never expire.",
    )),
    ("Wraith of the Flaky Test", "wraith", 3, 30, 13, 5, 8, 100, 30, (
        "Pass... or fail... who can say?",
        "Works on my machine. Fails on yours.",
        "Just mark me known-flaky and we'll revisit next quarter.",
    )),
    ("Ancient Wyrm of Legacy Prod", "dragon", 6, 60, 15, 7, 10, 250, 100, (
        "YOU SHALL. NOT. MERGE.",
        "I WAS HERE BEFORE THE MONOREPO.",
        "PER MY LAST EMAIL: YOU SHALL. NOT. MERGE.",
    )),
]

# Higher tiers are palette-swapped, tougher versions of the same foe.
# prefix, HP multiplier, reward multiplier, to-hit bonus, unlocks at hero level
TIERS = [
    ("", 1.0, 1.0, 0, 1),
    ("Senior ", 1.5, 1.5, 1, 5),
    ("Skip Level ", 2.2, 2.2, 2, 10),
]


def tier_weights(level: int) -> list[int]:
    """Odds of meeting a base, Senior or Skip Level foe at a given hero level."""
    if level >= TIERS[2][4]:
        return [40, 35, 25]
    if level >= TIERS[1][4]:
        return [65, 35, 0]
    return [100, 0, 0]


KINDS = [("combat", 60), ("treasure", 20), ("trap", 20)]
# A passing run is mostly a monster fight. Chests are sure wins; traps can still get you.
PASS_KIND_WEIGHTS = {"combat": 70, "treasure": 15, "trap": 15}
FAIL_KIND_WEIGHTS = {"combat": 60, "treasure": 20, "trap": 20}
WIN_ODDS = 0.9  # a passing run still has to win its monster fight
TRAP_WIN_ODDS = 0.8  # ...and still has to dodge the trap

@dataclass
class Result:
    kind: str
    title: str
    success: bool
    transcript: list[Event] = field(default_factory=list)
    xp: int = 0
    kens: int = 0
    loot: str = ""
    loot_action: str = ""  # 'equipped', 'bag' or 'sold' (a spare of something already owned)
    replaced: str = ""  # what the loot pushed out of its slot, when it was equipped
    levels: list[int] = field(default_factory=list)
    new_achievements: list[str] = field(default_factory=list)
    foe: str = ""
    tier: int = 0
    prior_losing: int = 0
    scene: str = ""  # the backdrop a monster is drawn in (scenes.SCENES); empty draws it bare

    @property
    def lines(self) -> list[str]:
        """The story as text, art omitted."""
        return [e.text for e in self.transcript if not isinstance(e, Art)]

def roll_loot(rng: random.Random, ch: Character, bonus: int = 0) -> str:
    """Rarer finds get likelier with level; weapons of other classes turn up less often."""
    weights = []
    for it in ITEMS:
        w = RARITY_WEIGHT[it.rarity] + (bonus if it.rarity != "common" else 0)
        weights.append(w if items.usable(label(it.name, it.rarity), ch.cls) else max(w // 5, 1))
    it = rng.choices(ITEMS, weights=weights)[0]
    return label(it.name, it.rarity)


def pick_kind(rng: random.Random, forced: str | None, passed: bool = True) -> str:
    if forced and forced != "random":
        return forced
    weights = PASS_KIND_WEIGHTS if passed else FAIL_KIND_WEIGHTS
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _combat(ch: Character, rng: random.Random, win: bool, r: Result) -> None:
    pool = [m for m in MONSTERS if m[2] <= ch.level]
    # Every eligible foe can appear, with the tougher ones a little likelier.
    mon = rng.choices(pool, weights=range(1, len(pool) + 1))[0]
    base, artkey, _, mhp, mac, mhit, mdie, mxp, mkens, taunts = mon
    tier = rng.choices(range(len(TIERS)), weights=tier_weights(ch.level))[0]
    prefix, hp_x, reward_x, bonus, _unlock = TIERS[tier]
    name = prefix + base
    mhp, mxp, mkens = round(mhp * hp_x), round(mxp * reward_x), round(mkens * reward_x)
    mac, mhit = mac + bonus, mhit + bonus
    r.foe, r.tier = name, tier
    t = r.transcript
    t.append(Art(artkey, tier))
    t.append(Narration(f"A wild {name} appears! ({mhp} HP)"))
    t.append(Narration(f'"{taunts[tier]}"'))
    wielding = f"[{ch.wielding}]" if ch.main_hand else ch.wielding
    t.append(Narration(f"{ch.name} the {ch.cls} readies their {wielding}. ({ch.hp_max} HP, {ch.mp_max} MP, {ch.gray} GRAY)"))
    Fight(ch, rng, win, t, name, mhp, mac, mhit, mdie).run()
    r.success = win
    if win:
        r.xp, r.kens = mxp, mkens + d(rng, 6)
        ch.kills[name] = ch.kills.get(name, 0) + 1
        if rng.random() < 0.45:
            r.loot = roll_loot(rng, ch, ch.level)
        r.title = f"Slew the {name}"
    else:
        r.title = f"Defeated by the {name}"


def _treasure(ch: Character, rng: random.Random, win: bool, r: Result) -> None:
    t = r.transcript
    if win:
        t.append(Art("chest"))
        t.append(Narration("A suspiciously well-lit chest sits in the corridor."))
        roll = d(rng, 20)
        t.append(Narration(f"{ch.name} picks the lock ({roll}+{ch.gray}). *click*"))
        r.xp, r.kens = 60, 20 + d(rng, 30)
        r.loot = roll_loot(rng, ch, ch.level + 5)
        t.append(Narration(f"Inside: {r.kens} 'kens and a [{items.parse(r.loot)[0]}]! The 'kens go in the pile with the rest."))
        r.title = "Looted a treasure chest"
    else:  # the mimic is the whole chest, so its sprite stands in for it
        tier = rng.choices(range(len(TIERS)), weights=tier_weights(ch.level))[0]
        name = TIERS[tier][0] + "Mimic"
        r.tier = tier
        t.append(Art("mimic", tier))
        purse = ", which held 'kens nobody knew how to spend" if ch.kens else ""
        t.append(Narration(f"A suspiciously well-lit chest sits in the corridor. It's a {name.upper()}! Teeth everywhere. It chews through {ch.name}'s coin purse{purse}."))
        r.title = "Bitten by a mimic" if tier == 0 else f"Bitten by a {name}"
    r.success = win


def _trap(ch: Character, rng: random.Random, win: bool, r: Result) -> None:
    t = r.transcript
    t.append(Art("trap"))
    t.append(Narration(f"*click* The floor tile beneath {ch.name} was not a floor tile."))
    if win:
        t.append(Narration(f"{ch.name} dives clear and disarms it ({d(rng, 20)}+{ch.gray}). Pressure plates hate this trick."))
        r.xp, r.kens = 55, 10 + d(rng, 15)
        t.append(Narration(f"Salvaged {r.kens} 'kens worth of springs."))
        r.title = "Disarmed a trap"
    else:
        t.append(Narration(f"Darts whistle. {ch.name} takes {d(rng, 8) + 2} damage and a lot of embarrassment."))
        r.title = "Triggered a trap"
    r.success = win


_KIND_FN = {"combat": _combat, "treasure": _treasure, "trap": _trap}

def _slain(c: Character, base: str) -> int:
    """Kills of a foe across all tiers."""
    return sum(v for k, v in c.kills.items() if k.endswith(base))


ACHIEVEMENTS = {
    "back-in-green": ("Back in the Green (win after 3 losses)", lambda c, r: r.success and r.prior_losing >= 3),
    "journeyman": ("Journeyman (GRAY 5)", lambda c, r: c.natural_gray >= 5),
    "greybeard": ("Greybeard (GRAY 10)", lambda c, r: c.natural_gray >= 10),
    "regular": ("Regular (100 wins)", lambda c, r: c.wins >= 100),
    "veteran": ("Veteran (1,000 wins)", lambda c, r: c.wins >= 1000),
    "unbroken": ("Unbroken (25 wins in a row)", lambda c, r: c.streak >= 25),
    "century": ("Century (100 wins in a row)", lambda c, r: c.streak >= 100),
    "lint-roller": ("Lint Roller (10 Lint Goblins)", lambda c, r: _slain(c, "Lint Goblin") >= 10),
    "flake-whisperer": ("Flake Whisperer (10 Wraiths)", lambda c, r: _slain(c, "Wraith of the Flaky Test") >= 10),
    "prod-survivor": ("Prod Survivor (slew the Wyrm)", lambda c, r: _slain(c, "Ancient Wyrm of Legacy Prod") >= 1),
    "promotion": ("Promotion (slew a Senior foe)", lambda c, r: any(k.startswith("Senior ") for k in c.kills)),
    "skip-level": ("Skip Level Meeting (slew a Skip Level foe)", lambda c, r: any(k.startswith("Skip Level ") for k in c.kills)),
    "magpie": ("Magpie (owned every item)", lambda c, r: {items.parse(i)[0] for i in [c.main_hand, c.accessory, *c.inventory] if i} >= {i.name for i in ITEMS}),
    "crowned": ("Crowned (equipped the Crown)", lambda c, r: c.accessory.startswith("Crown of the Main Branch")),
    "unpaid-vacation": ("Unpaid Vacation (10,000 encounters)", lambda c, r: c.encounters >= 10000),
}


def run_encounter(ch: Character, success: bool, rng: random.Random, kind: str | None = None, win_odds: float = WIN_ODDS, trap_odds: float = TRAP_WIN_ODDS) -> Result:
    """`success` is how the workflow went. A failed run is always a loss. A passing run is
    a sure win in a chest, a trap dodged with `trap_odds`, and a monster fight won with `win_odds` (always, with the Ring of Retries).
    The transcript always records the loss bookkeeping (`Retreat`); presenting a run that is never saved is up to the caller."""
    k = pick_kind(rng, kind, success)
    win = success
    if success and k == "combat" and not ch.accessory.startswith("Ring of Retries"):
        win = rng.random() < win_odds
    elif success and k == "trap":
        win = rng.random() < trap_odds
    r = Result(kind=k, title="", success=win)
    r.prior_losing = ch.loss_run
    _KIND_FN[k](ch, rng, win, r)

    streak_bonus = min(ch.streak * 10, 50)
    if win:
        r.xp = r.xp * (100 + streak_bonus) // 100
        ch.wins += 1
        ch.streak += 1
        ch.loss_run = 0
        ch.best_streak = max(ch.best_streak, ch.streak)
    else:
        r.xp = 5  # participation trophy
        lost = ch.kens // 10
        ch.kens -= lost
        r.kens = -lost
        r.transcript.append(Retreat(lost, ch.name, ch.streak))
        ch.losses += 1
        ch.loss_run += 1
        ch.streak = 0

    ch.encounters += 1
    ch.kens += max(r.kens, 0)
    if r.loot:
        slot_attr = "main_hand" if items.slot(r.loot) == "weapon" else "accessory"
        before = getattr(ch, slot_attr)
        r.loot_action = ch.pick_up(r.loot)
        r.replaced = before if r.loot_action == "equipped" else ""
        if r.loot_action == "sold":
            price = items.sell_price(r.loot)
            r.kens += price
            r.transcript.append(Narration(f"{ch.name} already has one, so the spare [{items.parse(r.loot)[0]}] goes up on the classifieds and sells in minutes for {price} 'kens."))
    r.levels = ch.grant_xp(r.xp)
    for lv in r.levels:
        r.transcript.append(Narration(f"{ch.name} reaches level {lv}."))
        for prefix, *_, unlock in TIERS[1:]:
            if unlock == lv:
                r.transcript.append(Narration(f"Word gets around: {prefix.strip()} foes can now turn up."))
    ch.last_encounter = r.title

    for key, (label, test) in ACHIEVEMENTS.items():
        if label not in ch.achievements and test(ch, r):
            ch.achievements.append(label)
            r.new_achievements.append(label)
    return r
