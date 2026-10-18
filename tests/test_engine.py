from questops import render
from questops.engine import run_encounter
from questops.state import Character, Store
import random


def test_outcome_is_fate():
    for seed in range(40):
        for win in (True, False):
            ch = Character.create("t")
            r = run_encounter(ch, win, random.Random(seed), win_odds=1.0, trap_odds=1.0)
            assert r.success is win
            assert ch.wins == int(win) and ch.losses == int(not win)


def test_deterministic():
    a = run_encounter(Character.create("t"), True, random.Random(7)).transcript
    b = run_encounter(Character.create("t"), True, random.Random(7)).transcript
    assert a == b


def test_level_up_and_persistence(tmp_path):
    store = Store(tmp_path)
    ch = store.load("Ada Lovelace")
    for i in range(14):
        run_encounter(ch, True, random.Random(i), "treasure")
    store.save(ch)
    again = store.load("Ada Lovelace")
    assert again.level >= 2 and again.kens > 10
    assert "Level" in render.sheet_md(again)


def test_defeat_costs_kens_and_streak():
    ch = Character.create("t")
    ch.kens, ch.streak = 100, 4
    run_encounter(ch, False, random.Random(1))
    assert ch.kens == 90 and ch.streak == 0
