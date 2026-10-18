import random
import re

import pytest

from questops import art, engine, pixels, render, sprites, title
from questops.pixels import HALF, PLAIN, SOLID, SQUARE, Label, Px, Square, backend_for, emit
from questops.presentation import Presentation
from questops.state import Character

ANSI = re.compile(r"\x1b\[[0-9;]*m")
SGR = re.compile(r"\x1b\[([0-9;]*)m")


def decode(s: str) -> list[tuple]:
    """Per-cell (fg, bg, glyph) of an ANSI string."""
    fg = bg = None
    cells, pos = [], 0
    for m in SGR.finditer(s):
        cells += [(fg, bg, ch) for ch in s[pos : m.start()]]
        pos = m.end()
        p = m.group(1).split(";")
        i = 0
        while i < len(p):
            if p[i] in ("", "0"):
                fg = bg = None
            elif p[i] == "38":
                fg, i = int(p[i + 2]), i + 2
            elif p[i] == "48":
                bg, i = int(p[i + 2]), i + 2
            i += 1
    return cells + [(fg, bg, ch) for ch in s[pos:]]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in ("NO_COLOR", "QUESTOPS_COLOR", "FORCE_COLOR", "GITHUB_ACTIONS", "GITLAB_CI", "QUESTOPS_PIXELS"):
        monkeypatch.delenv(v, raising=False)


def test_emit_coalesces_runs_into_one_escape_pair():
    cells = [(1, 2, "\u2580")] * 3 + [(None, None, " ")] + [(1, 2, "\u2580")] + [(5, None, "\u2584")] * 2
    out = emit(cells)
    assert out == "\x1b[38;5;1;48;5;2m\u2580\u2580\u2580\x1b[0m \x1b[38;5;1;48;5;2m\u2580\x1b[0m\x1b[38;5;5m\u2584\u2584\x1b[0m"
    assert decode(out) == cells
    assert emit([]) == "" and emit([(None, None, "a"), (None, None, "b")]) == "ab"


@pytest.mark.parametrize("backend", [HALF, SOLID, SQUARE])
def test_backends_emit_one_escape_per_run_of_equal_cells(backend):
    flat = [[Px(9)] * 6, [Px(9)] * 6]
    (line,) = backend.draw(flat)[:1]
    assert line.count("\x1b[") == 2  # one escape and one reset
    assert len(ANSI.sub("", line)) == 6 * backend.cell_width


def test_half_cells():
    rows = [[Px(1), Px(2), None, None], [Px(3), None, Px(4), None]]
    assert decode(HALF.draw(rows)[0]) == [(1, 3, "\u2580"), (2, None, "\u2580"), (4, None, "\u2584"), (None, None, " ")]


def test_half_pads_an_odd_grid():
    assert len(HALF.draw([[Px(1)]] * 3)) == 2


def test_square_cells_are_non_space_glyphs_with_matching_fg_and_bg():
    rows = [[Px(7), None], [None, Px(8)]]
    lines = SQUARE.draw(rows)
    assert len(lines) == 2  # one text row per pixel row
    assert decode(lines[0]) == [(7, 7, "\u2580")] * 2 + [(None, None, " ")] * 2
    assert decode(lines[1]) == [(None, None, " ")] * 2 + [(8, 8, "\u2580")] * 2
    assert all("\x1b[38;5;7;48;5;7m" in ln or "7" not in ln for ln in lines)
    assert decode(Square(3).draw([[Px(1)]])[0]) == [(1, 1, "\u2580")] * 3


def test_plain_shade_and_block_rules():
    eye, teeth, void = Px(1, 5, "E"), Px(1, 5, "T"), Px(1, 0, "M")
    rows = [[eye, teeth, void, Px(1, 0), None], [None, None, void, Px(1, 5), None]]
    assert PLAIN.draw(rows) == ["@v \u2592 "]
    shadow, solid = Px(9, kind="S"), Px(9)
    block = PLAIN.draw([[solid, solid, None, shadow, None], [solid, None, solid, None, None]], plain="block")
    assert block == ["\u2588\u2580\u2584\u2591 "]


def test_labels_are_bold_text_on_the_pixel_colour_in_every_backend():
    rows = [[Px(3)] * 4, [Px(3)] * 4, [Px(5)] * 4, [Px(5)] * 4]
    on_row_2 = Label(2, 1, "42", 232)
    half = HALF.draw(rows, labels=(on_row_2,))
    assert "42" not in half[0] and "\x1b[1;38;5;232;48;5;5m42\x1b[0m" in half[1]
    square = SQUARE.draw(rows, labels=(on_row_2,))
    assert decode(square[2])[2] == (232, 5, "4") and decode(square[2])[4] == (232, 5, "2")
    assert "4" not in ANSI.sub("", square[1])
    gap = Label(0, 0, "x", 232)
    assert HALF.draw([[None, Px(1)], [None, Px(1)]], labels=(gap,))[0].startswith("\x1b[1;38;5;232mx")
    assert PLAIN.draw(rows, labels=(on_row_2,)) == ["\u2591\u2591\u2591\u2591", "\u259142\u2591"]


def test_backend_choice_follows_colour_and_env(monkeypatch):
    assert backend_for(False) is PLAIN and backend_for(True) is HALF and backend_for(SQUARE) is SQUARE
    monkeypatch.setenv("GITHUB_ACTIONS", "true")  # GitHub's log viewer smears two-colour cells
    assert backend_for(True) is SOLID
    for name, backend in pixels.BACKENDS.items():
        monkeypatch.setenv("QUESTOPS_PIXELS", name.upper())
        assert backend_for(True) is backend
    monkeypatch.setenv("QUESTOPS_PIXELS", "square")
    assert backend_for(False) is PLAIN  # NO_COLOR wins
    monkeypatch.setenv("QUESTOPS_PIXELS", "nonsense")
    assert backend_for(True) is SOLID
    monkeypatch.delenv("GITHUB_ACTIONS")
    assert backend_for(True) is HALF


