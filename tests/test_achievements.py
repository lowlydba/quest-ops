import random

from questops.engine import ACHIEVEMENTS, run_encounter
from questops.state import Character


def test_back_in_the_green_needs_three_losses_in_a_row():
    ch = Character.create("t")
    for i in range(2):
        run_encounter(ch, False, random.Random(i))
    assert "Back in the Green (win after 3 losses)" not in run_encounter(ch, True, random.Random(9), win_odds=1.0).new_achievements
    for i in range(3):
        run_encounter(ch, False, random.Random(i))
    assert "Back in the Green (win after 3 losses)" in run_encounter(ch, True, random.Random(9), win_odds=1.0).new_achievements


def test_gray_milestones_follow_level():
    ch = Character.create("t")
    ch.level = 4
    assert ACHIEVEMENTS["journeyman"][1](ch, None)
    assert not ACHIEVEMENTS["greybeard"][1](ch, None)
    ch.level = 9
    assert ACHIEVEMENTS["greybeard"][1](ch, None)


def test_removed_achievements_are_gone():
    labels = [v[0] for v in ACHIEVEMENTS.values()]
    assert not any(x in " ".join(labels) for x in ("First Blood", "Hat Trick", "Mimic Bait"))
