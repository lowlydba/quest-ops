"""Spells, new items and sets, with scripted dice so every branch is deterministic."""

import random

import pytest

from questops import items, spells
from questops.engine import run_encounter
from questops.events import Round
from questops.fight import MORPHS, Fight
from questops.state import Character

JADE, ZOLTRAAK, PRECOMMIT, REFACTOR = (spells.BY_NAME[n] for n in ("Jade", "Zoltraak", "Pre-commit", "Refactor"))
CONFUSE, HARD_BLOCK, SUPPLY = (spells.BY_NAME[n] for n in ("Confuse", "Hard Block", "Supply Chain Attack"))
HARD_RESET = next(i for i in items.ITEMS if i.name == "Hard Reset")
BLUDGEON = next(i for i in items.ITEMS if i.name == "Local Bludgeon")
HOTFIX = next(i for i in items.ITEMS if i.name == "Hotfix")
STAFF = "Intern's Staff [common]"


class Dice:
    """A scripted rng: queued values first, then harmless defaults (a 1, a high float, the first choice)."""

    def __init__(self, ints=(), floats=(), choices=()):
        self.ints, self.floats, self.choices = list(ints), list(floats), list(choices)

    def randint(self, a, b):
        return self.ints.pop(0) if self.ints else a

    def random(self):
        return self.floats.pop(0) if self.floats else 0.99

    def choice(self, seq):
        return self.choices.pop(0) if self.choices else seq[0]


def hero(cls="Wizard", level=7, main="", acc=""):
    return Character(name="Ada", cls=cls, level=level, main_hand=main, accessory=acc)


def fight(ch, dice=None, win=True, mhp=100, mac=10, mhit=0, mdie=6, rnd=1, final=False):
    f = Fight(ch, dice or Dice(), win, [], "Imp", mhp, mac, mhit, mdie)
    f.rnd, f.final = rnd, final
    return f


def notes(f):
    return [n.text.strip() for n in f.notes]


# unlocks, costs, gating


def test_spells_unlock_by_level_with_their_costs():
    assert [s.name for s in spells.unlocked(1)] == ["Jade"]
    assert [s.name for s in spells.unlocked(3)] == ["Jade", "Confuse", "Hard Block"]
    assert [s.name for s in spells.unlocked(7)] == [s.name for s in spells.SPELLS]
    assert [s.level for s in spells.SPELLS] == [1, 2, 3, 4, 5, 6, 7]
    assert [s.mp for s in spells.SPELLS] == [2, 2, 2, 3, 4, 5, 4]
    assert spells.cost(SUPPLY, spells.STAFF_DISCOUNT) == 3 and spells.cost(JADE, spells.STAFF_DISCOUNT) == 1
    assert spells.cost(spells.Spell("Tiny", 1, 1, ""), 1) == 1


def test_only_a_wizard_with_a_staff_can_cast():
    assert fight(hero(main=STAFF)).can_cast
    assert not fight(hero(main="")).can_cast
    assert not fight(hero("Fighter", main="Hard Reset [rare]")).can_cast
    assert not fight(hero("Rogue", main="Hotfix [rare]")).can_cast


def test_pick_spell_rules():
    f = fight(hero(main=STAFF), Dice(choices=[ZOLTRAAK]))
    assert f.pick_spell(False) is ZOLTRAAK and f.mp == f.ch.mp_max - 4
    assert fight(hero(main=STAFF), final=True).pick_spell(False) is JADE  # round 3 is always Jade
    assert fight(hero(main=STAFF)).pick_spell(True) is JADE  # after Pre-commit too
    f = fight(hero(main=STAFF))
    f.mp = 1
    assert f.pick_spell(False) is None
    f = fight(hero(main="Staff of Regex [rare]"))
    f.mp = 1
    assert f.pick_spell(False) is JADE and f.mp == 0  # Regex makes it cost 1


def test_a_low_level_wizard_only_has_what_is_unlocked():
    for seed in range(40):
        for lv, allowed in ((1, {"Jade"}), (3, {"Jade", "Confuse", "Hard Block"})):
            ch = hero(level=lv, main=STAFF)
            r = run_encounter(ch, True, random.Random(seed), "combat")
            cast = {s.name for s in spells.SPELLS for ln in r.lines if f"casts {s.name}" in ln}
            assert cast <= allowed


def test_a_staffless_wizard_never_casts():
    for seed in range(40):
        r = run_encounter(hero(level=7), seed % 2 == 0, random.Random(seed), "combat")
        assert not any("casts" in ln for ln in r.lines)


# spells


