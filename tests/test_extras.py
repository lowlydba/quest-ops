"""Narration colours, loot facts, set display, the codex and the merchant's d20."""

import random
import re

import pytest

from questops import cli, dice, engine, items, merchant, pages, render, spells, svg
from questops.engine import Result
from questops.events import Art, Narration, Retreat, Round
from questops.lore import ITEM_EFFECTS, LORE, SPELL_LORE
from questops.presentation import Presentation
from questops.state import Character, Store, slug, xp_for_level

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def esc(text, code, bold=False):
    return f"\x1b[{'1;' if bold else ''}38;5;{code}m{text}\x1b[0m"


@pytest.fixture(autouse=True)
def no_ambient_colour(monkeypatch):
    """CI runners set GITHUB_ACTIONS, which turns colour on; tests that want colour ask for it."""
    for v in ("GITHUB_ACTIONS", "GITLAB_CI", "FORCE_COLOR", "QUESTOPS_COLOR", "QUESTOPS_PIXELS"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")


# narration colours


def test_colorize_hero_and_plain_text():
    assert render.colorize_narration("e2e-hero-6 picks the lock (5+4). *click*", "e2e-hero-6") == f"{esc('e2e-hero-6', 255, True)} picks the lock (5+4). *click*"
    assert render.colorize_narration("Nothing to see.", "") == "Nothing to see."


def test_colorize_kens_and_item_labels():
    out = render.colorize_narration("Inside: 43 'kens and a [Ring of Retries]!", "ada")
    assert out == f"Inside: {esc(chr(52) + chr(51) + ' ' + chr(39) + 'kens', 172)} and a {esc('[Ring of Retries]', 75, True)}!"
    assert render.colorize_narration("a [Hotfix] and a [Rusty Dagger]", "") == f"a {esc('[Hotfix]', 75, True)} and a {esc('[Rusty Dagger]', 77, True)}"
    assert render.colorize_narration("the [Mystery Thing] is not an item", "") == "the [Mystery Thing] is not an item"


def test_colorize_a_round_in_one_pass():
    text = "  R1: Ada casts Jade for 5. Senior Lint Goblin strikes for 3."
    assert render.colorize_narration(text, "Ada", ("Senior Lint Goblin",)) == (
        f"  R1: {esc('Ada', 255, True)} casts {esc('Jade', 141)} for {esc('5', 196)}. "
        f"{esc('Senior Lint Goblin', 203)} strikes for {esc('3', 196)}."
    )


def test_colorize_damage_weary_and_every_spell():
    assert render.colorize_narration("Darts whistle. Ada takes 7 damage and a lot of embarrassment.", "Ada") == (
        f"Darts whistle. {esc('Ada', 255, True)} takes {esc('7', 196)} damage and a lot of embarrassment."
    )
    assert render.colorize_narration("The Wraith of the Flaky Test looks Weary.", "Ada") == f"The {esc('Wraith of the Flaky Test', 203)} looks {esc('Weary', 244)}."
    for s in spells.SPELLS:
        assert render.colorize_narration(f"casts {s.name}", "") == f"casts {esc(s.name, 141)}"


def test_colorize_leaves_escaped_text_alone():
    text = "\x1b[1mAda\x1b[0m hits for 3"
    assert render.colorize_narration(text, "Ada") == text


def test_colour_on_only_adds_escapes_to_the_story():
    for seed in range(20):
        ch = Character.create("ada")
        r = engine.run_encounter(ch, seed % 2 == 0, random.Random(seed), None)
        plain = render.transcript(ch, r, "", Presentation(color=False))
        coloured = render.transcript(ch, r, "", Presentation(color=True))
        assert "\x1b" not in plain and "\x1b" in coloured
        story = lambda t: [ln for ln in ANSI.sub("", t).split("\n") if ln.startswith("  R") or ln.startswith("A wild")]
        assert story(plain) == story(coloured)
        for e in r.transcript:
            if isinstance(e, (Narration, Round)):
                assert ANSI.sub("", render.colorize_narration(e.text, "ada", (r.foe,))) == e.text


def test_coloured_transcript_paints_names_numbers_and_loot():
    ch = Character.create("ada")
    r = Result("treasure", "t", True, [Narration("ada picks the lock (5+4). *click*"), Narration("Inside: 43 'kens and a [Ring of Retries]!")])
    text = render.transcript(ch, r, "", Presentation(color=True))
    assert esc("ada", 255, True) + " picks the lock (5+4)" in text
    assert esc("43 'kens", 172) in text and esc("[Ring of Retries]", 75, True) in text


# loot facts


def test_item_facts_cover_stats_effects_and_sets():
    assert render.item_facts("Hotfix [rare]") == [
        "Rogue only, +5 damage", ITEM_EFFECTS["Hotfix"], "Part of Hotfix Friday with Cloak of Mild Inconvenience"]
    assert render.item_facts("Lucky Rubber Duck [common]") == [
        ITEM_EFFECTS["Lucky Rubber Duck"], "Part of Pair Programming with Squeaky Mallet"]
    assert render.item_facts("Rusty Dagger [common]") == ["Rogue only, +2 damage"]
    assert render.item_facts("Mystery [odd]") == []


def _loot_run(monkeypatch, loot, **setup):
    ch = Character.create("ada")
    ch.cls = "Rogue"
    for k, v in setup.items():
        setattr(ch, k, v)
    monkeypatch.setattr(engine, "roll_loot", lambda rng, c, bonus=0: loot)
    return ch, engine.run_encounter(ch, True, random.Random(1), "treasure")


def test_the_engine_records_what_loot_replaced(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]", main_hand="Rusty Dagger [common]")
    assert r.loot_action == "equipped" and r.replaced == "Rusty Dagger [common]"
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]")
    assert r.loot_action == "equipped" and r.replaced == ""
    ch, r = _loot_run(monkeypatch, "Rusty Dagger [common]", main_hand="Hotfix [rare]")
    assert r.loot_action == "bag" and r.replaced == ""


