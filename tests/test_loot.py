import random

from questops import items
from questops.engine import run_encounter
from questops.state import Character, level_for_xp, xp_for_level


def test_slower_levels():
    assert xp_for_level(2) == 600 and xp_for_level(5) == 19200
    assert level_for_xp(599) == 1 and level_for_xp(600) == 2


def test_weapons_are_class_locked_and_accessories_are_not():
    assert items.usable("Hotfix [rare]", "Rogue") and not items.usable("Hotfix [rare]", "Wizard")
    assert items.usable("Intern's Staff [common]", "Wizard") and not items.usable("Intern's Staff [common]", "Fighter")
    assert all(items.usable(f"{i.name} [{i.rarity}]", k) for i in items.ITEMS if i.slot == "accessory" for k in ("Fighter", "Rogue", "Wizard"))


def test_staffs_are_weaker_than_other_weapons_of_the_same_rarity():
    for rarity in items.RARITY_RANK:
        staff = [i.bonus for i in items.ITEMS if i.category == "staff" and i.rarity == rarity]
        heavy = [i.bonus for i in items.ITEMS if i.category in ("dagger", "mallet") and i.rarity == rarity]
        if staff and heavy:
            assert staff[0] < min(heavy)


def test_best_usable_item_per_slot_is_equipped_and_the_rest_bagged():
    ch = Character.create("t")
    ch.cls = "Rogue"
    ch.inventory = ["Rusty Dagger [common]", "Hard Reset [rare]", "Hotfix [rare]", "Lucky Rubber Duck [common]", "Crown of the Main Branch [legendary]"]
    ch.tidy()
    assert ch.main_hand == "Hotfix [rare]"  # Hard Reset is a Fighter weapon
    assert ch.accessory == "Crown of the Main Branch [legendary]"
    assert sorted(ch.inventory) == ["Hard Reset [rare]", "Lucky Rubber Duck [common]", "Rusty Dagger [common]"]


def test_old_saves_with_a_single_equipped_item_migrate():
    ch = Character.from_dict({"name": "t", "cls": "Rogue", "equipped": "Rusty Dagger [common]", "inventory": ["Ring of Retries [rare]"]})
    ch.tidy()
    assert ch.main_hand == "Rusty Dagger [common]" and ch.accessory == "Ring of Retries [rare]"


def test_loot_obeys_the_slots():
    ch = Character.create("t")
    for seed in range(300):
        r = run_encounter(ch, True, random.Random(seed), "treasure")
        if r.loot:
            assert r.loot_action in ("equipped", "bag", "sold")
    assert ch.main_hand == "" or items.usable(ch.main_hand, ch.cls)
    for it in ch.inventory:
        current = ch.main_hand if items.slot(it) == "weapon" else ch.accessory
        assert not (items.usable(it, ch.cls) and items.better(it, current))


def test_weapon_bonus_adds_to_damage():
    ch = Character.create("t")
    ch.cls = "Rogue"
    base = ch.weapon_bonus
    ch.main_hand = "Hotfix [rare]"
    assert ch.weapon_bonus == base + 5 and ch.wielding == "Hotfix"


def test_rubber_duck_grants_gray_but_not_for_achievements():
    ch = Character.create("t")
    gray, natural = ch.gray, ch.natural_gray
    ch.accessory = "Lucky Rubber Duck [common]"
    assert ch.gray == gray + 1 and ch.natural_gray == natural