def test_zoltraak_rolls_double_dice():
    f = fight(hero(main=STAFF), Dice(ints=[15, 3, 4], choices=[ZOLTRAAK]))
    mine, shield = f.hero_turn()
    assert mine == "Ada casts Zoltraak for 10" and f.mhp == 90 and not shield


def test_jade_may_leave_the_foe_weary_once():
    f = fight(hero(main=STAFF), Dice(ints=[15, 2, 15, 2], floats=[0.1, 0.1], choices=[JADE, JADE]))
    f.hero_turn()
    assert notes(f) == ["The Imp looks Weary."]
    f.hero_turn()
    assert notes(f) == ["The Imp looks Weary."]  # not repeated
    f = fight(hero(main=STAFF), Dice(ints=[15, 2], floats=[0.9], choices=[JADE]))
    f.hero_turn()
    assert notes(f) == []
    f = fight(hero(main=STAFF), Dice(floats=[0.1], choices=[JADE]), mhp=5, final=True)
    f.hero_turn()
    assert f.mhp <= 0 and notes(f) == []  # nothing is Weary once it has collapsed


def test_confuse_and_hard_block_shield_the_reply():
    for spell, reply in ((CONFUSE, "stumbles in confusion"), (HARD_BLOCK, "the ward absorbs it")):
        f = fight(hero(main=STAFF), Dice(choices=[spell]))
        mine, shield = f.hero_turn()
        assert mine == f"Ada casts {spell.name}" and reply in f.foe_turn(shield)
    f = fight(hero(main=STAFF), win=False, final=True)
    assert "strikes for" in f.foe_turn("Confuse")  # fate beats the shield on a lost last round


def test_supply_chain_attack_chains_two_hits():
    f = fight(hero(main=STAFF), Dice(ints=[15, 3, 15, 4], choices=[SUPPLY]))
    assert f.hero_turn()[0] == "Ada casts Supply Chain Attack: hits for 6, then hits for 8 (+1 chain)"
    f = fight(hero(main=STAFF), Dice(ints=[15, 3, 1], choices=[SUPPLY]))
    assert f.hero_turn()[0].endswith("hits for 6, then fumbles")
    f = fight(hero(main=STAFF), Dice(ints=[1, 15, 4], choices=[SUPPLY]))
    assert f.hero_turn()[0].endswith("fumbles, then hits for 7")  # no link, no bonus
    f = fight(hero(main=STAFF), Dice(ints=[1, 3], choices=[SUPPLY]), mac=30)
    assert f.hero_turn()[0].endswith("fumbles, then misses")
    f = fight(hero(main=STAFF), Dice(ints=[15, 3], choices=[SUPPLY]), mhp=2)
    assert f.hero_turn()[0].endswith("hits for 6") and f.mhp <= 0  # the foe is already down


def test_pre_commit_gathers_energy_then_the_next_attack_is_a_critical():
    f = fight(hero(main=STAFF), Dice(ints=[2, 3], choices=[PRECOMMIT]))
    assert f.hero_turn()[0] == "Ada casts Pre-commit and gathers energy" and f.pending == "precommit" and f.mhp == 100
    mine, _ = f.hero_turn()
    assert mine == "Ada casts Jade for 8 (critical)" and f.pending is None
    f = fight(hero(main=STAFF), Dice(ints=[2, 3], choices=[PRECOMMIT]))
    f.hero_turn()
    f.mp = 0  # nothing left to cast: the gathered energy still powers a plain attack
    assert f.hero_turn()[0] == "Ada hits for 8 (critical)"


def test_refactor_morphs_the_staff_for_one_round_with_its_quirks():
    f = fight(hero(main=STAFF), Dice(choices=[REFACTOR, HARD_RESET]))
    assert f.hero_turn()[0] == "Ada casts Refactor. The staff morphs into the [Hard Reset]"
    mp = f.mp
    f.dice = None
    f.rng.ints = [15, 5]
    mine, _ = f.hero_turn()
    assert mine == "Ada hits for 14" and notes(f) == ["The [Hard Reset] reverts to the staff."] and f.mp == mp and f.pending is None
    f = fight(hero(main=STAFF), Dice(ints=[4], choices=[REFACTOR, BLUDGEON]), win=False)
    f.hero_turn()
    assert "backfires for 8" in f.hero_turn()[0]
    f = fight(hero(main=STAFF), Dice(floats=[0.1], choices=[REFACTOR, BLUDGEON]))
    f.hero_turn()
    assert f.hero_turn()[0].endswith("KO") and f.mhp == 0
    f = fight(hero(main=STAFF), Dice(ints=[4], floats=[0.0], choices=[REFACTOR, HOTFIX]))
    f.hero_turn()
    assert "[Hotfix]. Nobody reviewed it, and it backfires for 8" in f.hero_turn()[0]


