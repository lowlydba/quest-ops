"""Lore pages for the data branch: a bestiary of monsters and a reliquary of items."""

from __future__ import annotations

from itertools import groupby

from . import items, merchant, scenes, spells, svg
from .engine import MONSTERS, TIERS
from .lore import CATEGORY_NOTES, ITEM_EFFECTS, LORE, ROOM_LORE, ROOM_VARIANTS, SPELL_LORE, TIER_LORE
from .sprites import ITEM_RAMPS, ITEM_SPRITES, MONSTER_RAMPS, SPRITES, _mirror, merchant_describe, merchant_look, tier_ramps
from .state import slug
from .svg import pixel_rects

SCALE = 10
ROOM_SCALE = 8
RARITY_BADGE = {"common": "\U0001F7E2", "uncommon": "\U0001F7E1", "rare": "\U0001F535", "legendary": "\U0001F7E3"}
TIER_SLUG = ["", "-senior", "-skip-level"]
TIER_LABEL = ["Base", "Senior", "Skip Level"]


def sprite_svg(kind: str, key: str, tier: int = 0) -> str:
    if kind == "monster":
        rows, ramps, dither, rim = SPRITES[key], tier_ramps(key, tier), 0.9, 1.6
    else:
        rows, ramps, dither, rim = ITEM_SPRITES[key], ITEM_RAMPS, 0.3, 0.6
    grid = _mirror(rows)
    w, h = len(grid[0]) * SCALE, len(grid) * SCALE
    body = pixel_rects(rows, ramps, 0, 0, SCALE, dither, rim)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges">{body}</svg>\n')


def merchant_svg(bot: str) -> str:
    rows, ramps = merchant_look(bot)
    grid = _mirror(rows)
    w, h = len(grid[0]) * SCALE, len(grid) * SCALE
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges">{pixel_rects(rows, ramps, 0, 0, SCALE, 0.9, 1.6)}</svg>\n')


def room_svg(name: str) -> str:
    """A scene's backdrop as a picture: the same colours the log draws, one rectangle per run of a colour."""
    rects = []
    for y, row in enumerate(scenes.backdrop(name)):
        x = 0
        for colour, run in groupby(row):
            n = len(list(run))
            rects.append(f'<rect x="{x * ROOM_SCALE}" y="{y * ROOM_SCALE}" width="{n * ROOM_SCALE}" height="{ROOM_SCALE}" fill="{svg.xterm_hex(colour)}"/>')
            x += n
    w, h = scenes.W * ROOM_SCALE, scenes.H * ROOM_SCALE
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges">{"".join(rects)}</svg>\n')


def _room_page(name: str) -> str:
    title, lore = ROOM_LORE[name]
    variants = [(v, text) for v, (base, text) in ROOM_VARIANTS.items() if base == name]
    extra = "".join(f"\n## Variant\n\n![{title}, in blue stone](../img/room-{v}.svg)\n\n{text}\n" for v, text in variants)
    return f"""# {title}

![{title}](../img/room-{name}.svg)

> {lore}

Rooms are scenery. Every foe stands in one, picked from a hash of the run's seed, and it changes nothing about the fight or the dice.
{extra}
[\u2190 Back to the lore](../README.md)
"""


def elder_svg() -> str:
    grid = _mirror(SPRITES["elder"])
    w, h = len(grid[0]) * SCALE, len(grid) * SCALE
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges">{pixel_rects(SPRITES["elder"], MONSTER_RAMPS["elder"], 0, 0, SCALE, 0.9, 1.6)}</svg>\n')


MERCHANT_BOTS = ["github-actions[bot]", "dependabot[bot]", "renovate[bot]", "copilot[bot]", "codecov[bot]", "snyk-bot"]


def _merchant_page() -> str:
    _, _, lore = LORE["Traveling Merchant"]
    prices = _table(["Rarity", "Pays"], [[r, f"{p} 'kens"] for r, p in items.SELL_PRICE.items()])
    rows = [[f'<img src="../img/{_merchant_img(b)}" width="72">', f"`{b}`", merchant_describe(b)] for b in MERCHANT_BOTS]
    return f"""# Traveling Merchant

![Traveling Merchant](../img/traveling-merchant.svg)

> {lore}

Bots are not heroes. A run by the Actions bot, Dependabot or the like does nothing almost every time, but with a {int(merchant.MERCHANT_ODDS * 100)}% chance a merchant bumps into a random hero and buys some of what is in their bag. Anything equipped is safe, and the sale is automatic. A hero with nothing at all gets a gift instead.

## \U0001F525 The old man
When the merchant finds a hero with empty hands, it sends someone else: an old man in a red robe, a flame on either side. He says it is dangerous to go alone and hands over a basic weapon for the hero's class, a Squeaky Mallet, Rusty Dagger or Intern's Staff.

<img src="../img/old-man.svg" width="96">

## \U0001FA99 Prices
{prices}

## \U0001F9D1\u200D\U0001F33E What each bot's name renders to
Every bot sends its own merchant. The Actions bot's is hand-drawn. All the others are generated from the bot's name, always with a hat and a beard, so they are never mistaken for a hero. Any bot not listed gets its own the same way.

{_table(["", "Bot name", "Look"], rows)}

[\u2190 Back to the lore](../README.md)
"""


