import json
import random
import subprocess
import sys
import os

import pytest

from questops import merchant, items
from questops.state import Character, Store


def _store_with_heroes(tmp_path):
    store = Store(tmp_path)
    ada = Character.create("ada")
    ada.main_hand, ada.accessory = "Hotfix [rare]", "Crown of the Main Branch [legendary]"
    ada.inventory = ["Rusty Dagger [common]", "Ring of Retries [rare]", "Lucky Rubber Duck [common]", "Squeaky Mallet [common]"]
    bare = Character.create("bare")  # an empty bag but a weapon in hand: never visited
    bare.main_hand = "Rusty Dagger [common]"
    store.save(ada)
    store.save(bare)
    return store


def test_the_merchant_mostly_does_nothing():
    visits = 0
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        store = _store_with_heroes(pathlib.Path(tmp))
        visits = sum(merchant.visit(store, f"run-{i}").summoned for i in range(2000))
    assert 60 < visits < 140  # about 5%


def test_the_merchant_only_buys_from_the_bag_and_pays_by_rarity(tmp_path):
    store = _store_with_heroes(tmp_path)
    ch, v = merchant.visit(store, "any", chance=1.0).found
    assert ch.name == "ada" and 1 <= len(v.sold) <= 3
    assert ch.main_hand == "Hotfix [rare]" and ch.accessory == "Crown of the Main Branch [legendary]"
    assert ch.kens == v.kens_before + v.total
    for item, price in v.sold:
        assert price == items.SELL_PRICE[items.parse(item)[1]] and item not in ch.inventory


def test_the_roll_is_seeded_by_the_run_so_reruns_cannot_reroll(tmp_path):
    store = _store_with_heroes(tmp_path)
    hits = [merchant.visit(store, f"k{i}").roll for i in range(300)]
    again = [merchant.visit(_store_with_heroes(tmp_path / "again"), f"k{i}").roll for i in range(300)]
    assert hits == again


def _bot_run(tmp_path, sha, bot="github-actions[bot]"):
    env = {**os.environ, "GITHUB_SHA": sha, "PYTHONPATH": "src", "QUESTOPS_COLOR": "0", "PYTHONIOENCODING": "utf-8", "QUESTOPS_MERCHANT_ODDS": "1"}
    return subprocess.run(
        [sys.executable, "-m", "questops", "quest", "--outcome", "success", "--player", bot, "--data-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, encoding="utf-8",
    )


@pytest.mark.parametrize("cls,weapon", [("Fighter", "Squeaky Mallet [common]"), ("Rogue", "Rusty Dagger [common]"), ("Wizard", "Intern's Staff [common]")])
def test_a_hero_with_nothing_is_gifted_a_basic_weapon_for_their_class(tmp_path, cls, weapon):
    store = Store(tmp_path)
    ch = Character.create("newbie")
    ch.cls = cls
    ch.kens = 7
    store.save(ch)
    meeting = merchant.visit(store, "any", chance=1.0)
    hero, v = meeting.found
    assert v.gift == weapon and v.sold == [] and v.total == 0
    assert hero.main_hand == weapon and hero.kens == 7 and items.usable(weapon, cls)


def test_a_hero_of_an_unknown_class_is_left_alone(tmp_path):
    store = Store(tmp_path)
    ch = Character.create("odd")
    ch.cls = "Bard"
    store.save(ch)
    assert merchant.visit(store, "any", chance=1.0).found is None


def test_the_merchant_picks_between_customers_and_empty_handed_heroes(tmp_path):
    store = Store(tmp_path)
    ada = Character.create("ada")
    ada.inventory = ["Rusty Dagger [common]"]
    store.save(ada)
    store.save(Character.create("newbie"))
    gifted, sold = set(), set()
    for i in range(40):
        ch, v = merchant.visit(store, f"k{i}", chance=1.0).found
        (gifted if v.gift else sold).add(ch.name)
        store = Store(tmp_path)  # the visit edits the hero in memory; start each roll from what is saved
    assert gifted == {"newbie"} and sold == {"ada"}


def test_nobody_to_help_means_no_visit(tmp_path):
    store = Store(tmp_path)
    ch = Character.create("equipped")
    ch.main_hand = "Rusty Dagger [common]"
    store.save(ch)
    assert merchant.visit(store, "any", chance=1.0).found is None


def test_a_bot_run_gifts_a_weapon_and_logs_it(tmp_path):
    ch = Character.create("newbie")
    ch.cls = "Wizard"
    Store(tmp_path).save(ch)
    out = _bot_run(tmp_path, "c" * 40).stdout
    assert "It's dangerous to go alone! Take this!" in out and "A gift for newbie" in out and "[Intern's Staff] common  NEW!" in out
    log = json.loads((tmp_path / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert log["kind"] == "merchant" and log["title"] == "Gifted a starter weapon by a traveling merchant" and log["loot"] == "Intern's Staff [common]" and log["kens"] == 0
    assert json.loads((tmp_path / "characters" / "newbie.json").read_text(encoding="utf-8"))["main_hand"] == "Intern's Staff [common]"


def test_a_bot_run_can_trigger_a_sale_once_per_commit(tmp_path):
    _store_with_heroes(tmp_path)
    first = _bot_run(tmp_path, "a" * 40)
    assert "Traveling Merchant" in first.stdout and "ada" in first.stdout
    log = (tmp_path / "log" / "quests.jsonl").read_text(encoding="utf-8")
    assert '"kind": "merchant"' in log
    again = _bot_run(tmp_path, "a" * 40)
    assert "already passed through" in again.stdout
    assert len((tmp_path / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_a_bot_with_no_merchant_just_no_ops(tmp_path):
    env = {**os.environ, "GITHUB_SHA": "b" * 40, "PYTHONPATH": "src", "QUESTOPS_COLOR": "0", "PYTHONIOENCODING": "utf-8", "QUESTOPS_MERCHANT_ODDS": "0"}
    out = subprocess.run([sys.executable, "-m", "questops", "quest", "--outcome", "success", "--player", "dependabot[bot]", "--data-dir", str(tmp_path)], capture_output=True, text=True, env=env, encoding="utf-8")
    assert "Legend says no roll can summon a merchant to your" in out.stdout and not (tmp_path / "log").exists()


def test_each_bot_gets_its_own_look_and_the_default_is_hand_drawn():
    from questops.sprites import SPRITES, merchant_look

    assert merchant_look("github-actions[bot]")[0] == SPRITES["merchant"]
    looks = {str(merchant_look(b)) for b in ["dependabot[bot]", "renovate[bot]", "copilot[bot]", "snyk-bot", "codecov[bot]"]}
    assert len(looks) == 5