def test_a_spare_of_owned_gear_is_sold_for_its_price(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]", main_hand="Hotfix [rare]", inventory=[], kens=10)
    assert r.loot_action == "sold" and r.replaced == "" and ch.main_hand == "Hotfix [rare]" and ch.inventory == []
    assert r.kens >= 140 + 20 and ch.kens == 10 + r.kens
    assert "already has one" in r.transcript[-1].text and "sells in minutes for 140 'kens" in r.transcript[-1].text
    assert render.loot_status(ch, r) == "Spare sold for 140 'kens"
    ch, r = _loot_run(monkeypatch, "Rusty Dagger [common]", main_hand="Hotfix [rare]", inventory=["Rusty Dagger [common]"])
    assert r.loot_action == "sold" and ch.inventory == ["Rusty Dagger [common]"]
    plain = render.transcript(ch, r, "", Presentation())
    assert "[Rusty Dagger] common" in plain and "Spare sold for 15 'kens" in plain and "Bagged" not in plain


def test_gray_still_shows_when_no_effect_text_describes_it(monkeypatch):
    monkeypatch.delitem(ITEM_EFFECTS, "Lucky Rubber Duck")
    assert render.item_facts("Lucky Rubber Duck [common]") == ["+1 GRAY", "Part of Pair Programming with Squeaky Mallet"]


