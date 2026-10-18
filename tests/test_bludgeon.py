import random

from questops.engine import run_encounter
from questops.events import Round
from questops.state import Character


def _fight(win, seed):
    ch = Character.create("t")
    ch.cls = "Fighter"
    ch.main_hand = "Local Bludgeon [uncommon]"
    return run_encounter(ch, win, random.Random(seed), "combat", win_odds=1.0)


def test_bludgeon_fate_still_decides_the_fight():
    for seed in range(60):
        win, loss = _fight(True, seed), _fight(False, seed)
        assert win.success and not loss.success
        assert any("KO" in line for line in win.lines)
        assert not any("KO" in line for line in loss.lines)


def test_bludgeon_backfires_otherwise():
    backfires = sum("backfires" in line for seed in range(60) for line in _fight(False, seed).lines)
    assert backfires >= 60
    assert any("backfires" in line for seed in range(60) for line in _fight(True, seed).lines)


def _hotfix_fight(win, seed):
    ch = Character.create("t")
    ch.cls = "Rogue"
    ch.main_hand = "Hotfix [rare]"
    return run_encounter(ch, win, random.Random(seed), "combat", win_odds=1.0)


def test_hotfix_sometimes_backfires_but_fate_still_decides():
    lines = [line for seed in range(400) for r in (_hotfix_fight(True, seed), _hotfix_fight(False, seed)) for line in r.lines]
    assert any("[Hotfix]. Nobody reviewed it, and it backfires" in line for line in lines)
    for seed in range(100):
        assert _hotfix_fight(True, seed).success and not _hotfix_fight(False, seed).success


def test_hotfix_never_backfires_on_the_winning_blow():
    for seed in range(300):
        r = _hotfix_fight(True, seed)
        final = [e for e in r.transcript if isinstance(e, Round) and e.number == 3]
        assert not any("backfires" in e.text for e in final)
