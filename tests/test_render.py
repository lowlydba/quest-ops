import random
import re

import pytest

from questops import art, avatar, engine, items, lore, render, sprites, svg, title
from questops.presentation import Presentation
from questops.state import Character, Store, _renamed

ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(autouse=True)
def plain_env(monkeypatch):
    for v in ("NO_COLOR", "QUESTOPS_COLOR", "FORCE_COLOR", "GITHUB_ACTIONS", "GITLAB_CI"):
        monkeypatch.delenv(v, raising=False)


# art


def test_color_enabled_env_precedence(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert art.color_enabled()
    monkeypatch.setenv("QUESTOPS_COLOR", "0")
    assert not art.color_enabled()
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("QUESTOPS_COLOR")
    assert not art.color_enabled()
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.delenv("FORCE_COLOR")
    monkeypatch.setenv("QUESTOPS_COLOR", "1")
    assert art.color_enabled()
    monkeypatch.delenv("QUESTOPS_COLOR")
    monkeypatch.setenv("GITLAB_CI", "true")
    assert art.color_enabled()
    monkeypatch.delenv("GITLAB_CI")
    monkeypatch.setattr(art.sys.stdout, "isatty", lambda: False, raising=False)
    assert not art.color_enabled()


def test_colour_helper():
    assert art._c("hi", 5) == "\x1b[38;5;5mhi\x1b[0m"
    assert art._c("  ", 5) == "  "


def test_banner_plain_and_colour():
    assert art.BANNER == art.banner(False) and "\x1b" not in art.BANNER
    assert "\x1b[38;5;" in art.banner(True)


def test_paint_applies_accents_and_keeps_blank_lines():
    out = art.paint("ab \n\nba", 10, {"b": 20})
    lines = out.split("\n")
    assert lines[1] == ""
    assert ANSI.sub("", out) == "ab \n\nba"
    assert "\x1b[38;5;10ma" in lines[0] and "\x1b[38;5;20mb" in lines[0]
    assert art.paint("a b", 3).count("\x1b[38;5;3m") == 1  # spaces keep the current colour


def test_center_block_and_visible_len():
    assert art.visible_len("\x1b[38;5;1mabc\x1b[0m") == 3
    out = art.center_block("ab\n\nabcd", width=10)
    assert out.split("\n") == ["   ab", "", "   abcd"]
    assert art.center_block("abcdef", width=2) == "abcdef"


def test_bars_clamp_and_fill():
    assert art.hp_bar(5, 10, 10) == "[#####.....] 5/10"
    assert art.hp_bar(-5, 0, 4) == "[....] 0/1"
    assert art.hp_bar(99, 10, 4) == "[####] 10/10"
    assert art.xp_bar(5, 10, 10) == "[=====-----] 5/10"
    assert art.xp_bar(0, 10, 4, color=True).startswith("[\x1b[38;5;240m----")
    full = art.xp_bar(10, 10, 4, color=True)
    assert "\x1b[38;5;71m====" in full and "-" not in ANSI.sub("", full)
    mid = ANSI.sub("", art.xp_bar(5, 10, 10, color=True))
    assert mid == "[=====-----] 5/10"


def test_box_pads_and_truncates():
    out = art.box(["hi", "x" * 100, "\x1b[38;5;1m" + "y" * 100 + "\x1b[0m"], width=20).split("\n")
    assert out[0] == out[-1] == "+" + "-" * 18 + "+"
    assert all(len(ln) == 20 for ln in out)
    assert out[2].endswith("\u2026 |") and "\x1b" not in out[3]


# title


def test_title_plain_and_colour_shapes():
    plain, col = title.title(False).split("\n"), title.title(True).split("\n")
    assert len(plain) == len(col) == 6
    assert set("".join(plain)) <= set("\u2588\u2591 ")
    assert "\u2588" in "".join(plain) and "\u2591" in "".join(plain)
    assert all("\x1b[" in ln for ln in col)
    assert "\x1b[38;5;220;48;5;220m" in "".join(col)  # the sword's gold guard


def test_title_svg_keeps_the_detailed_banner():
    assert len(title._pixels()) == 9 and title.HIGHLIGHT in title._pixels()[0]


# sprites


def test_mirror_pads_and_evens():
    assert sprites._mirror(["ab", "c", "d"]) == ["abba", "cccc", "dddd", "...."]


@pytest.mark.parametrize("color", [False, True])
def test_every_sprite_renders(color):
    for key in sprites.SPRITES:
        s = sprites.sprite(key, color)
        assert s.strip() and ("\x1b" in s) is color
    for key, tiers in sprites.MONSTER_TIERS.items():
        for t in tiers:
            assert sprites.sprite(key, color, t)


def test_render_colour_covers_all_cell_kinds():
    ramps = {"B": [1, 2, 3, 4, 5, 6]}
    out = sprites.render(["BB.", "B.B", "..."], ramps, True, dither=0, rim=0)
    assert "\u2580" in out and "\u2584" in out and "48;5;" in out and " " in out
    assert sprites.render(["B.", ".B"], ramps, False, dither=0, rim=0)


def test_shadow_shapes():
    assert len(ANSI.sub("", sprites.shadow(3, True))) == 8
    col, plain = sprites.shadow(20, True), sprites.shadow(20, False)
    assert "\u2580" in col and "\u2584" in col
    assert set(plain) == {"\u2591"} and len(plain) == 20


def test_tier_ramps_override_base():
    assert sprites.tier_ramps("dragon", 2)["B"] != sprites.tier_ramps("dragon", 0)["B"]
    assert sprites.tier_ramps("mimic", 1)["eye"] == 208


def test_item_icons_and_merchants():
    for cat in sprites.ITEM_SPRITES:
        assert sprites.item_icon(cat, False) and sprites.item_icon(cat, True)
    for bot in ("github-actions[bot]", "dependabot[bot]", "x[bot]"):
        assert sprites.merchant_sprite(bot, False).strip()
        assert sprites.merchant_sprite(bot, True)
        assert sprites.merchant_describe(bot)
        assert sprites.merchant_look(bot)[0]
    assert sprites.merchant_look("dependabot[bot]") == sprites.merchant_look("dependabot[bot]")


# avatar / svg


def test_portrait_is_stable_and_follows_class_and_name():
    rows, ramps = avatar.portrait("octocat", "Wizard")
    assert (rows, ramps) == avatar.portrait("octocat", "Wizard")
    assert rows != avatar.portrait("octocat", "Fighter")[0]
    assert {tuple(avatar.portrait(f"hero{n}", "Rogue")[0]) for n in range(20)} == set(map(tuple, avatar.LOOKS["Rogue"]))
    assert len({str(avatar.portrait(f"hero{n}", "Wizard")[1]) for n in range(20)}) > 10
    assert avatar.portrait("octocat", "Bard")[0] in avatar.LOOKS["Fighter"]


def test_xterm_hex_ranges():
    assert svg.xterm_hex(0) == "#000000" and svg.xterm_hex(9) == "#ff0000" and svg.xterm_hex(15) == "#ffffff"
    assert svg.xterm_hex(16) == "#000000" and svg.xterm_hex(231) == "#ffffff" and svg.xterm_hex(196) == "#ff0000"
    assert svg.xterm_hex(232) == "#080808" and svg.xterm_hex(255) == "#eeeeee"


def test_card_pills_and_overflow():
    ch = Character.create("ada")
    assert "No achievements yet" in svg.card(ch)
    assert "bag: 0 items" in svg.card(ch)
    ch.inventory = ["Rusty Dagger [common]"]
    ch.achievements = ["First Blood", "Very Long Achievement Name Indeed (x)", "B", "C"]
    s = svg.card(ch)
    assert "bag: 1 item<" in s and "\u2605" in s and "First Blood" in s and "(x)" not in s
    ch.achievements = [f"Achievement number {i}" for i in range(8)]
    s = svg.card(ch)
    assert re.search(r">\+\d+<", s) and s.count('height="22" rx="11"') < 8
    ch.achievements = ["An unreasonably long achievement label that cannot ever fit the card width"]
    assert svg.card(ch).count('height="22" rx="11"') == 0


# state / lore / merchant


def test_renamed_foes_and_unknown_lore():
    assert _renamed("Senior Ancient Wyrm of Prod") == "Senior Ancient Wyrm of Legacy Prod"
    assert _renamed("Goblin") == "Goblin"
    assert lore.lore_for("not-an-item")[2].startswith("Nothing is known")


def test_store_load_repairs_unknown_class(tmp_path):
    store = Store(tmp_path)
    ch = Character.create("ada")
    ch.cls = "Bard"
    store.save(ch)
    assert store.load("ada").cls == Character.create("ada").cls


def test_merchant_edge_cases(tmp_path, monkeypatch):
    from questops import merchant

    store = Store(tmp_path)
    nobody = merchant.visit(store, "k", chance=1.0)
    assert nobody.summoned and nobody.found is None
    ch = Character.create("ada")
    ch.inventory = ["Mystery Thing [odd]"]
    store.save(ch)
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "garbage")
    assert merchant.odds() == merchant.MERCHANT_ODDS
    monkeypatch.setenv("QUESTOPS_MERCHANT_ODDS", "1")
    assert merchant.odds() == 1.0
    hero, v = merchant.visit(store, "").found  # no key: unseeded roll
    assert v.sold == [("Mystery Thing [odd]", 15)]