def test_long_names_titles_and_achievements_wrap_instead_of_truncating():
    ch = Character.create("a-very-long-hero-name-for-layout-1234")
    ch.cls, ch.kens, ch.xp = "Wizard", 1234567, 98765
    r = Result("combat", "Defeated by the Skip Level Ancient Wyrm of Legacy Prod", False, [], xp=5, kens=-123456,
               new_achievements=["Skip Level Meeting (slew a Skip Level foe)"])
    lines = [ln for ln in render.transcript(ch, r, "", Presentation()).splitlines() if ln.startswith("|")]
    text = "\n".join(lines)
    assert "\u2026" not in text and "a-very-long-hero-name-for-layout-1234" in text and "the Wizard  Lv" in text
    assert "DEFEAT\n" in text.replace("  ", "\n", 1) or "| DEFEAT" in text
    assert "Skip Level Ancient Wyrm of Legacy Prod" in text and "\u25cf 123 toh \u25cf 4,567 'kens (-123,456)" in text
    assert "Achievement" not in text and all(len(ln) == 62 for ln in lines)  # the story carries achievements, not the card
    assert "Achievement unlocked: Skip Level Meeting (slew a Skip Level foe)" in render.transcript(ch, r, "", Presentation())
    coloured = render.transcript(ch, r, "", Presentation(color=True))
    assert "123 toh" in coloured and "4,567" in coloured and "\u2026" not in coloured


def test_nothing_is_said_about_zero_kens(monkeypatch):
    ch = Character.create("ada")
    ch.cls, ch.kens = "Rogue", 0
    r = engine.run_encounter(ch, False, random.Random(3), "trap")
    assert "'kens" not in r.transcript[-1].text and r.kens == 0
    plain = render.transcript(ch, r, "", Presentation())
    assert "(+0)" not in plain and "(-0)" not in plain and "0 'kens (" not in plain
    assert "(+0)" not in render.summary_md(ch, r) and "'kens | 0 |" in render.summary_md(ch, r)
    assert "'kens" not in render.comment_md(ch, r).split("<details>")[0]


def test_the_mimic_replaces_the_chest_and_the_purse_joke_needs_a_purse():
    ch = Character.create("ada")
    ch.kens = 0
    r = engine.run_encounter(ch, False, random.Random(4), "treasure")
    assert isinstance(r.transcript[0], Art) and r.transcript[0].key == "mimic" and sum(isinstance(e, Art) for e in r.transcript) == 1
    assert "well-lit chest" in r.transcript[1].text and "nobody knew how to spend" not in r.transcript[1].text
    ch.kens = 100
    r = engine.run_encounter(ch, False, random.Random(4), "treasure")
    assert "nobody knew how to spend" in r.transcript[1].text


def test_an_empty_handed_hero_meets_the_old_man_not_the_usual_merchant():
    from questops.sprites import gift_sprite, merchant_sprite

    ch = Character.create("ada")
    gift = merchant.Visit("ada", [], 0, gift="Squeaky Mallet [common]")
    sale = merchant.Visit("ada", [("Rusty Dagger [common]", 15)], 0)
    elder = [ln for ln in gift_sprite(False).splitlines() if ln.strip()]
    assert all(ln in render.merchant_card(ch, gift, "ci[bot]", Presentation()) for ln in elder)
    assert elder[0] not in render.merchant_card(ch, sale, "ci[bot]", Presentation())
    assert "\x1b[" in gift_sprite(True) and gift_sprite(True) != merchant_sprite("ci[bot]", True)
    files = pages.lore_files()
    assert files["lore/img/old-man.svg"].startswith("<svg") and "old man" in files["lore/npcs/traveling-merchant.md"] and "old-man.svg" in files["lore/npcs/traveling-merchant.md"]


def _levelling(from_level, to_xp_level):
    ch = Character.create("ada")
    ch.cls, ch.level, ch.xp = "Rogue", from_level, xp_for_level(to_xp_level) - 1
    r = engine.run_encounter(ch, True, random.Random(2), "trap")
    return ch, r, [e.text for e in r.transcript if isinstance(e, Narration)]


