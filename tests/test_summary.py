import pytest

from questops import ci, cli, render
from questops.engine import Result
from questops.events import Art, Narration, Retreat
from questops.merchant import Meeting, Visit
from questops.presentation import Presentation
from questops.state import Character


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in ("GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "QUESTOPS_DATA_BRANCH", "QUESTOPS_DATA_REPO", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")


def test_summary_is_plain_markdown_without_pixel_art():
    ch = Character.create("ada")
    r = Result("combat", "Slew a mimic", True, [Art("mimic"), Narration("You swing."), Narration("It dies.")], xp=40, kens=12, loot="Rusty Dagger [common]", loot_action="equipped", levels=[2], new_achievements=["First Blood"])
    md = render.summary_md(ch, r, "o/r / ci", "https://x/card.svg")
    assert "```" not in md and "\u2580" not in md and "\u2591" not in md
    assert md.startswith("## \u2705 QuestOps: Slew a mimic\n\n**Victory**")
    assert "> Quest: o/r / ci  \n> You swing.  \n> It dies.  \n" in md and "art" not in md.replace("Quest", "")
    for row in ("| Hero | **ada**, Level 1 ", "| XP | +40 (", "| 'kens | 10 (+12) |", "| Record | 0W / 0L (-) |", "| Loot | **[Rusty Dagger]** *common*<br>Rogue only, +2 damage<br>Equipped |", "| Level up | Now level 1 |", "First Blood"):
        assert row in md
    assert '<img src="https://x/card.svg" alt="ada" width="480">' in md


def test_summary_defeat_bag_and_no_context_or_card():
    ch = Character.create("ada")
    ch.wins, ch.losses, ch.encounters = 1, 2, 3
    r = Result("trap", "Triggered a trap", False, [Narration("Click.")], loot="Rusty Dagger [common]", loot_action="bag")
    md = render.summary_md(ch, r)
    assert md.startswith("## \u274c QuestOps: Triggered a trap\n\n**Defeat**") and "Quest:" not in md and "<img" not in md
    assert "in the bag" in md and "1W / 2L (33%)" in md and "Level up" not in md


def test_merchant_summary_singular_and_plural():
    ch = Character.create("ada")
    one = render.merchant_summary_md(ch, Visit("ada", [("Rusty Dagger [common]", 5)], 0), "ci[bot]", "https://x/c.svg")
    assert "Bought 1 item from **ada** for 5 'kens" in one and "| **[Rusty Dagger]** *common* | +5 'kens |" in one and "ci[bot]" in one and "https://x/c.svg" in one
    two = render.merchant_summary_md(ch, Visit("ada", [("Rusty Dagger [common]", 5), ("Lucky Rubber Duck [common]", 5)], 0), "ci[bot]")
    assert "Bought 2 items" in two and "<img" not in two


def test_comment_is_the_card_and_one_line_with_the_story_collapsed():
    ch = Character.create("ada")
    r = Result("combat", "Slew a mimic", True, [Narration("You swing.")], xp=40, kens=12, loot="Rusty Dagger [common]", loot_action="equipped", new_achievements=["First Blood"])
    md = render.comment_md(ch, r, "o/r / ci", "https://x/card.svg")
    head, rest = md.split("<details>", 1)
    assert head.startswith("### \u2705 QuestOps: Slew a mimic\n") and '<img src="https://x/card.svg" alt="ada" width="480">' in head
    assert "**Victory.** ada the " in head and "Lv 1" in head and "+40 XP" in head and "+12 'kens" in head and "streak 0" in head
    assert "found [Rusty Dagger]" in head and "\U0001F3C6 First Blood" in head
    assert "> You swing." in rest and "| XP |" in rest and rest.rstrip().endswith("</details>")
    assert "<summary>The full encounter</summary>" in rest and "> You swing." not in head