def _merchant_img(bot: str) -> str:
    return "traveling-merchant.svg" if bot == "github-actions[bot]" else f"traveling-merchant-{slug(bot)}.svg"


def _table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _monster_page(name: str) -> str:
    _, key, lore = LORE[name]
    stats = next((m for m in MONSTERS if m[0] == name), None)
    variants = []
    for t, (prefix, hp_x, rw_x, _bonus, unlock) in enumerate(TIERS):
        img = f'<img src="../img/{slug(name)}{TIER_SLUG[t]}.svg" width="72">'
        if stats:
            variants.append([img, f"**{prefix}{name}**", f"level {max(stats[2], unlock)}", round(stats[3] * hp_x),
                             f"{round(stats[7] * rw_x)} XP, {round(stats[8] * rw_x)} 'kens", f'*"{stats[9][t]}"*'])
        else:
            variants.append([img, f"**{prefix}{name}**", f"level {unlock}", "-", "-"])
    if not stats:
        return f"""# {name}

![{name}](../img/{slug(name)}.svg)

> {lore}

Appears inside treasure chests, whenever the workflow fails. You can't slay one; you can only survive it.

## \U0001F396\ufe0f Variants
{_table(["", "Variant", "From", "HP", "Reward"], variants)}

The only difference between the variants is the look in their eyes.

[\u2190 Back to the bestiary](../README.md)
"""
    tier_lore = "\n".join(f"- **{TIERS[t][0].strip()}**: {text}" for t, text in TIER_LORE.items())
    return f"""# {name}

![{name}](../img/{slug(name)}.svg)

> {lore}

## \U0001F396\ufe0f Variants
{_table(["", "Variant", "From", "HP", "Reward", "Says"], variants)}

{tier_lore}

[\u2190 Back to the bestiary](../README.md)
"""


def _item_page(it: items.Item) -> str:
    name, rarity, cat = it.name, it.rarity, it.category
    _, _, lore = LORE[name]
    label = items.label(name, rarity)
    effect = f"\n**Effect:** {ITEM_EFFECTS[name]}\n" if name in ITEM_EFFECTS else ""
    if it.slot == "weapon":
        kind = f"{rarity.capitalize()} {cat} \u00b7 weapon for {it.klass}s only \u00b7 +{it.bonus} damage"
        note = f"\n{CATEGORY_NOTES[cat]}\n" if cat in CATEGORY_NOTES else ""
    else:
        kind, note = f"{rarity.capitalize()} {cat} \u00b7 accessory, any class", ""
    set_line = "".join(f"\n**Set:** part of [{s.name}](../README.md#-sets), with the {s.accessory if it.slot == 'weapon' else s.weapon}.\n"
                       for s in items.SETS if name in (s.weapon, s.accessory))
    return f"""# {name}

![{name}](../img/{slug(name)}.svg)

{RARITY_BADGE[rarity]} **{kind}**
{note}
> {lore}
{effect}{set_line}
[\u2190 Back to the reliquary](../README.md)
"""


def _spellbook_page() -> str:
    rows = [[f"**{s.name}**", s.level, s.mp, s.effect, SPELL_LORE[s.name]] for s in spells.SPELLS]
    return f"""# \U0001F4D6 Spellbook

Only Wizards cast, and only with a staff in the main hand. Spells unlock with hero level, and a Wizard picks from the ones unlocked each round. Fights last three rounds, and the last one always ends with Jade. The Staff of Regex takes 1 MP off every cast.

{_table(["Spell", "Unlocks", "MP", "Effect", "Lore"], rows)}

[\u2190 Back to the lore](README.md)
"""


def _wanderers() -> str:
    thumb = f'<img src="img/{_merchant_img("github-actions[bot]")}" width="72">'
    return _table(["", "Wanderer", "Appears"], [[thumb, "[Traveling Merchant](npcs/traveling-merchant.md)", "on bot runs (about 5%), buying what you are not wearing"]])