def test_levelling_up_is_part_of_the_story_and_unlocks_are_announced():
    ch, r, texts = _levelling(4, 5)
    assert r.levels == [5] and "ada reaches level 5." in texts and texts[-1] == "Word gets around: Senior foes can now turn up."
    assert "LEVEL UP! Now level 5" in render.transcript(ch, r, "", Presentation())
    ch, r, texts = _levelling(1, 11)
    assert r.levels[-1] == 11 and texts.count("Word gets around: Senior foes can now turn up.") == 1
    assert "Word gets around: Skip Level foes can now turn up." in texts and texts.index("ada reaches level 10.") < texts.index("Word gets around: Skip Level foes can now turn up.")
    ch, r, texts = _levelling(6, 7)
    assert "reaches level 7." in texts[-1] and not any("Word gets around" in x for x in texts)
    quiet = engine.run_encounter(Character.create("ada"), False, random.Random(2), "trap")
    assert not any("reaches level" in e.text for e in quiet.transcript if isinstance(e, Narration))


def test_a_loss_never_shows_an_upward_streak():
    ch = Character.create("ada")
    won = Result("trap", "t", True, [])
    ch.streak = 3
    assert "\u25b2 streak 3" in render.transcript(ch, won, "", Presentation())
    ch.streak = 0
    lost = Result("trap", "t", False, [Retreat(0, "ada", 4)])
    text = render.transcript(ch, lost, "", Presentation())
    assert "\u25bc streak 0" in text and "\u25b2" not in text
    assert "\x1b[38;5;196m\u25bc streak 0" in render.transcript(ch, lost, "", Presentation(color=True))
    nothing = render.transcript(ch, Result("trap", "t", False, [Retreat(0, "ada", 0)]), "", Presentation())
    assert "streak 0" in nothing and "\u25bc" not in nothing and "\u25b2" not in nothing


def test_traveling_merchant_is_rainbow_only_with_colour():
    assert render.rainbow("Traveling Merchant", False) == "Traveling Merchant"
    out = render.rainbow("Traveling Merchant", True)
    codes = re.findall(r"\x1b\[1;38;5;(\d+)m(.)", out)
    assert "".join(ch for _, ch in codes) == "TravelingMerchant" and " " in re.sub(r"\x1b\[[0-9;]*m", "", out)
    assert codes[0][0] == str(render.RAINBOW[0]) and codes[-1][0] == str(render.RAINBOW[-1]) and len({c for c, _ in codes}) > 8
    ch = Character.create("ada")
    assert "Traveling Merchant" in render.merchant_roll("ci[bot]", merchant.Meeting(7, 20), Presentation()) 
    assert "Traveling Merchant" not in render.merchant_roll("ci[bot]", merchant.Meeting(7, 20), Presentation(color=True))
    assert re.sub(r"\x1b\[[0-9;]*m", "", render.merchant_roll("ci[bot]", merchant.Meeting(7, 20), Presentation(color=True))).count("Traveling Merchant") == 1
    visit = merchant.Visit("ada", [("Rusty Dagger [common]", 15)], 0)
    assert "Traveling Merchant" not in render.merchant_card(ch, visit, "ci[bot]", Presentation(color=True))
    gift = merchant.Visit("ada", [], 0, gift="Squeaky Mallet [common]")
    assert "Traveling Merchant" in re.sub(r"\x1b\[[0-9;]*m", "", render.merchant_card(ch, gift, "ci[bot]", Presentation(color=True)))


def test_loot_status_says_what_happened(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]", main_hand="Rusty Dagger [common]")
    assert render.loot_status(ch, r) == "Equipped, replacing Rusty Dagger"
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]")
    assert render.loot_status(ch, r) == "Equipped"
    ch, r = _loot_run(monkeypatch, "Rusty Dagger [common]", main_hand="Hotfix [rare]")
    assert render.loot_status(ch, r) == "Kept in the bag: not rarer than your Hotfix"
    ch, r = _loot_run(monkeypatch, "Hard Reset [rare]")
    assert render.loot_status(ch, r) == "Kept in the bag: your class cannot wield it"
    ch, r = _loot_run(monkeypatch, "Ring of Retries [rare]", accessory="Crown of the Main Branch [legendary]")
    assert render.loot_status(ch, r) == "Kept in the bag: not rarer than your Crown of the Main Branch"


