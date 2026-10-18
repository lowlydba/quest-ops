import random

from questops.engine import PASS_KIND_WEIGHTS, WIN_ODDS, run_encounter
from questops.state import Character


def _run(success, seed, kind, ring=False, odds=WIN_ODDS):
    ch = Character.create("t")
    if ring:
        ch.accessory = "Ring of Retries [rare]"
    return run_encounter(ch, success, random.Random(seed), kind, win_odds=odds)


def test_a_failed_run_is_always_a_loss():
    for seed in range(150):
        for kind in ("combat", "treasure", "trap"):
            assert not _run(False, seed, kind).success
            assert not _run(False, seed, kind, ring=True).success


def test_a_passing_run_wins_chests_for_sure_and_traps_and_fights_most_of_the_time():
    for seed in range(150):
        assert _run(True, seed, "treasure").success
    traps = sum(_run(True, seed, "trap").success for seed in range(2000))
    assert 0.74 < traps / 2000 < 0.86  # about 80%, never certain
    wins = sum(_run(True, seed, "combat").success for seed in range(2000))
    assert 0.84 < wins / 2000 < 0.95  # about 90%, never certain


def test_ring_of_retries_makes_a_passing_fight_a_sure_win():
    for seed in range(400):
        r = _run(True, seed, "combat", ring=True)
        assert r.success
        assert any("[Ring of Retries] hums" in line for line in r.lines)


def test_passing_runs_are_mostly_monster_fights():
    assert PASS_KIND_WEIGHTS["combat"] > PASS_KIND_WEIGHTS["treasure"] + PASS_KIND_WEIGHTS["trap"] - 1