def lore_files() -> dict[str, str]:
    """Relative path -> content for every lore page and image.

    Lore is static: it depends only on the game content, never on who has played, so quests
    never change these files and concurrent runs cannot conflict over them."""
    files: dict[str, str] = {"banner.svg": svg.title_svg()}
    beasts = [m[0] for m in MONSTERS] + ["Mimic"]
    for name in beasts:
        key = LORE[name][1]
        files[f"lore/monsters/{slug(name)}.md"] = _monster_page(name)
        for t in range(len(TIERS)):
            files[f"lore/img/{slug(name)}{TIER_SLUG[t]}.svg"] = sprite_svg("monster", key, t)
    for name in ROOM_LORE:
        files[f"lore/rooms/{name}.md"] = _room_page(name)
        files[f"lore/img/room-{name}.svg"] = room_svg(name)
    for variant in ROOM_VARIANTS:
        files[f"lore/img/room-{variant}.svg"] = room_svg(variant)
    files["lore/npcs/traveling-merchant.md"] = _merchant_page()
    files["lore/img/old-man.svg"] = elder_svg()
    for bot in MERCHANT_BOTS:
        files[f"lore/img/{_merchant_img(bot)}"] = merchant_svg(bot)
    for it in items.ITEMS:
        files[f"lore/items/{slug(it.name)}.md"] = _item_page(it)
        files[f"lore/img/{slug(it.name)}.svg"] = sprite_svg("item", it.category)

    beast_rows = []
    for name in beasts:
        stats = next((m for m in MONSTERS if m[0] == name), None)
        thumbs = "".join(f'<img src="img/{slug(name)}{TIER_SLUG[t]}.svg" width="72"> ' for t in range(len(TIERS)))
        beast_rows.append([thumbs, f"[{name}](monsters/{slug(name)}.md)", f"level {stats[2]}, tougher variants later" if stats else "treasure chests, when the workflow fails"])
    def thumb(it):
        return f'<img src="img/{slug(it.name)}.svg" width="72">'

    weapon_rows = [[thumb(i), f"[{i.name}](items/{slug(i.name)}.md)", i.klass, f"{RARITY_BADGE[i.rarity]} {i.rarity} {i.category}", f"+{i.bonus}"]
                   for i in sorted((i for i in items.ITEMS if i.slot == "weapon"), key=lambda i: (i.klass, items.RARITY_RANK[i.rarity]))]
    accessory_rows = [[thumb(i), f"[{i.name}](items/{slug(i.name)}.md)", f"{RARITY_BADGE[i.rarity]} {i.rarity} {i.category}"]
                      for i in items.ITEMS if i.slot == "accessory"]
    room_rows = [[f'<img src="img/room-{name}.svg" width="144">', f"[{title}](rooms/{name}.md)", lore] for name, (title, lore) in ROOM_LORE.items()]
    set_rows = [[f"**{s.name}**", s.weapon, s.accessory, s.effect, s.lore] for s in items.SETS]
    files["lore/spellbook.md"] = _spellbook_page()
    files["lore/README.md"] = f"""# \U0001F4D6 Lore

## Bestiary
Every foe comes in three flavours: the base creature, a **Senior** version (from hero level 5) and a **Skip Level** version (from level 10).

{_table(["", "Monster", "Found"], beast_rows)}

## \U0001F6AA Rooms
Each foe stands in one of {len(ROOM_LORE)} rooms. They are scenery only.

{_table(["", "Room", "Lore"], room_rows)}

## \U0001F9F3 Wanderers
{_wanderers()}

## \U0001F392 Reliquary

### \u2694\ufe0f Weapons
Weapons are class-locked, and you wield one at a time. Staffs hit weakly but let a Wizard cast spells. Daggers and mallets hit hard, with no spells.

{_table(["", "Weapon", "Class", "Kind", "Damage"], weapon_rows)}

### \U0001F48D Accessories
Any class can wear these, one at a time.

{_table(["", "Accessory", "Kind"], accessory_rows)}

### \U0001F517 Sets
Wear both halves of a pair and the set bonus applies in combat.

{_table(["Set", "Weapon", "Accessory", "Effect", "Lore"], set_rows)}

## \U0001F4DC Spellbook
Wizards with a staff unlock {len(spells.SPELLS)} spells, from {spells.SPELLS[0].name} at level {spells.SPELLS[0].level} to {spells.SPELLS[-1].name} at level {spells.SPELLS[-1].level}. See the full [Spellbook](spellbook.md).

{_table(["Spell", "Unlocks", "MP"], [[s.name, f"level {s.level}", s.mp] for s in spells.SPELLS])}

[\u2190 Hall of Heroes](../README.md)
"""
    return files