def test_a_new_accessory_with_no_other_facts_gets_no_bare_slot_line(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Dependabot Charm [uncommon]")
    plain = render.transcript(ch, r, "", Presentation())
    assert "[Dependabot Charm] uncommon  NEW!" in plain and "accessory" not in plain
    coloured = render.transcript(ch, r, "", Presentation(color=True))
    assert "\x1b[3;38;5;244mOnce per fight" in coloured and "\x1b[3;38;5;244maccessory" not in coloured
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]")
    assert "\x1b[3;38;5;244mRogue only" in render.transcript(ch, r, "", Presentation(color=True))


def test_transcript_shows_the_loot_facts_in_its_gear_row_once(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]", main_hand="Rusty Dagger [common]")
    plain = render.transcript(ch, r, "", Presentation())
    assert "[Hotfix] rare  NEW!" in plain and "Rogue only, +5 damage" in plain
    assert "Replaced Rusty Dagger" in plain and "Part of Hotfix Friday with" in plain
    card = [ln for ln in plain.splitlines() if ln.startswith("|")]
    assert sum("[Hotfix] rare" in ln for ln in card) == 1 and "Found:" not in plain
    assert all(len(ln) == 62 for ln in plain.splitlines() if ln.startswith("|"))
    coloured = render.transcript(ch, r, "", Presentation(color=True))
    assert esc("[Hotfix]", 75, True) in coloured and "\x1b[3;38;5;244mrare\x1b[0m" in coloured
    ch, r = _loot_run(monkeypatch, "Rusty Dagger [common]", main_hand="Hotfix [rare]")
    bagged = render.transcript(ch, r, "", Presentation())
    assert "[Rusty Dagger] common" in bagged and "Bagged: not rarer than your Hotfix" in bagged
    assert "\u2026" not in bagged


def test_dry_run_shows_the_loot_but_not_what_became_of_it(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]", main_hand="Rusty Dagger [common]")
    pres = Presentation(ephemeral=True)
    text = render.transcript(ch, r, "", pres)
    assert "Found: [Hotfix] rare" in text and "+5 damage" in text
    assert "Equipped" not in text and "replacing" not in text and "bag" not in text
    md = render.summary_md(ch, r, "", pres=pres)
    assert "| Loot | **[Hotfix]** *rare*<br>Rogue only, +5 damage" in md and "Equipped" not in md
    assert "Loot" not in render.summary_md(ch, Result("trap", "t", True), "", pres=pres)


def test_summary_loot_row_has_the_facts(monkeypatch):
    ch, r = _loot_run(monkeypatch, "Hotfix [rare]", main_hand="Rusty Dagger [common]")
    md = render.summary_md(ch, r)
    assert "**[Hotfix]** *rare*<br>Rogue only, +5 damage<br>" in md and "Part of Hotfix Friday" in md
    assert "<br>Equipped, replacing Rusty Dagger |" in md and "\x1b" not in md


# sets


def test_every_set_names_real_items_and_has_lore():
    names = {i.name: i for i in items.ITEMS}
    assert len(items.SETS) == 5
    for s in items.SETS:
        assert names[s.weapon].slot == "weapon" and names[s.accessory].slot == "accessory"
        assert s.effect and len(re.findall(r"[.!?](?:\s|$)", s.lore)) == 2
    assert items.active_set("Hotfix [rare]", "Cloak of Mild Inconvenience [uncommon]").name == "Hotfix Friday"
    assert items.active_set("Hotfix [rare]", "") is None and items.active_set("", "") is None


def _set_hero():
    ch = Character.create("ada")
    ch.cls, ch.main_hand, ch.accessory = "Rogue", "Hotfix [rare]", "Cloak of Mild Inconvenience [uncommon]"
    return ch


def test_active_set_shows_on_card_summary_sheet_and_svg():
    ch = _set_hero()
    r = Result("trap", "t", True, [Narration("x")])
    plain = render.transcript(ch, r, "", Presentation())
    assert "+ Set: Hotfix Friday" in plain
    assert "Set: Hotfix Friday" not in render.transcript(ch, r, "", Presentation(ephemeral=True))
    assert "| Set | **Hotfix Friday**: Hotfix backfires are absorbed" in render.summary_md(ch, r)
    assert "**Set:** Hotfix Friday." in render.sheet_md(ch)
    assert "Set: Hotfix Friday" in svg.card(ch)
    ch.accessory = ""
    assert "Set:" not in svg.card(ch) and "Set:" not in render.sheet_md(ch)


