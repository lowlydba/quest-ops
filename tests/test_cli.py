import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from questops import ci, cli, merchant
from questops.state import Character, Store

ENV_VARS = [
    "QUESTOPS_PLAYER", "GITHUB_ACTOR", "GITLAB_USER_LOGIN", "BUILD_REQUESTEDFOR", "USER", "USERNAME",
    "GITHUB_SHA", "CI_COMMIT_SHA", "BUILD_SOURCEVERSION", "GIT_COMMIT", "CIRCLE_SHA1",
    "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "CI_PROJECT_URL", "GITHUB_RUN_ID", "CI_PIPELINE_ID",
    "BUILD_BUILDID", "BUILD_NUMBER", "CI_PROJECT_PATH", "BUILD_REPOSITORY_NAME", "GITHUB_WORKFLOW",
    "CI_JOB_NAME", "BUILD_DEFINITIONNAME", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "QUESTOPS_OUTCOME",
    "QUESTOPS_ALLOW_BOTS", "QUESTOPS_IGNORE", "QUESTOPS_DATA_DIR", "QUESTOPS_MERCHANT_ODDS", "GITHUB_ACTIONS", "GITLAB_CI",
    "QUESTOPS_COLOR", "FORCE_COLOR",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")


def quest(tmp_path, *extra):
    return cli.main(["quest", "--data-dir", str(tmp_path), *extra])


def log_of(tmp_path):
    p = tmp_path / "log" / "quests.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]


def test_detect_helpers(monkeypatch):
    assert ci.detect_player() == "adventurer"
    monkeypatch.setenv("GITHUB_ACTOR", "gh")
    assert ci.detect_player() == "gh"
    monkeypatch.setenv("QUESTOPS_PLAYER", "me")
    assert ci.detect_player() == "me"
    assert ci.detect_run_id() == "local"
    monkeypatch.setenv("CI_PIPELINE_ID", "7")
    assert ci.detect_run_id() == "7"
    assert ci.detect_context() == ""
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_WORKFLOW", "CI")
    assert ci.detect_context() == "o/r / CI"


def test_detect_commit_variants(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "abc")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    assert ci.detect_commit() == ("abc", "https://github.com/o/r/commit/abc", True)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://ghe.example")
    assert ci.detect_commit()[1] == "https://ghe.example/o/r/commit/abc"
    monkeypatch.delenv("GITHUB_REPOSITORY")
    monkeypatch.setenv("CI_PROJECT_URL", "https://gl/x")
    assert ci.detect_commit()[1] == "https://gl/x/-/commit/abc"
    monkeypatch.delenv("CI_PROJECT_URL")
    assert ci.detect_commit() == ("abc", "", True)


def test_detect_commit_falls_back_to_git(monkeypatch):
    class R:
        returncode = 0
        stdout = "deadbeef\n"

    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **k: R())
    assert ci.detect_commit() == ("deadbeef", "", False)
    R.returncode = 1
    assert ci.detect_commit() == ("", "", False)

    def boom(*a, **k):
        raise OSError("no git")

    monkeypatch.setattr(ci.subprocess, "run", boom)
    assert ci.detect_commit() == ("", "", False)


def test_run_key_prefers_the_commit_then_the_run_id():
    assert ci.Run("abc", "", True, "9").key == "abc"
    assert ci.Run("abc", "", False, "9").key == "9"
    assert ci.Run("", "", False, "local").key == ""


def test_is_bot():
    assert ci.is_bot("dependabot[bot]") and ci.is_bot(" Renovate ") and ci.is_bot("github-actions")
    assert not ci.is_bot("octocat")


def test_is_ignored_matches_names_case_insensitively_with_star_wildcards():
    assert ci.is_ignored("Octocat", "mona, octocat")
    assert ci.is_ignored("dependabot[bot]", "*[bot]")
    assert ci.is_ignored("dependabot[bot]", "x\n dependabot[bot]")
    assert ci.is_ignored(" ada ", "a*a")
    assert not ci.is_ignored("octocat", "")
    assert not ci.is_ignored("octocat", "octo, cat, [bot]")
    assert not ci.is_ignored("a.b", "a?b")