def test_refactor_can_become_any_non_staff_weapon():
    assert MORPHS and all(i.slot == "weapon" and i.category != "staff" for i in MORPHS)
    assert {"Sudo Shiv", "Force Merge", "Local Bludgeon", "Hotfix"} <= {i.name for i in MORPHS}


def test_sudo_shiv_morph_ignores_armour_once():
    f = fight(hero(main=STAFF), Dice(ints=[2, 3, 2], choices=[REFACTOR, next(i for i in items.ITEMS if i.name == "Sudo Shiv")]), mac=99)
    f.hero_turn()
    assert "hits for" in f.hero_turn()[0]


def test_staff_of_regex_makes_spells_cheaper_and_sometimes_hits_the_caster():
    f = fight(hero(main="Staff of Regex [rare]"), Dice(ints=[5, 15, 2], floats=[0.1], choices=[JADE]))
    mine, _ = f.hero_turn()
    assert "matches too much and hits Ada for 9" in mine and f.hp == f.ch.hp_max - 9 and f.mp == f.ch.mp_max - 1
    f = fight(hero(main="Staff of Regex [rare]"), Dice(ints=[15, 2], floats=[0.9], choices=[JADE]))
    assert "matches too much" not in f.hero_turn()[0]
    f = fight(hero(main="Staff of Regex [rare]", acc="Lockfile Locket [rare]"), Dice(ints=[15, 2], floats=[0.1], choices=[JADE]))
    mine, _ = f.hero_turn()
    assert "the lockfile pins it" in mine and f.hp == f.ch.hp_max  # Dependency Hell


# weapons and accessories


def test_force_merge_ignores_one_failing_result_per_fight():
    ch = hero("Fighter", 1, "Force Merge [rare]")
    f = fight(ch, Dice(ints=[2, 2, 3, 2]), mac=30)
    assert "hits for" in f.hero_turn()[0] and notes(f) == ["[Force Merge] overrides the failing check."]
    assert f.hero_turn()[0] == "Ada misses"  # used up
    f = fight(ch, Dice(ints=[15]))
    assert f.foe_turn("") == "Imp strikes, but [Force Merge] overrides the failing check" and f.hp == ch.hp_max
    f.rng.ints = [15, 4]
    assert f.foe_turn("") == "Imp strikes for 4"
    f = fight(ch, Dice(ints=[3, 4]), win=False, final=True)
    assert f.foe_turn("") == "Imp strikes for 7"  # never overrules a lost last round


def test_sudo_shiv_ignores_armour_on_the_first_attack_only():
    f = fight(hero("Rogue", 1, "Sudo Shiv [legendary]"), Dice(ints=[5, 3, 5]), mac=99)
    assert "hits for" in f.hero_turn()[0]
    assert f.hero_turn()[0] == "Ada misses"


def test_zero_trust_ignores_armour_all_fight():
    ch = hero("Rogue", 1, "Sudo Shiv [legendary]", "Lockfile Locket [rare]")
    f = fight(ch, Dice(ints=[5, 3, 5, 3]), mac=99)
    assert f.set == "Zero Trust"
    assert "hits for" in f.hero_turn()[0] and "hits for" in f.hero_turn()[0]


def test_lockfile_locket_blocks_the_first_strike():
    ch = hero("Fighter", 1, "", "Lockfile Locket [rare]")
    f = fight(ch, Dice(ints=[15, 15, 4]))
    assert f.foe_turn("") == "Imp strikes first, but the lockfile blocks it" and f.hp == ch.hp_max
    assert f.foe_turn("") == "Imp strikes for 4"
    f = fight(ch, Dice(ints=[3, 4]), win=False, final=True)
    assert f.foe_turn("") == "Imp strikes for 7"  # fate still wins


def test_dependabot_charm_rerolls_one_miss():
    f = fight(hero("Fighter", 1, "", "Dependabot Charm [uncommon]"), Dice(ints=[2, 20, 3, 4, 2, 2]), mac=30)
    mine, _ = f.hero_turn()
    assert mine == "Ada hits for 7 (critical)" and notes(f) == ["Dependabot bumps the roll."]
    assert f.hero_turn()[0] == "Ada misses"  # only once per fight


def test_cloak_takes_one_off_each_hit():
    f = fight(hero("Fighter", 1, "", "Cloak of Mild Inconvenience [uncommon]"), Dice(ints=[15, 5, 15, 1]))
    assert f.foe_turn("") == "Imp strikes for 4" and f.foe_turn("") == "Imp strikes for 0"