def test_codex_lists_spells_and_sets(tmp_path):
    text = render.codex(Store(tmp_path))
    for s in spells.SPELLS:
        assert s.name in text and s.effect in text
    for s in items.SETS:
        assert s.name in text and s.effect in text
    assert "Lv 7" in text


# lore pages


def test_every_spell_and_set_has_lore_and_a_page():
    files = pages.lore_files()
    book, index = files["lore/spellbook.md"], files["lore/README.md"]
    assert "spellbook.md" in index
    for s in spells.SPELLS:
        assert len(re.findall(r"[.!?](?:\s|$)", SPELL_LORE[s.name])) == 2
        assert s.name in book and SPELL_LORE[s.name] in book and s.effect in book and f"| {s.level} | {s.mp} |" in book
    assert set(SPELL_LORE) == {s.name for s in spells.SPELLS}
    for s in items.SETS:
        assert s.name in index and s.lore in index and s.effect in index
    for name in ("Staff of Regex", "Force Merge", "Sudo Shiv", "Lockfile Locket", "Dependabot Charm"):
        assert LORE[name][0] == "item" and name in ITEM_EFFECTS
        assert f"lore/items/{slug(name)}.md" in files
    assert "part of [Zero Trust]" in files["lore/items/sudo-shiv.md"] and "part of" not in files["lore/items/dependabot-charm.md"]


# the merchant's d20


def _sha_with_roll(want):
    return next(f"sha{i}" for i in range(10000) if random.Random(__import__("questops.state", fromlist=["x"]).seed_int("merchant", f"sha{i}")).randint(1, 20) == want)


def test_threshold_maps_odds_to_a_d20_roll():
    assert [merchant.threshold(p) for p in (0.05, 0.5, 1, 2, 0, -1, 0.01, 0.25)] == [20, 11, 1, 1, 21, 21, 20, 16]


def test_only_a_natural_20_summons_by_default(tmp_path):
    store = Store(tmp_path)
    ch = Character.create("ada")
    ch.inventory = ["Rusty Dagger [common]"]
    store.save(ch)
    miss = merchant.visit(store, _sha_with_roll(7))
    assert (miss.roll, miss.need, miss.summoned, miss.found) == (7, 20, False, None)
    hit = merchant.visit(store, _sha_with_roll(20))
    assert hit.roll == 20 and hit.summoned and hit.found[1].sold
    assert merchant.visit(store, _sha_with_roll(20)).roll == 20  # re-runs agree


def test_the_odds_override_moves_the_threshold(tmp_path, monkeypatch):
    store = Store(tmp_path)
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "0.5")
    assert merchant.visit(store, _sha_with_roll(11)).need == 11 and merchant.visit(store, _sha_with_roll(11)).summoned
    assert not merchant.visit(store, _sha_with_roll(10)).summoned
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "0")
    assert not merchant.visit(store, _sha_with_roll(20)).summoned