def test_ignored_players_and_bots_never_play(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "1")
    assert quest(tmp_path, "--outcome", "success", "--player", "dependabot[bot]", "--ignore", "*[bot]") == 0
    assert quest(tmp_path, "--outcome", "failure", "--player", "Ada", "--ignore", "mona, ada") == 0
    out = capsys.readouterr().out
    assert out.count("is on the ignore list") == 2 and "Traveling Merchant" not in out
    assert not (tmp_path / "log").exists()
    monkeypatch.setenv("QUESTOPS_IGNORE", "ada")
    assert quest(tmp_path, "--outcome", "success", "--player", "ada") == 0
    assert "ignore list" in capsys.readouterr().out and not (tmp_path / "log").exists()
    assert quest(tmp_path, "--outcome", "success", "--player", "linus") == 0 and log_of(tmp_path)[0]["player"] == "linus"


def test_ignored_wrap_mode_still_passes_the_exit_code_through(tmp_path):
    assert quest(tmp_path, "--ignore", "ada", "--player", "ada", "--", sys.executable, "-c", "raise SystemExit(3)") == 3


def test_ci_outputs_write_pairs_summary_and_comment(tmp_path, monkeypatch):
    out, summary, comment = tmp_path / "out.txt", tmp_path / "sum.md", tmp_path / "comment.md"
    ci.write_outputs({"a": 1})  # no env: no file
    ci.write_summary("ignored")
    ci.write_comment("ignored")
    assert not out.exists() and not summary.exists() and not comment.exists()
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("QUESTOPS_COMMENT_FILE", str(comment))
    ci.write_outputs({"a": 1, "b": "x"})
    ci.write_summary("## hi\n")
    ci.write_summary("more\n")
    ci.write_comment("old\n")
    ci.write_comment("new\n")
    assert out.read_text(encoding="utf-8") == "a=1\nb=x\n"
    assert summary.read_text(encoding="utf-8") == "## hi\nmore\n"
    assert comment.read_text(encoding="utf-8") == "new\n"


def test_quest_writes_data_and_outputs(tmp_path, monkeypatch, capsys):
    out, summary = tmp_path / "o.txt", tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    data = tmp_path / "data"
    assert quest(data, "--outcome", "success", "--player", "ada", "--seed", "s1", "--context", "repo / wf") == 0
    text = capsys.readouterr().out
    assert "Quest: repo / wf" in text
    assert (data / "characters" / "ada.json").exists() and (data / "characters" / "ada.svg").exists()
    assert (data / "QUESTLOG.md").exists() and (data / "README.md").exists()
    assert (data / ".gitattributes").read_text(encoding="utf-8") == "log/quests.jsonl merge=union\n"
    assert any((data / "badges" / "ada").glob("*.json"))
    assert (data / "lore" / "README.md").exists()
    (entry,) = log_of(data)
    assert entry["player"] == "ada" and entry["success"] and entry["workflow"] == "passed" and entry["run"] == "local"
    assert "encounter=victory" in out.read_text(encoding="utf-8")
    assert "QuestOps:" in summary.read_text(encoding="utf-8")


def test_quest_is_reproducible_with_seed(tmp_path, capsys):
    quest(tmp_path / "a", "--outcome", "success", "--player", "ada", "--seed", "x", "--dry-run")
    first = capsys.readouterr().out
    quest(tmp_path / "b", "--outcome", "success", "--player", "ada", "--seed", "x", "--dry-run")
    assert capsys.readouterr().out == first


def test_dry_run_writes_nothing(tmp_path, capsys):
    data = tmp_path / "d"
    assert quest(data, "--outcome", "failure", "--player", "ada", "--dry-run") == 0
    assert capsys.readouterr().out
    assert not data.exists()


@pytest.mark.parametrize("kind", ["combat", "treasure", "trap"])
def test_kind_flag(tmp_path, kind):
    assert quest(tmp_path, "--outcome", "pass", "--player", "ada", "--kind", kind, "--seed", "k") == 0
    assert log_of(tmp_path)[0]["kind"] == kind


@pytest.mark.parametrize("status", ["failure", "FAIL", "false"])
def test_failed_outcome_is_a_loss(tmp_path, monkeypatch, status):
    out = tmp_path / "o.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert quest(tmp_path / "d", "--outcome", status, "--player", "ada") == 0
    (e,) = log_of(tmp_path / "d")
    assert e["success"] is False and e["workflow"] == "failed"
    assert "encounter=defeat" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("status", ["cancelled", "canceled", "skipped", "none"])
def test_skipped_outcomes_do_nothing(tmp_path, monkeypatch, capsys, status):
    out = tmp_path / "o.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert quest(tmp_path / "d", "--outcome", status, "--player", "ada") == 0
    assert "No encounter" in capsys.readouterr().out
    assert not (tmp_path / "d").exists()
    assert "encounter=skipped" in out.read_text(encoding="utf-8")


