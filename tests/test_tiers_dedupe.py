import random
import subprocess
import sys
import os

from questops.engine import TIERS, run_encounter, tier_weights
from questops.state import Character


def test_tiers_unlock_by_level():
    assert tier_weights(1) == [100, 0, 0]
    assert tier_weights(5)[1] > 0 and tier_weights(5)[2] == 0
    assert tier_weights(10)[2] > 0
    seen = set()
    for i in range(300):
        ch = Character.create("t")
        ch.level = 10
        seen.add(run_encounter(ch, True, random.Random(i), "combat", win_odds=1.0).tier)
    assert seen == {0, 1, 2}


def test_higher_tiers_are_tougher_and_pay_more():
    base = Character.create("a")
    base.level = 10
    xp = {}
    for i in range(400):
        ch = Character.create("t")
        ch.level = 10
        r = run_encounter(ch, True, random.Random(i), "combat", win_odds=1.0)
        xp.setdefault(r.foe.replace(TIERS[r.tier][0], ""), {})[r.tier] = r.xp
    for tiers in xp.values():
        if len(tiers) == 3:
            assert tiers[0] < tiers[1] < tiers[2]


def _quest(tmp_path, sha, outcome="failure"):
    env = {**os.environ, "GITHUB_SHA": sha, "PYTHONPATH": "src", "QUESTOPS_COLOR": "0", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "questops", "quest", "--outcome", outcome, "--player", "ada", "--data-dir", str(tmp_path)],
        capture_output=True, text=True, env=env, encoding="utf-8",
    )


def test_one_encounter_per_commit_so_reruns_do_not_count(tmp_path):
    _quest(tmp_path, "a" * 40)
    again = _quest(tmp_path, "a" * 40, "success")
    assert "already quested" in again.stdout
    _quest(tmp_path, "b" * 40, "success")
    log = (tmp_path / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 2
    assert '"commit": "' + "a" * 40 in log[0]