def test_the_roll_scene_matches_an_encounter():
    plain = render.merchant_roll("ci[bot]", merchant.Meeting(7, 20), False, "o/r / ci")
    assert "\x1b" not in plain and "Quest: o/r / ci" in plain
    assert "ci[bot] rolls a d20 for the Traveling Merchant." in plain and "Bots don't quest" not in plain
    assert "It lands on 7. The road stays empty." in plain
    assert "| QUIET  Rolled a 7" in plain and "| Legend says only a natural 20 can summon a merchant to" in plain
    assert plain.splitlines()[0].strip() == render.banner(False).splitlines()[0].strip()
    assert "skitters off the table" in render.merchant_roll("b", merchant.Meeting(1, 20))
    assert "rattles in the distance" in render.merchant_roll("b", merchant.Meeting(15, 20))
    assert "Legend says only an 11 or higher can summon a" in render.merchant_roll("b", merchant.Meeting(3, 11))
    assert "Legend says no roll can summon a merchant to your" in render.merchant_roll("b", merchant.Meeting(3, 21))
    for roll in (8, 11, 18):
        assert f"Rolled an {roll}" in render.merchant_roll("b", merchant.Meeting(roll, 20))
    nobody = render.merchant_roll("b", merchant.Meeting(20, 20))
    assert "a natural 20! Wheels creak" in nobody and "NO SALE" in nobody and "nobody had anything to sell" in nobody
    lucky = render.merchant_roll("b", merchant.Meeting(12, 11))
    assert "It lands on 12. Wheels creak, and a cart pulls up." in lucky and "natural 20" not in lucky
    sold = render.merchant_roll("b", merchant.Meeting(20, 20, (Character.create("a"), None)))
    assert "a natural 20!" in sold and "+---" not in sold and "nobody" not in sold


def test_the_d20_is_pixel_art_coloured_by_the_roll():
    for roll, ramp in ((1, dice.RAMPS["red"]), (7, dice.RAMPS["gold"]), (20, dice.RAMPS["green"])):
        assert dice.ramp_for(roll) == ramp
        out = render.merchant_roll("b", merchant.Meeting(roll, 20), True)
        assert f"38;5;{ramp[4]}" in out and "\u2580" in out
        assert esc(str(roll), ramp[4], True) in out
    assert render.merchant_roll("b", merchant.Meeting(7, 20), Presentation(color=False)) == render.merchant_roll("b", merchant.Meeting(7, 20))


def test_the_d20_grid_is_a_symmetric_outlined_die_with_the_roll_as_text():
    for roll in (1, 7, 13, 20):
        g = dice.grid(roll)
        assert len(g) == dice.H and all(len(r) == dice.W for r in g)
        assert [[p is None for p in r] for r in g] == [[p is None for p in reversed(r)] for r in g]
        assert all(p.color == dice.EDGE for r in g for p in r[:1] + r[-1:] if p)
        lab = dice.label(roll)
        assert lab.text == str(roll) and lab.y % 2 == 0
        assert all(g[lab.y][lab.x + i].color == dice.ramp_for(roll)[5] for i in range(len(lab.text)))
        assert abs((lab.x + (len(lab.text) - 1) / 2) - (dice.W - 1) / 2) <= 0.5
    assert "13" in dice.d20(13, False) and "7" in dice.d20(7, False)
    coloured = dice.d20(13, True)
    assert f"\x1b[1;38;5;{dice.INK};48;5;{dice.RAMPS['gold'][5]}m13\x1b[0m" in coloured


def test_the_roll_markdown():
    assert render.merchant_roll_md(merchant.Meeting(7, 20)) == "Rolled a 7 (legend says only a natural 20 can summon a merchant to your location)"
    assert render.merchant_roll_md(merchant.Meeting(20, 20)) == "Rolled a 20 (the merchant came), but found nobody with anything to sell"
    assert render.merchant_roll_md(merchant.Meeting(20, 20, (Character.create("a"), None))) == "Rolled a 20 (the merchant came)"
    assert "Rolled a 7" in render.merchant_miss_md("ci[bot]", merchant.Meeting(7, 20))