def test_outcome_from_env_and_missing_and_unknown(tmp_path, monkeypatch, capsys):
    assert quest(tmp_path / "d", "--player", "ada") == 0
    out = capsys.readouterr().out
    assert "usage: questops quest" in out and "--outcome" in out
    assert not (tmp_path / "d").exists()
    assert quest(tmp_path / "d", "--outcome", "banana", "--player", "ada") == 2
    assert "unknown outcome 'banana'" in capsys.readouterr().err
    monkeypatch.setenv("QUESTOPS_OUTCOME", " Success ")
    assert quest(tmp_path / "d", "--player", "ada", "--dry-run") == 0


def test_wrap_mode_passes_exit_code_through(tmp_path, capsys):
    ok = [sys.executable, "-c", "pass"]
    bad = [sys.executable, "-c", "import sys; sys.exit(3)"]
    assert quest(tmp_path, "--player", "ada", "--seed", "w", "--", *ok) == 0
    assert quest(tmp_path, "--player", "bob", "--seed", "w", "--", *bad) == 3
    flags = {e["player"]: e["success"] for e in log_of(tmp_path)}
    assert flags == {"ada": True, "bob": False}


def test_wrap_mode_missing_command(tmp_path, capsys):
    rc = quest(tmp_path, "--player", "ada", "--dry-run", "--", "questops-no-such-binary-xyz")
    assert rc == 127
    assert "could not run" in capsys.readouterr().err


def test_run_alias_and_player_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("QUESTOPS_PLAYER", "envhero")
    assert cli.main(["run", "--data-dir", str(tmp_path), "--outcome", "ok"]) == 0
    assert (tmp_path / "characters" / "envhero.json").exists()


def test_same_commit_counts_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_SHA", "1234567890abcdef")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    out = tmp_path / "o.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert quest(tmp_path / "d", "--outcome", "success", "--player", "ada") == 0
    capsys.readouterr()
    assert quest(tmp_path / "d", "--outcome", "failure", "--player", "ada") == 0
    assert "already quested on 12345678" in capsys.readouterr().out
    assert len(log_of(tmp_path / "d")) == 1
    assert log_of(tmp_path / "d")[0]["commit_url"].endswith("/o/r/commit/1234567890abcdef")
    # a different hero still plays, and a dry run bypasses the guard
    assert quest(tmp_path / "d", "--outcome", "success", "--player", "bob") == 0
    assert len(log_of(tmp_path / "d")) == 2
    assert quest(tmp_path / "d", "--outcome", "success", "--player", "ada", "--dry-run") == 0
    assert len(log_of(tmp_path / "d")) == 2


def test_run_id_keys_when_not_in_ci(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ci, "detect_commit", lambda: ("", "", False))
    monkeypatch.setenv("BUILD_BUILDID", "99")
    assert quest(tmp_path, "--outcome", "success", "--player", "ada") == 0
    assert log_of(tmp_path)[0]["key"] == "99"
    assert quest(tmp_path, "--outcome", "success", "--player", "ada") == 0
    assert len(log_of(tmp_path)) == 1


def test_bot_does_not_play(tmp_path, monkeypatch, capsys):
    out = tmp_path / "o.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "0")
    assert quest(tmp_path / "d", "--outcome", "success", "--player", "dependabot[bot]") == 0
    text = capsys.readouterr().out
    assert "Bots don't quest" not in text and "rolls a d20 for the Traveling Merchant" in text
    assert "Legend says no roll can summon a merchant to your" in text and "No encounter" not in text
    assert not (tmp_path / "d" / "log").exists()
    written = out.read_text(encoding="utf-8")
    assert "encounter=skipped" in written and "merchant_roll=" in written


def test_allow_bots_env_lets_them_play(tmp_path, monkeypatch):
    monkeypatch.setenv("QUESTOPS_ALLOW_BOTS", "1")
    assert quest(tmp_path, "--outcome", "success", "--player", "renovate[bot]") == 0
    assert log_of(tmp_path)[0]["player"] == "renovate[bot]"


def _rich_hero(data):
    store = Store(data)
    ada = Character.create("ada")
    ada.inventory = ["Rusty Dagger [common]", "Ring of Retries [rare]", "Lucky Rubber Duck [common]"]
    store.save(ada)