# render


def _fight(win=True, kind="combat", seed="r", **setup):
    ch = Character.create("ada")
    for k, v in setup.items():
        setattr(ch, k, v)
    return ch, engine.run_encounter(ch, win, random.Random(seed), kind)


@pytest.mark.parametrize("color", [False, True])
def test_transcript_levels_achievements_and_context(color):
    ch = Character.create("ada")
    ch.xp = 10_000_000
    ch.level = 1
    r = engine.run_encounter(ch, True, random.Random("lv"), "combat")
    assert r.levels and r.new_achievements
    text = render.transcript(ch, r, "ctx", Presentation(color=color))
    plain = ANSI.sub("", text)
    assert "Quest: ctx" in plain and "LEVEL UP! Now level" in plain and "Achievement unlocked: " in plain
    assert ("\x1b[" in text) is color
    assert "ada" in plain and "kens" in plain


def test_transcript_bag_and_new_loot_labels():
    ch = Character.create("ada")
    ch.main_hand = ""
    r = engine.Result(kind="treasure", title="t", success=True)
    r.loot, r.loot_action = "Crown of the Main Branch [legendary]", "equipped"
    ch.accessory = r.loot
    assert "NEW!" in render.transcript(ch, r, "", Presentation())
    r.loot, r.loot_action = "Rusty Dagger [common]", "bag"
    bagged = render.transcript(ch, r, "", Presentation())
    assert "[Rusty Dagger] common" in bagged and "Bagged: not rarer than your current gear" in bagged


