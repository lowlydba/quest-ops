import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "data-branch.sh"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None or shutil.which("git") is None, reason="needs bash and git")


def _sh(*args, cwd=None):
    return subprocess.run([BASH, SCRIPT.as_posix(), *[str(a) for a in args]], capture_output=True, text=True, cwd=cwd)


def _quest(data_dir, player, sha):
    env = {**os.environ, "GITHUB_SHA": sha, "PYTHONPATH": "src", "QUESTOPS_COLOR": "0", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "questops", "quest", "--outcome", "success", "--player", player, "--data-dir", str(data_dir), "--seed", sha],
        capture_output=True, text=True, env=env, encoding="utf-8",
    )


@needs_bash
def test_a_lost_race_exits_75_and_a_redo_on_the_new_tip_lands(tmp_path):
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", remote.as_posix()], check=True, capture_output=True)
    url = remote.as_posix()
    a, b = tmp_path / "a", tmp_path / "b"

    # seed the branch so both runs start from the same tip
    seed = tmp_path / "seed"
    assert _sh("pull", seed, "data", url).returncode == 0
    (seed / "README.md").write_text("start\n")
    assert _sh("push", seed, "data", "seed").returncode == 0

    assert _sh("pull", a, "data", url).returncode == 0
    assert _sh("pull", b, "data", url).returncode == 0
    _quest(a, "ada", "1" * 40)
    _quest(b, "linus", "2" * 40)
    assert _sh("push", a, "data", "ada").returncode == 0
    lost = _sh("push", b, "data", "linus")
    assert lost.returncode == 75, lost.stderr

    # the shim's answer: throw the attempt away, pull the new tip, play again, push
    assert _sh("pull", b, "data", url).returncode == 0
    _quest(b, "linus", "2" * 40)
    assert _sh("push", b, "data", "linus").returncode == 0

    check = tmp_path / "check"
    assert _sh("pull", check, "data", url).returncode == 0
    assert (check / "characters" / "ada.json").exists() and (check / "characters" / "linus.json").exists()
    log = (check / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 2  # both quests, no merge, no conflict


def test_rebuild_regenerates_every_derived_file(tmp_path):
    _quest(tmp_path, "ada", "3" * 40)
    _quest(tmp_path, "linus", "4" * 40)
    derived = [tmp_path / "README.md", tmp_path / "QUESTLOG.md", tmp_path / "characters" / "ada.svg", tmp_path / "badges" / "linus" / "level.json", tmp_path / "lore" / "README.md"]
    for p in derived:
        p.unlink()
    env = {**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run([sys.executable, "-m", "questops", "rebuild", "--data-dir", str(tmp_path)], capture_output=True, text=True, env=env, encoding="utf-8")
    assert out.returncode == 0 and "rebuilt 2 hero cards" in out.stdout
    assert all(p.exists() for p in derived)
    assert "merge=union" in (tmp_path / ".gitattributes").read_text(encoding="utf-8")