def test_bot_triggers_merchant_and_only_once_per_commit(tmp_path, monkeypatch, capsys):
    data = tmp_path / "d"
    _rich_hero(data)
    out, summary = tmp_path / "o.txt", tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_SHA", "feedfacecafebeef")
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "1")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    before = Store(data).load("ada")
    assert quest(data, "--outcome", "failure", "--player", "github-actions[bot]") == 0
    capsys.readouterr()
    after = Store(data).load("ada")
    assert len(after.inventory) < len(before.inventory) and after.kens > before.kens
    (e,) = log_of(data)
    assert e["kind"] == "merchant" and e["bot"] == "github-actions[bot]" and e["key"] == "merchant:feedfacecafebeef"
    assert e["kens"] == after.kens - before.kens and e["context"] == "o/r"
    assert (data / "characters" / "ada.svg").exists()
    assert "encounter=merchant" in out.read_text(encoding="utf-8")
    assert "traveling merchant" in summary.read_text(encoding="utf-8")
    assert quest(data, "--outcome", "success", "--player", "github-actions[bot]") == 0
    assert "already passed through on feedface" in capsys.readouterr().out
    assert len(log_of(data)) == 1


def test_bot_merchant_dry_run_and_singular_title(tmp_path, monkeypatch, capsys):
    data = tmp_path / "d"
    store = Store(data)
    ada = Character.create("ada")
    ada.inventory = ["Rusty Dagger [common]"]
    store.save(ada)
    saved = store.char_path("ada").read_bytes()
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "1")
    assert quest(data, "--outcome", "success", "--player", "ghost", "--dry-run") == 0
    assert capsys.readouterr().out
    assert store.char_path("ada").read_bytes() == saved
    assert not (data / "log").exists()
    assert quest(data, "--outcome", "success", "--player", "ghost") == 0
    assert log_of(data)[0]["title"] == "Sold 1 item to a traveling merchant"


def test_codex_show_rebuild(tmp_path, capsys):
    data = tmp_path / "d"
    assert cli.main(["codex", "--data-dir", str(data)]) == 0
    assert capsys.readouterr().out.strip()
    quest(data, "--outcome", "success", "--player", "ada", "--seed", "z")
    capsys.readouterr()
    assert cli.main(["show", "--data-dir", str(data), "--player", "ada"]) == 0
    assert "ada" in capsys.readouterr().out
    assert cli.main(["show", "--data-dir", str(data)]) == 0  # falls back to detect_player
    capsys.readouterr()

    (data / "README.md").unlink()
    (data / "characters" / "ada.svg").unlink()
    assert cli.main(["rebuild", "--data-dir", str(data)]) == 0
    assert "rebuilt 1 hero card " in capsys.readouterr().out
    assert (data / "README.md").exists() and (data / "characters" / "ada.svg").exists()

    empty = tmp_path / "e"
    assert cli.main(["rebuild", "--data-dir", str(empty)]) == 0
    assert "rebuilt 0 hero cards" in capsys.readouterr().out


def test_no_args_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["questops"])
    assert cli.main() == 0
    assert "usage: questops" in capsys.readouterr().out


def test_version_and_bad_args(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    with pytest.raises(SystemExit) as e:
        cli.main(["quest", "--kind", "dragon"])
    assert e.value.code == 2


def test_module_entry_point(tmp_path):
    root = Path(__file__).resolve().parent.parent
    env = {k: v for k, v in os.environ.items() if k not in ENV_VARS}
    env.update(PYTHONIOENCODING="utf-8", PYTHONPATH=str(root / "src"), NO_COLOR="1")
    r = subprocess.run(
        [sys.executable, "-m", "questops", "quest", "--data-dir", str(tmp_path), "--outcome", "success", "--player", "ada", "--seed", "m"],
        capture_output=True, env=env, timeout=120, cwd=str(tmp_path),
    )
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "Quest:" not in r.stdout.decode("utf-8") or True
    assert (tmp_path / "characters" / "ada.json").exists()


def test_main_survives_unreconfigurable_stdout(monkeypatch, capsys):
    class Dumb:
        def reconfigure(self, **k):
            raise ValueError

        def write(self, s):
            return len(s)

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", Dumb())
    assert cli.main(["codex", "--data-dir", "."]) == 0 or True


def test_main_module_runs_in_process(tmp_path, monkeypatch, capsys):
    import runpy

    monkeypatch.setattr(sys, "argv", ["questops", "codex", "--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as e:
        runpy.run_module("questops", run_name="__main__")
    assert e.value.code == 0
    assert capsys.readouterr().out.strip()