def test_comment_for_a_run_that_saves_nothing_has_no_stats_or_card():
    ch = Character.create("ada")
    r = Result("trap", "Triggered a trap", False, [Narration("Click.")], xp=5, kens=-3)
    md = render.comment_md(ch, r, "", "https://x/card.svg", EPHEMERAL)
    head = md.split("<details>")[0]
    assert "<img" not in head and "streak" not in head and "Lv " not in head and "**Defeat.** ada the " in head
    assert render.comment_md(ch, r).startswith("### \u274c QuestOps: Triggered a trap")


def test_merchant_comment_keeps_the_card_up_top_and_the_prices_collapsed():
    ch = Character.create("ada")
    visit = Visit("ada", [("Rusty Dagger [common]", 5), ("Lucky Rubber Duck [common]", 5)], 0)
    md = render.merchant_comment_md(ch, visit, "ci[bot]", "https://x/c.svg")
    head, rest = md.split("<details>", 1)
    assert head.startswith("### \U0001F6D2 QuestOps: a traveling merchant\n") and "https://x/c.svg" in head
    assert "bought 2 items from ada for 10 'kens" in head and "| **[Rusty Dagger]** *common* | +5 'kens |" in rest and "<img" not in rest
    assert "bought 1 item from ada" in render.merchant_comment_md(ch, Visit("ada", [("Rusty Dagger [common]", 5)], 0), "ci[bot]")


def test_lore_footer_links_the_bestiary_and_the_hall():
    base = "https://github.com/o/r/blob/questops-data/"
    assert render.lore_md(base) == f"\U0001F4D6 [Bestiary and reliquary]({base}lore/README.md) \u00b7 [Hall of Heroes]({base}README.md)"
    assert render.lore_line(base) == f"Lore: {base}lore/README.md"
    assert render.lore_md("") == "" and render.lore_line("") == ""


def test_summary_and_comment_carry_the_lore_links_quietly():
    ch = Character.create("ada")
    r = Result("combat", "Slew a mimic", True, [Narration("It dies.")], foe="Cache Slime")
    lore = render.lore_md("https://x/")
    assert render.summary_md(ch, r, "", "", None, lore).rstrip().endswith(lore)
    head, rest = render.comment_md(ch, r, "", "", None, lore).split("<details>", 1)
    assert lore in head and lore not in rest and lore not in render.comment_md(ch, r)


def test_gift_summary_comment_and_card_say_it_is_dangerous_to_go_alone():
    ch = Character.create("ada")
    ch.cls, ch.main_hand = "Fighter", "Squeaky Mallet [common]"
    visit = Visit("ada", [], 0, gift="Squeaky Mallet [common]")
    md = render.merchant_summary_md(ch, visit, "ci[bot]", "https://x/c.svg", Meeting(20, 20))
    assert md.startswith("## \U0001F6D2 QuestOps: a traveling merchant") and "finds ada empty-handed" in md
    assert "It's dangerous to go alone! Take this!" in md and "**ada** now wields **[Squeaky Mallet]** *common* (Fighter only, +2 damage)." in md
    assert '<img src="https://x/c.svg"' in md and "Price" not in md
    head, rest = render.merchant_comment_md(ch, visit, "ci[bot]", "https://x/c.svg").split("<details>", 1)
    assert "gifted ada a starter weapon: Squeaky Mallet." in head and "dangerous to go alone" in rest and "<img" not in rest
    card = render.merchant_card(ch, visit, "ci[bot]", Presentation())
    assert "empty-handed" in card and "dangerous to go alone" in card and "A gift for ada" in card
    assert "[Squeaky Mallet] common  NEW!" in card and "Fighter only, +2 damage" in card and "Sold" not in card
    assert "\x1b[3;38;5;244mFighter only" in render.merchant_card(ch, visit, "ci[bot]", Presentation(color=True))
    plain_gift = Visit("ada", [], 0, gift="Lucky Rubber Duck [common]")
    assert "(" not in render.merchant_summary_md(ch, Visit("ada", [], 0, gift="Mystery [odd]"), "ci[bot]").split("now wields")[1].split("\n")[0]
    assert render.merchant_summary_md(ch, plain_gift, "ci[bot]")