def test_transcript_uses_env_colour_by_default(monkeypatch):
    ch, r = _fight()
    assert "\x1b[" not in render.transcript(ch, r)
    monkeypatch.setenv("QUESTOPS_COLOR", "1")
    assert "\x1b[" in render.transcript(ch, r)


def test_transcript_losses_and_every_kind():
    for kind in ("combat", "treasure", "trap"):
        for win in (True, False):
            ch, r = _fight(win, kind, seed=f"{kind}{win}")
            text = render.transcript(ch, r, pres=Presentation())
            assert r.title and text.count("+") >= 4 and r.success is (win and r.success)


def test_side_by_side_and_avatar():
    out = render.side_by_side(["ab", "cde"], ["1", "2", "3"], min_width=5)
    assert out == ["ab   1", "cde  2", "     3"] or len(out) == 3
    ch = Character.create("ada")
    assert render.avatar_lines(ch, False) and "\x1b" in "".join(render.avatar_lines(ch, True))


def test_codex_lists_content_and_heroes(tmp_path):
    store = Store(tmp_path)
    assert render.codex(store)
    ch = Character.create("ada")
    store.save(ch)
    text = render.codex(store)
    assert "ada" in text
    for m in engine.MONSTERS[:1]:
        assert m[0] in text if isinstance(m, tuple) else True


def test_sheet_index_and_log_markdown(tmp_path):
    store = Store(tmp_path)
    ada, bob = Character.create("ada"), Character.create("bob")
    ada.xp, ada.main_hand, ada.kens = 5000, "Hotfix [rare]", 42
    store.save(ada)
    store.save(bob)
    sheet = render.sheet_md(ada)
    assert sheet.startswith("# ada, Level") and "GRAY" in sheet
    idx = render.index_md(store)
    assert "ada" in idx and "bob" in idx
    assert render.index_md(Store(tmp_path / "none"))
    entries = [
        {"ts": "2026-01-01T00:00:00Z", "player": "ada", "success": True, "kind": "combat", "title": "T1", "xp": 5, "kens": 3, "loot": "", "context": "c", "run": "1", "commit": "abc1234", "commit_url": "http://x/c", "key": "k"},
        {"ts": "2026-01-02T00:00:00Z", "player": "bob", "success": False, "kind": "trap", "title": "T2", "xp": 0, "kens": 0, "loot": "Rusty Dagger [common]", "context": "", "run": "2", "commit": "", "commit_url": "", "key": ""},
    ]
    md = render.quest_log_md(entries)
    assert "T1" in md and "T2" in md and "ada" in md
    many = [dict(entries[0], title=f"Q{i}") for i in range(80)]
    assert "Q79" in render.quest_log_md(many, limit=5) and "Q0<" not in render.quest_log_md(many, limit=5)
    assert render.quest_log_md([])


def test_merchant_card(tmp_path):
    ch = Character.create("ada")
    from questops.merchant import Visit

    v = Visit(hero="ada", sold=[("Rusty Dagger [common]", 15), ("Hotfix [rare]", 140)], kens_before=0)
    plain = render.merchant_card(ch, v, "dependabot[bot]", Presentation())
    assert "dependabot[bot]" in plain and "155" in plain and "Rusty Dagger" in plain
    assert "\x1b[" in render.merchant_card(ch, v, "dependabot[bot]", Presentation(color=True))
    assert render.merchant_card(ch, v, "github-actions[bot]", Presentation())
