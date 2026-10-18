import xml.etree.ElementTree as ET

from questops import items, pages, scenes
from questops.engine import MONSTERS, TIERS
from questops.lore import ITEM_EFFECTS, LORE, ROOM_LORE, ROOM_VARIANTS
from questops.sprites import ITEM_SPRITES, MONSTER_TIERS, SPRITES
from questops.state import Store, slug


def test_every_monster_and_item_has_lore_art_and_pages(tmp_path):
    files = pages.lore_files()
    index = files["lore/README.md"]
    for m in MONSTERS:
        assert LORE[m[0]][0] == "monster" and LORE[m[0]][1] in SPRITES
        assert f"lore/monsters/{slug(m[0])}.md" in files and f"monsters/{slug(m[0])}.md" in index
        for suffix in pages.TIER_SLUG[: len(TIERS)]:
            assert f"lore/img/{slug(m[0])}{suffix}.svg" in files
    for it in items.ITEMS:
        name, category = it.name, it.category
        assert LORE[name][0] == "item" and category in ITEM_SPRITES
        assert f"lore/items/{slug(name)}.md" in files and f"items/{slug(name)}.md" in index
        assert f"lore/img/{slug(name)}.svg" in files
    assert "Mimic" in LORE and "lore/monsters/mimic.md" in files
    assert set(ITEM_EFFECTS) <= {i.name for i in items.ITEMS}
    assert set(MONSTER_TIERS) <= set(SPRITES)
    for path, content in files.items():
        if path.endswith(".svg"):
            ET.fromstring(content)
        else:
            assert content.lstrip().startswith(("#", "<p"))


def test_every_room_has_lore_a_picture_and_a_page():
    files = pages.lore_files()
    index = files["lore/README.md"]
    assert set(scenes.SCENES) == set(ROOM_LORE)
    for name, (title, lore) in ROOM_LORE.items():
        assert lore.count(". ") == 1 and lore.endswith(".")  # two sentences, as everywhere else
        assert files[f"lore/rooms/{name}.md"].startswith(f"# {title}") and f"rooms/{name}.md" in index
        assert f"lore/img/room-{name}.svg" in files and lore in index
    for variant, (base, text) in ROOM_VARIANTS.items():
        assert base in ROOM_LORE and f"lore/img/room-{variant}.svg" in files and text in files[f"lore/rooms/{base}.md"]
        assert variant in scenes.BACKDROPS
    assert "changes nothing about the fight" in files["lore/rooms/corridor.md"]


def test_effect_items_show_their_effect_on_the_page(tmp_path):
    files = pages.lore_files()
    for name, effect in ITEM_EFFECTS.items():
        assert effect in files[f"lore/items/{slug(name)}.md"]


def test_lore_is_static_so_quests_never_touch_it():
    files = pages.lore_files()
    assert files == pages.lore_files()
    text = "\n".join(c for c in files.values())
    for dynamic in ("Slain by", "Equipped by", "In the bag of", "History", "not met yet"):
        assert dynamic not in text


def test_every_tier_has_its_own_taunt():
    import random

    from questops import engine
    from questops.engine import MONSTERS, TIERS
    from questops.state import Character

    for m in MONSTERS:
        assert len(m[9]) == len(TIERS) and len(set(m[9])) == len(TIERS), m[0]
    heard = {}
    for n in range(400):
        ch = Character.create("taunt-probe")
        ch.level = 12
        r = engine.run_encounter(ch, True, random.Random(n), "combat")
        mon = next(m for m in MONSTERS if r.foe.endswith(m[0]))
        heard[(mon[0], r.tier)] = any(e.text == f'"{mon[9][r.tier]}"' for e in r.transcript if hasattr(e, "text"))
    assert heard and all(heard.values())
    assert {t for _, t in heard} == {0, 1, 2}