@pytest.fixture()
def bot_env(monkeypatch, tmp_path):
    for v in ("GITHUB_SHA", "GITHUB_REPOSITORY", "QUESTOPS_MERCHANT_ODDS", "GITHUB_RUN_ID", "QUESTOPS_PLAYER", "GITHUB_ACTOR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "sum.md"))
    return tmp_path


def _bot(data, *extra):
    return cli.main(["quest", "--data-dir", str(data), "--outcome", "success", "--player", "dependabot[bot]", *extra])


def test_bot_miss_shows_the_roll_and_records_it(bot_env, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_SHA", _sha_with_roll(7))
    assert _bot(bot_env / "d") == 0
    out = capsys.readouterr().out
    assert "dependabot[bot] rolls a d20 for the Traveling Merchant." in out and "It lands on 7." in out
    assert "Legend says only a natural 20 can summon a merchant to" in out and "living adventurers" not in out
    assert "Rolled a 7 (legend says only a natural 20 can summon a merchant to your location)" in (bot_env / "sum.md").read_text(encoding="utf-8")
    written = (bot_env / "out.txt").read_text(encoding="utf-8")
    assert "merchant_roll=7" in written and "encounter=skipped" in written


def test_bot_nat_20_with_nobody_to_sell_to(bot_env, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_SHA", _sha_with_roll(20))
    assert _bot(bot_env / "d") == 0
    out = capsys.readouterr().out
    assert "It lands on 20, a natural 20!" in out and "nobody had anything to sell" in out and "Sold " not in out
    assert "merchant_roll=20" in (bot_env / "out.txt").read_text(encoding="utf-8")


def test_bot_nat_20_summons_the_merchant_and_dry_run_saves_nothing(bot_env, monkeypatch, capsys):
    store = Store(bot_env / "d")
    ch = Character.create("ada")
    ch.cls, ch.inventory = "Rogue", ["Hard Reset [rare]"]  # a Fighter weapon stays in a Rogue's bag
    store.save(ch)
    monkeypatch.setenv("GITHUB_SHA", _sha_with_roll(20))
    assert _bot(bot_env / "d", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "It lands on 20, a natural 20!" in out and "A Traveling Merchant, summoned by dependabot[bot], bumps into ada!" in out
    assert out.count("Quest:") <= 1 and out.count(render.banner(False).splitlines()[0].strip()) == 1
    assert not (bot_env / "d" / "log").exists() and store.load("ada").inventory == ["Hard Reset [rare]"]
    assert _bot(bot_env / "d") == 0
    assert "Rolled a 20 (the merchant came)" in (bot_env / "sum.md").read_text(encoding="utf-8")
    assert "merchant_roll=20" in (bot_env / "out.txt").read_text(encoding="utf-8")
    assert store.load("ada").inventory == []


def test_forced_roll_hook(monkeypatch, tmp_path):
    monkeypatch.delenv("QUESTOPS_MERCHANT_ODDS", raising=False)
    store = Store(tmp_path)
    ch = Character.create("ada")
    ch.inventory = ["Rusty Dagger [common]"]
    store.save(ch)
    monkeypatch.setenv("QUESTOPS_MERCHANT_ROLL", "20")
    m = merchant.visit(store, "any-key")
    assert m.roll == 20 and m.summoned and m.found and m.found[0].name == "ada"
    monkeypatch.setenv("QUESTOPS_MERCHANT_ROLL", "99")
    assert merchant.forced_roll() == 20
    monkeypatch.setenv("QUESTOPS_MERCHANT_ROLL", "-3")
    assert merchant.forced_roll() == 1
    monkeypatch.setenv("QUESTOPS_MERCHANT_ROLL", "nat twenty")
    assert merchant.forced_roll() is None
    monkeypatch.delenv("QUESTOPS_MERCHANT_ROLL")
    assert merchant.forced_roll() is None


def test_money_rolls_balances_up_into_toh():
    from questops.state import money
    assert money(9_999) == "9,999 'kens" and money(0) == "0 'kens"
    assert money(10_000) == "1 toh" and money(10_000, False) == "1 toh"
    assert money(12_345) == "1 toh 2,345 'kens" and money(12_345, False) == "1 toh 2,345"
    from questops.render import purse
    assert "\x1b[1;38;5;250m1 toh" in purse(12_345, True) and "\x1b[38;5;172m2,345 'kens" in purse(12_345, True)
    assert purse(10_000, False) == "\u25cf 1 toh" and purse(500, False, " total") == "\u25cf 500 'kens total"
    assert money(1_234_567) == "123 toh 4,567 'kens"
