import random
import re

import pytest

from questops import engine, render, scenes
from questops.ci import Run
from questops.game import play
from questops.pixels import HALF, PLAIN, SQUARE, Half
from questops.presentation import Presentation
from questops.sprites import SPRITES, tier_ramps
from questops.state import Character, Store, seed_int

ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.mark.parametrize("name", scenes.SCENES)
def test_backdrops_fill_the_frame_with_xterm_256_colours(name):
    bg = scenes.backdrop(name)
    assert len(bg) == scenes.H and all(len(row) == scenes.W for row in bg)
    # 0-15 follow the terminal theme, so a backdrop never uses them
    assert all(16 <= c <= 255 for row in bg for c in row)
    assert len({c for row in bg for c in row}) > 10


def test_tier_lighting_tints_the_stone_but_not_saturated_colour():
    assert scenes.light((60, 60, 60), scenes.TIER_LIGHT[0]) == (60, 60, 60)
    r, g, b = scenes.light((60, 60, 60), scenes.TIER_LIGHT[1])
    assert b > r  # Senior: cold blue
    r, g, b = scenes.light((60, 60, 60), scenes.TIER_LIGHT[2])
    assert r > g  # Skip Level: red-violet
    assert scenes.light((255, 0, 0), scenes.TIER_LIGHT[2]) == (255, 0, 0)
    assert scenes.light((0, 0, 0), scenes.TIER_LIGHT[0]) == (0, 0, 0)
    assert len({scenes.backdrop("stairs", t) for t in range(3)}) == 3


def test_quantize_dithers_toward_the_nearest_palette_colour():
    assert scenes.quantize((0, 0, 0), 0, 0, spread=0) == 16
    assert scenes.quantize((255, 255, 255), 0, 0, spread=0) == 231
    assert scenes.quantize((128, 128, 128), 0, 0, spread=0) >= 232


@pytest.mark.parametrize("key", ["goblin", "slime", "wraith", "dragon", "mimic"])
@pytest.mark.parametrize("name", scenes.SCENES)
def test_compose_stands_the_sprite_on_the_floor_with_an_outline_and_shadow(name, key):
    rows = scenes.compose(name, SPRITES[key], tier_ramps(key, 0))
    assert len(rows) == scenes.H and all(len(r) == scenes.W for r in rows)
    kinds = {p.kind for r in rows for p in r}
    assert {"G", "O", "S"} <= kinds
    assert any(p.kind not in "GOS" for p in rows[scenes.FLOOR])  # feet on the floor row
    assert all(p.kind in "GOS" for p in rows[scenes.FLOOR + 1])  # below the feet: floor, outline and shadow only


def test_odd_height_sprites_stand_on_their_last_drawn_row():
    rows = scenes.compose("corridor", ["BBB", "BEB", "BBB"], tier_ramps("goblin", 0))
    assert rows[scenes.FLOOR][scenes.W // 2].kind == "B"


@pytest.mark.parametrize("backend, lines, width", [(HALF, scenes.H // 2, scenes.W), (SQUARE, scenes.H, scenes.W * 2)])
def test_staged_draws_through_colour_backends(backend, lines, width):
    out = scenes.staged("torches", SPRITES["goblin"], tier_ramps("goblin", 2), backend).split("\n")
    assert len(out) == lines and max(len(ANSI.sub("", ln)) for ln in out) == width


def test_pick_scene_is_stable_and_uses_every_scene():
    assert scenes.pick_scene("a") == scenes.pick_scene("a")
    assert {scenes.pick_scene(str(n)) for n in range(50)} == set(scenes.SCENES)


def test_play_picks_a_scene_without_changing_the_dice(tmp_path):
    q = play(Store(tmp_path), "ada", True, kind="combat", seed="s", context="", run=Run("", "", False, "local"))
    assert q.result.scene == scenes.pick_scene("s")
    bare = engine.run_encounter(Character.create("ada"), True, random.Random(seed_int("s")), "combat")
    assert [e.text for e in bare.transcript] == [e.text for e in q.result.transcript]


def test_transcript_draws_monsters_in_their_scene_only_with_colour():
    ch = Character.create("ada")
    r = engine.run_encounter(ch, True, random.Random("r"), "combat")
    art = r.transcript[0]
    first = scenes.staged("stairs", SPRITES[art.key], tier_ramps(art.key, art.tier), HALF).split("\n")[0]
    r.scene = "stairs"
    assert first in render.transcript(ch, r, pres=Presentation(color=True, pixels=HALF))
    assert "\x1b[" not in render.transcript(ch, r, pres=Presentation(pixels=PLAIN))
    r.scene = ""
    assert first not in render.transcript(ch, r, pres=Presentation(color=True, pixels=HALF))


def test_chests_and_traps_stand_alone():
    assert "chest" not in render.STAGED and "trap" not in render.STAGED
    assert {m[1] for m in engine.MONSTERS} | {"mimic"} == render.STAGED


@pytest.mark.parametrize("name", scenes.SCENES + ("bluestone",))
def test_solid_backdrops_give_each_text_cell_one_colour(name):
    bg = scenes.backdrop(name, 0, solid=True)
    assert len(bg) == scenes.H and all(a == b for a, b in zip(bg[::2], bg[1::2]))


def test_castle_goes_blue_behind_foes_that_clash_with_red_brick():
    assert scenes.suit("castle", "slime") == scenes.suit("castle", "dragon") == "bluestone"
    assert scenes.suit("castle", "goblin") == scenes.suit("castle", "wraith") == "castle"
    assert scenes.suit("corridor", "slime") == "corridor"
    assert scenes.backdrop("bluestone") != scenes.backdrop("castle")


def test_solid_cells_keep_the_sprite_over_scene_outlines_and_backdrop():
    from questops.pixels import SOLID, Px

    body, outline, backdrop, shadow = Px(40, 0, ""), Px(16, 0, "O"), Px(20, 0, "G"), Px(30, 0, "S")
    for top, bot in ((outline, body), (body, outline), (backdrop, body), (body, backdrop), (shadow, body)):
        assert SOLID.draw([[top], [bot]])[0].startswith("\x1b[38;5;40;48;5;40m")
    assert SOLID.draw([[outline], [shadow]])[0].startswith("\x1b[38;5;16;48;5;16m")
    assert SOLID.draw([[body], [Px(0, 0, "E")]])[0].startswith("\x1b[38;5;0;48;5;0m")


def test_staged_averages_rows_for_a_solid_backend():
    class Solid(Half):
        name = "solid"

    solid = scenes.staged("castle", SPRITES["slime"], tier_ramps("slime", 0), Solid())
    assert solid != scenes.staged("castle", SPRITES["slime"], tier_ramps("slime", 0), HALF)