def test_solid_cells_are_one_colour_and_keep_features():
    eye, teeth, void, body, ground = Px(1, kind="E"), Px(2, kind="T"), Px(3, kind="M"), Px(4), Px(5, kind="S")
    rows = [[eye, body, void, ground, body, None, ground], [body, teeth, body, body, None, body, None]]
    cells = decode(SOLID.draw(rows)[0])
    assert cells == [(1, 1, "\u2580"), (2, 2, "\u2580"), (3, 3, "\u2580"), (4, 4, "\u2580"), (4, 4, "\u2580"), (4, 4, "\u2580"), (5, 5, "\u2580")]
    assert decode(SOLID.draw([[Px(4), Px(6)], [Px(7), None]])[0])[0] == (4, 4, "\u2580")  # ties keep the top
    assert decode(SOLID.draw([[None], [None]])[0]) == [(None, None, " ")]
    labelled = SOLID.draw([[Px(9)] * 3, [Px(9)] * 3], labels=(Label(0, 1, "x", 232),))[0]
    assert "\x1b[1;38;5;232;48;5;9mx\x1b[0m" in labelled


@pytest.mark.parametrize("backend", [HALF, SOLID, SQUARE, PLAIN])
def test_sprite_shadow_title_icons_and_avatar_draw_through_every_backend(backend):
    pieces = [
        sprites.sprite("dragon", backend, 2),
        sprites.shadow(10, backend),
        title.title(backend),
        "\n".join(sprites.item_icon("ring", backend)),
        sprites.merchant_sprite("x[bot]", backend),
        "\n".join(render.avatar_lines(Character.create("ada"), backend)),
    ]
    for p in pieces:
        assert p.strip() and (("\x1b" in p) is backend.colored)
    assert len(sprites.shadow(10, backend).split("\n")) == (2 if backend is SQUARE else 1)


def test_square_sprite_is_twice_as_wide_and_as_tall_as_half():
    half, square = sprites.sprite("goblin", HALF).split("\n"), sprites.sprite("goblin", SQUARE).split("\n")
    assert len(square) == 2 * len(half)
    assert art.visible_len(square[0]) == 2 * art.visible_len(half[0])


def test_title_plain_is_stripped_and_every_cell_is_one_colour():
    assert all(ln == ln.rstrip() for ln in title.title(PLAIN).split("\n"))
    for backend in (HALF, SOLID, SQUARE):
        lines = title.title(backend).split("\n")
        assert len(lines) == 6
        assert all(fg == bg for ln in lines for fg, bg, _ in decode(ln) if fg is not None)


def _won(kind="combat", seed="sq"):
    ch = Character.create("ada")
    return ch, engine.run_encounter(ch, True, random.Random(seed), kind)


def test_square_transcript_never_truncates_and_centres_the_sprite():
    ch, r = _won()
    r.title = "Slew the Skip Level Ancient Wyrm of Legacy Prod and a long tail of other things"
    pres = Presentation(color=True, pixels=SQUARE)
    text = render.transcript(ch, r, "o/r / ci", pres)
    plain = ANSI.sub("", text)
    assert "\u2026" not in plain and r.title in plain
    box_lines = [ln for ln in plain.split("\n") if ln.startswith(("+", "|"))]
    width = len(box_lines[0])
    assert width > 62 and {len(ln) for ln in box_lines} == {width}
    art_ev = next(e for e in r.transcript if isinstance(e, engine.Art))
    block = sprites.sprite(art_ev.key, SQUARE, art_ev.tier)
    block_width = max(art.visible_len(ln) for ln in block.split("\n"))
    assert width > block_width
    assert art.center_block(block, width) in text  # centred in the card's width
    assert (width - block_width) // 2 > 0


def test_square_merchant_card_and_gear_rows_fit_the_box():
    ch = Character.create("ada")
    ch.main_hand, ch.accessory = "Hotfix [rare]", "Crown of the Main Branch [legendary]"
    ch2, r = _won("treasure")
    pres = Presentation(color=True, pixels=SQUARE)
    plain = ANSI.sub("", render.transcript(ch, r, "", pres))
    assert "\u2026" not in plain and "Hotfix" in plain and "Crown of the Main Branch" in plain
    from questops.merchant import Visit

    v = Visit("ada", [("Rusty Dagger [common]", 15)], 0)
    card = ANSI.sub("", render.merchant_card(ch, v, "x[bot]", pres))
    assert "\u2026" not in card and "Rusty Dagger" in card
    widths = {len(ln) for ln in card.split("\n") if ln.startswith(("+", "|"))}
    assert len(widths) == 1


def test_half_and_plain_keep_the_fixed_62_column_card():
    ch, r = _won()
    for pres in (Presentation(color=True), Presentation()):
        plain = ANSI.sub("", render.transcript(ch, r, "", pres))
        assert {len(ln) for ln in plain.split("\n") if ln.startswith(("+", "|"))} == {62}


def test_presentation_decides_features_in_one_place():
    live, dry = Presentation(color=True), Presentation(ephemeral=True)
    assert live.pixels is HALF and Presentation().pixels is PLAIN
    assert (live.show_stats, live.show_gear, live.narrated) == (True, True, False)
    assert (dry.show_stats, dry.show_gear, dry.narrated) == (False, False, True)
    assert Presentation.detect(color=False).pixels is PLAIN and Presentation.detect(ephemeral=True, color=True).ephemeral
