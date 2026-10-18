from questops import avatar, render
from questops.state import CLASS_STATS, Character


def test_stats_are_derived_from_level():
    ch = Character.create("newbie")
    assert ch.level == 1 and ch.gray == ch.natural_gray + CLASS_STATS[ch.cls]["gray"] == 2 + CLASS_STATS[ch.cls]["gray"]
    before = (ch.hp_max, ch.mp_max, ch.gray)
    ch.level_up()
    assert (ch.hp_max, ch.mp_max, ch.gray) > before


def test_class_and_avatar_are_always_generated_from_the_name():
    a, b = Character.create("octocat"), Character.create("octocat")
    assert a.cls == b.cls
    rows, ramps = avatar.portrait("octocat", a.cls)
    assert avatar.portrait("octocat", a.cls) == (rows, ramps)
    assert avatar.portrait("octocat", "Rogue")[0] != avatar.portrait("octocat", "Wizard")[0]
    assert len(rows) == avatar.ROWS and all(len(r) == avatar.HALF for r in rows)
    assert len(render.avatar_lines(a, False)) == avatar.ROWS // 2


def test_classes_start_differently():
    from questops.state import CLASS_STATS

    stats = {}
    for cls in CLASS_STATS:
        ch = Character.create("t")
        ch.cls = cls
        stats[cls] = (ch.hp_max, ch.mp_max, ch.gray)
    assert stats["Fighter"][0] > stats["Rogue"][0] > stats["Wizard"][0]  # sturdiness
    assert stats["Wizard"][1] > stats["Rogue"][1] > stats["Fighter"][1]  # mana
    assert stats["Rogue"][2] > stats["Wizard"][2] > stats["Fighter"][2]  # sharpness