def test_crown_adds_one_to_hit():
    for acc, verb in (("", "misses"), ("Crown of the Main Branch [legendary]", "hits")):
        f = fight(hero("Fighter", 1, "", acc), Dice(ints=[7, 3]), mac=10)  # 7 + GRAY 2 = 9
        assert verb in f.hero_turn()[0]


def test_hotfix_friday_absorbs_the_backfire():
    plain = fight(hero("Rogue", 1, "Hotfix [rare]"), Dice(ints=[4], floats=[0.0]))
    assert "backfires for 5" in plain.hero_turn()[0] and plain.hp == plain.ch.hp_max - 5
    friday = fight(hero("Rogue", 1, "Hotfix [rare]", "Cloak of Mild Inconvenience [uncommon]"), Dice(ints=[4], floats=[0.0]))
    assert "cloak absorbs it" in friday.hero_turn()[0] and friday.hp == friday.ch.hp_max


def test_pair_programming_adds_one_to_hit_in_round_one_only():
    ch = hero("Fighter", 1, "Squeaky Mallet [common]", "Lucky Rubber Duck [common]")  # GRAY 3
    assert fight(ch, Dice(ints=[6, 3])).set == "Pair Programming"
    assert "hits" in fight(ch, Dice(ints=[6, 3]), mac=10).hero_turn()[0]
    assert "misses" in fight(ch, Dice(ints=[6, 3]), mac=10, rnd=2).hero_turn()[0]


def test_retry_loop_removes_the_ring_penalty():
    for acc_main, verb in (("Squeaky Mallet [common]", "misses"), ("Hard Reset [rare]", "hits")):
        f = fight(hero("Fighter", 1, acc_main, "Ring of Retries [rare]"), Dice(ints=[12, 3]), mac=14)  # 12 + GRAY 2
        assert verb in f.hero_turn()[0]


def test_ring_narrates_the_rewind_on_a_won_last_round():
    runs = [run_encounter(hero("Fighter", 1, "", "Ring of Retries [rare]"), True, random.Random(s), "combat", win_odds=1.0) for s in range(20)]
    assert any("[Ring of Retries] hums" in ln for r in runs for ln in r.lines)


# fate and the whole fight


GEAR = [
    ("Wizard", "Staff of Regex [rare]", "Lockfile Locket [rare]"),
    ("Wizard", "Staff of Regex [rare]", "Dependabot Charm [uncommon]"),
    ("Wizard", "Staff of Eventual Consistency [rare]", ""),
    ("Fighter", "Force Merge [rare]", "Lockfile Locket [rare]"),
    ("Fighter", "Hard Reset [rare]", "Ring of Retries [rare]"),
    ("Fighter", "Squeaky Mallet [common]", "Lucky Rubber Duck [common]"),
    ("Rogue", "Sudo Shiv [legendary]", "Lockfile Locket [rare]"),
    ("Rogue", "Hotfix [rare]", "Cloak of Mild Inconvenience [uncommon]"),
    ("Rogue", "Sudo Shiv [legendary]", "Crown of the Main Branch [legendary]"),
]


@pytest.mark.parametrize("cls,main,acc", GEAR)
def test_fate_still_decides_every_fight(cls, main, acc):
    for seed in range(60):
        for win in (True, False):
            r = run_encounter(hero(cls, 1 + seed % 8, main, acc), win, random.Random(seed), "combat", win_odds=1.0)
            assert r.success is win
            assert any("collapses" in ln for ln in r.lines) is win
            assert any("overwhelmed" in ln for ln in r.lines) is not win


def test_next_round_spells_are_only_cast_in_the_first_two_rounds():
    seen = set()
    for seed in range(300):
        for win in (True, False):
            r = run_encounter(hero(level=7, main=STAFF), win, random.Random(seed), "combat", win_odds=1.0)
            for e in r.transcript:
                if isinstance(e, Round) and e.number == 3:
                    assert "Pre-commit" not in e.hero and "morphs" not in e.hero
                if isinstance(e, Round) and ("Pre-commit" in e.hero or "Refactor" in e.hero):
                    seen.add(e.number)
    assert seen == {1, 2}


def test_every_new_spell_turns_up_in_a_real_fight():
    texts = "\n".join(ln for seed in range(300) for ln in run_encounter(hero(level=7, main=STAFF), True, random.Random(seed), "combat", win_odds=1.0).lines)
    for s in spells.SPELLS:
        assert f"casts {s.name}" in texts
    assert "reverts to the staff" in texts and "looks Weary" in texts and "(+1 chain)" in texts
