import json

import pytest

from questops import ci, game, site
from questops.events import Art, Narration, Retreat, Round
from questops.state import Character, Store

RUN = ci.Run("abc1234", "https://x/commit/abc1234", True, "42")


def test_events_render_their_text():
    assert Narration("hi").text == "hi" and Art("dragon", 2).text == ""
    assert Round(2, "ada hits for 3", "The orc misses").text == "  R2: ada hits for 3. The orc misses."
    assert Retreat(4, "ada", 3).text == "ada retreats, dropping 4 'kens. The streak is broken."
    assert Retreat(0, "ada").text == "ada retreats."
    assert Retreat(1234567, "ada").text == "ada retreats, dropping 1,234,567 'kens."


@pytest.mark.parametrize("kind", ["combat", "treasure", "trap"])
@pytest.mark.parametrize("win", [True, False])
def test_transcript_is_typed_events_with_art_first(kind, win, tmp_path):
    q = game.play(Store(tmp_path), "ada", win, kind=kind, seed="s", context="", run=RUN)
    events = q.result.transcript
    assert isinstance(events[0], Art) and all(isinstance(e, (Art, Narration, Round, Retreat)) for e in events)
    assert q.result.lines == [e.text for e in events if not isinstance(e, Art)]


def test_play_returns_a_result_without_writing(tmp_path):
    store = Store(tmp_path)
    q = game.play(store, "ada", False, kind="combat", seed="s", context="o/r / ci", run=RUN)
    assert isinstance(q.result.transcript[0], Art) and any(isinstance(e, Retreat) for e in q.result.transcript)
    assert q.hero.name == "ada" and q.key == "abc1234"
    assert q.entry["workflow"] == "failed" and q.entry["commit_url"] == RUN.commit_url and q.entry["context"] == "o/r / ci"
    assert q.outputs == {"encounter": "defeat", "title": q.result.title, "xp": 5, "level": q.hero.level, "player": "ada"}
    assert list(tmp_path.iterdir()) == []  # play() touches nothing


def test_play_is_seeded_and_persist_writes_everything(tmp_path):
    a = game.play(Store(tmp_path / "a"), "ada", True, kind=None, seed="s", context="", run=RUN)
    b = game.play(Store(tmp_path / "b"), "ada", True, kind=None, seed="s", context="", run=RUN)
    assert a.result.transcript == b.result.transcript
    store = Store(tmp_path / "a")
    assert not game.already_played(store, "ada", RUN.key)
    site.persist_quest(store, a)
    assert game.already_played(store, "ada", RUN.key) and not game.already_played(store, "ada", "") and not game.already_played(store, "bob", RUN.key)
    assert (store.root / "characters" / "ada.svg").exists() and (store.root / "README.md").exists() and (store.root / "QUESTLOG.md").exists()
    assert store.load("ada").encounters == 1
    assert json.loads((store.root / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()[0])["key"] == "abc1234"


def test_play_without_a_seed_derives_one_from_the_run(tmp_path):
    a = game.play(Store(tmp_path / "a"), "ada", True, kind=None, seed=None, context="c", run=RUN)
    b = game.play(Store(tmp_path / "b"), "ada", True, kind=None, seed=None, context="c", run=RUN)
    assert a.result.transcript == b.result.transcript


def test_play_merchant_and_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "1")
    store = Store(tmp_path)
    nobody = game.play_merchant(store, "ci[bot]", "ctx", RUN)  # the roll hits, but nobody has a bag
    assert not nobody.sold and nobody.meeting.summoned and nobody.outputs == {"encounter": "skipped", "merchant_roll": nobody.meeting.roll}
    ch = Character.create("ada")
    ch.inventory = ["Rusty Dagger [common]"]
    store.save(ch)
    assert game.merchant_key("") == "" and not game.already_visited(store, "")
    m = game.play_merchant(store, "ci[bot]", "ctx", RUN)
    assert m.entry["kind"] == "merchant" and m.entry["key"] == "merchant:abc1234" and m.entry["bot"] == "ci[bot]"
    assert m.entry["title"] == "Sold 1 item to a traveling merchant"
    assert m.outputs == {"encounter": "merchant", "player": "ada", "kens": m.visit.total, "merchant_roll": m.meeting.roll}
    assert not game.already_visited(store, RUN.key)
    site.persist_merchant(store, m)
    assert game.already_visited(store, RUN.key)
    assert store.load("ada").inventory == []