def test_card_url_needs_a_repo_and_data_branch_and_a_real_run(monkeypatch):
    assert ci.card_url("Ada Lovelace", False) == ""
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("QUESTOPS_DATA_BRANCH", "questops-data")
    assert ci.card_url("Ada Lovelace", True) == ""
    assert ci.card_url("Ada Lovelace", False) == "https://github.com/o/r/blob/questops-data/characters/ada-lovelace.svg?raw=true"
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://ghe.example")
    assert ci.card_url("ada", False).startswith("https://ghe.example/o/r/blob/")
    monkeypatch.setenv("QUESTOPS_DATA_REPO", "o/guild")
    assert ci.card_url("ada", False).startswith("https://ghe.example/o/guild/blob/questops-data/")


def test_cli_summary_embeds_the_card(tmp_path, monkeypatch):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("QUESTOPS_DATA_BRANCH", "questops-data")
    assert cli.main(["quest", "--data-dir", str(tmp_path / "d"), "--outcome", "success", "--player", "ada", "--seed", "s"]) == 0
    text = summary.read_text(encoding="utf-8")
    assert "```" not in text and "/blob/questops-data/characters/ada.svg?raw=true" in text

EPHEMERAL = Presentation(ephemeral=True)


def _ephemeral_run(win, kind="treasure"):
    from questops.engine import run_encounter
    import random

    ch = Character.create("ada")
    r = run_encounter(ch, win, random.Random("q"), kind)
    return ch, r


def test_retreat_is_always_recorded_but_only_shown_when_saved():
    _, r = _ephemeral_run(False)
    assert any(isinstance(e, Retreat) for e in r.transcript)
    assert not any("retreat" in ln for ln in EPHEMERAL.story(r))
    assert any("retreats, dropping" in ln for ln in Presentation().story(r))
    assert EPHEMERAL.show_gear is False and EPHEMERAL.show_stats is False and EPHEMERAL.narrated
    assert Presentation().show_gear and Presentation().show_stats and not Presentation().narrated


@pytest.mark.parametrize("win", [True, False])
def test_ephemeral_transcript_has_no_continuity(win):
    ch, r = _ephemeral_run(win)
    text = render.transcript(ch, r, "o/r / ci", EPHEMERAL)
    assert "ada wakes on a cold dungeon floor" in text and "wonders where this is" in text
    assert ("Then everything goes dark again." in text) == win and ("Then nothing." in text) == (not win)
    for gone in ("XP", "'kens (", "streak", "Lv ", "NEW!", "Bagged", "LEVEL UP", "Achievement"):
        assert gone not in text
    assert "ada the Rogue" in text or "ada the Fighter" in text or "ada the Wizard" in text
    full = render.transcript(ch, r, "", Presentation())
    assert "wakes on a cold dungeon floor" not in full and "XP" in full


def test_ephemeral_summary_is_the_story_and_the_hero_only():
    ch, r = _ephemeral_run(True)
    md = render.summary_md(ch, r, "o/r / ci", "https://x/card.svg", EPHEMERAL)
    assert "> ada wakes on a cold dungeon floor" in md and "Then everything goes dark again." in md
    assert "| Hero | **ada** the " in md
    for gone in ("| XP |", "| 'kens |", "Streak", "Record", "<img"):
        assert gone not in md


def test_cli_dry_run_is_ephemeral(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert cli.main(["quest", "--data-dir", str(tmp_path / "d"), "--outcome", "failure", "--player", "ada", "--seed", "s", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "wakes on a cold dungeon floor" in out and "streak" not in out and "retreat" not in out
    assert "Streak" not in summary.read_text(encoding="utf-8")
    assert not (tmp_path / "d" / "characters").exists()
