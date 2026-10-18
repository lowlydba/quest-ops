"""Rendering: terminal transcript, character sheet markdown, quest log, index."""

from __future__ import annotations

import re
import textwrap
from typing import NamedTuple

from .art import CLASS_COLORS, banner, box, center_block, hp_bar, visible_len, xp_bar
from .engine import MONSTERS, TIERS, Result
from .events import Art, Narration, Retreat, Round
from . import avatar as avatar_mod
from . import spells
from .lore import ITEM_EFFECTS
from .merchant import DIE, Meeting
from .pixels import Backend
from .presentation import MIN_WIDTH, Presentation
from .scenes import staged, suit
from .sprites import SPRITES, render as render_pixels, shadow, sprite, tier_ramps
from . import items
from .sprites import item_icon
from .state import Character, Store, slug, xp_for_level


RARITY_COLORS = {"common": 77, "uncommon": 220, "rare": 75, "legendary": 135}


class Centered(NamedTuple):
    """A block centred in the card's width once that width is known."""

    text: str


def item_facts(item: str) -> list[str]:
    """What a piece of loot does, as plain lines: class and damage, its fight effect and any set it belongs to.
    The slot and the stats an effect already spells out are left to the surrounding row."""
    found = items.find(item)
    if not found:
        return []
    effect = ITEM_EFFECTS.get(found.name)
    stats = []
    if found.slot == "weapon":
        stats += [f"{found.klass} only", *([f"+{found.bonus} damage"] if found.bonus else [])]
    if found.gray and not effect:
        stats.append(f"+{found.gray} GRAY")
    lines = [", ".join(stats)] if stats else []
    if effect:
        lines.append(effect)
    lines += [f"Part of {s.name} with {s.accessory if found.slot == 'weapon' else s.weapon}" for s in items.SETS if found.name in (s.weapon, s.accessory)]
    return lines


def loot_status(ch: Character, r: Result) -> str:
    """What became of the loot: equipped (and what it replaced), sold as a spare, or bagged (and why)."""
    if r.loot_action == "sold":
        return f"Spare sold for {items.sell_price(r.loot):,} 'kens"
    if r.loot_action == "equipped":
        return f"Equipped, replacing {items.parse(r.replaced)[0]}" if r.replaced else "Equipped"
    if not items.usable(r.loot, ch.cls):
        return "Kept in the bag: your class cannot wield it"
    current = ch.main_hand if items.slot(r.loot) == "weapon" else ch.accessory
    return f"Kept in the bag: not rarer than your {items.parse(current)[0] or 'current gear'}"


def loot_lines(ch: Character, r: Result, persisted: bool) -> list[str]:
    """The facts and, when the run is saved, the fate of what was found."""
    return [*item_facts(r.loot), *([loot_status(ch, r)] if persisted else [])]


def _s(text: str, code: int, color: bool, bold: bool = False, italic: bool = False) -> str:
    return f"\x1b[{'1;' if bold else ''}{'3;' if italic else ''}38;5;{code}m{text}\x1b[0m" if color else text


RAINBOW = [196, 202, 208, 214, 220, 190, 118, 48, 51, 39, 63, 99, 135, 171, 205]  # xterm-256, red through violet


def rainbow(text: str, color: bool) -> str:
    """Each letter a step along the rainbow; spaces are left plain. Plain text without colour."""
    if not color:
        return text
    steps = [c for c in text if c != " "]
    out, i = [], 0
    for ch in text:
        if ch == " ":
            out.append(ch)
            continue
        out.append(_s(ch, RAINBOW[i * (len(RAINBOW) - 1) // max(len(steps) - 1, 1)], True, True))
        i += 1
    return "".join(out)


HERO_COLOR, KENS_COLOR, FOE_COLOR, DAMAGE_COLOR, SPELL_COLOR, WEARY_COLOR = 255, 220, 203, 196, 141, 244


def item_tag(item: str, color: bool) -> str:
    """An item as [Name], bold in its rarity's colour: the one way a named item looks in the story, the cards and the summaries."""
    name, rarity = items.parse(item)
    return _s(f"[{name}]", RARITY_COLORS.get(rarity, 7), color, True)


def colorize_narration(text: str, hero: str, foes: tuple[str, ...] = ()) -> str:
    """Colour the names and numbers in a line of story, in one regex pass so nothing is wrapped twice.
    Text that already carries escapes is left alone."""
    if "\x1b" in text:
        return text
    foe_names = sorted({*foes, *(m[0] for m in MONSTERS), "Mimic"}, key=len, reverse=True)
    tiers = "|".join(re.escape(t[0]) for t in TIERS if t[0])
    pattern = "|".join([
        rf"(?P<item>\[(?:{'|'.join(re.escape(i.name) for i in sorted(items.ITEMS, key=lambda i: -len(i.name)))})\])",
        *([f"(?P<hero>{re.escape(hero)})"] if hero else []),
        r"(?P<kens>(?:\d{1,3}(?:,\d{3})+|\d+) 'kens)",
        rf"(?P<foe>(?:(?:{tiers}))?(?:{'|'.join(re.escape(f) for f in foe_names)}))",
        r"(?P<dmg>(?<=\bfor )\d+|(?<=\btakes )\d+(?= damage))",
        rf"(?P<spell>\b(?:{'|'.join(re.escape(s.name) for s in sorted(spells.SPELLS, key=lambda s: -len(s.name)))})\b)",
        r"(?P<weary>\bWeary\b)",
    ])

    def paint(m: re.Match) -> str:
        kind, word = m.lastgroup, m.group()
        if kind == "item":
            return _s(word, RARITY_COLORS[items.find(word[1:-1]).rarity], True, True)
        code = {"hero": HERO_COLOR, "kens": KENS_COLOR, "foe": FOE_COLOR, "dmg": DAMAGE_COLOR, "spell": SPELL_COLOR, "weary": WEARY_COLOR}[kind]
        return _s(word, code, True, bold=kind == "hero")

    return re.sub(pattern, paint, text)


def _layout(parts: list, pres: Presentation, box_lines: list[str] | None) -> str:
    """Centre the `Centered` blocks and box the card lines (if any), sizing both from their content."""
    box_width = pres.box_width(box_lines or [""])
    width = pres.layout_width([p.text for p in parts if isinstance(p, Centered)], box_width)
    lines = [center_block(p.text, width) if isinstance(p, Centered) else p for p in parts]
    return "\n".join(lines + ([box(box_lines, width)] if box_lines else []))


def _scene(art_block: str, pres: Presentation) -> list:
    """A sprite with its ground shadow, followed by a blank line."""
    return [Centered(art_block), Centered(shadow(pres.shadow_width(art_block), pres.pixels)), ""]


STAGED = {*(m[1] for m in MONSTERS), "mimic"}  # sprites drawn inside a scene; chests and traps stand alone


def _art(ev: Art, scene: str, pres: Presentation) -> list:
    """A monster in its scene when there is colour to draw one, otherwise the bare sprite and its shadow."""
    if scene and ev.key in STAGED and pres.pixels.colored:
        return [Centered(staged(suit(scene, ev.key), SPRITES[ev.key], tier_ramps(ev.key, ev.tier), pres.pixels, ev.tier)), ""]
    return _scene(sprite(ev.key, pres.pixels, ev.tier), pres)


def wake_line(ch: Character) -> str:
    return f"{ch.name} wakes on a cold dungeon floor, confused, with no idea how they got here. Something is right in front of them."


def fade_line(ch: Character, win: bool) -> str:
    if win:
        return f"{ch.name} wonders where this is, and what comes next. Then everything goes dark again."
    return f"In the dark, {ch.name} wonders where this is, and what comes next. Then nothing."


def transcript(ch: Character, r: Result, context: str = "", pres: Presentation | None = None) -> str:
    pres = pres or Presentation.detect()
    color = pres.color
    parts: list = [Centered(banner(pres.pixels))]
    if context:
        parts.append(f"Quest: {context}")
    parts.append("")
    if pres.narrated:
        parts += [wake_line(ch), ""]
    for ev in pres.events(r):
        if isinstance(ev, Art):
            parts += _art(ev, r.scene, pres)
        elif color and isinstance(ev, (Narration, Round)):
            parts.append(colorize_narration(ev.text, ch.name, (r.foe,) if r.foe else ()))
        else:
            parts.append(ev.text)

    parts += [_s("Achievement unlocked: ", 213, color) + _s(a, 213, color, True) for a in r.new_achievements]  # in the story, so the card stays calm
    if pres.narrated:
        parts += ["", fade_line(ch, r.success)]
    verdict = _s("VICTORY", 46, color, True) if r.success else _s("DEFEAT", 196, color, True)
    portrait = avatar_lines(ch, pres.pixels)
    pad = max(visible_len(x) for x in portrait)
    inner = (pres.pixels.width or MIN_WIDTH) - 4  # the card's text width inside "| " and " |"
    title = _s(r.title, 255, color, True)
    head = [f"{verdict}  {title}", ""] if len(r.title) + 8 <= inner else [verdict, title, ""]

    who = f"{ch.name} the {ch.cls}"
    lv = f"  Lv {ch.level}" if pres.show_stats else ""
    name_lines = [_s(ch.name, 255, color, True) + f" the {_s(ch.cls, CLASS_COLORS.get(ch.cls, 7), color)}"]
    if pad + 3 + len(who) + len(lv) > inner:  # a long name takes its own line
        name_lines = [_s(ch.name, 255, color, True), f"the {_s(ch.cls, CLASS_COLORS.get(ch.cls, 7), color)}"]
    if pres.show_stats:
        name_lines[-1] += _s(lv, 220, color, True)
        kens = _s("\u25cf", 220, color) + " " + _s(f"{ch.kens:,} {chr(39)}kens", 220, color)
        if r.kens:
            kens += f" ({_s(f'{r.kens:+,d}', 77 if r.kens >= 0 else 196, color)})"
        xp_line = f"XP {xp_bar(ch.xp - _base(ch), ch.next_level_xp - _base(ch), width=16, color=color)} " + _s(f"(+{r.xp:,})", 77, color)
        broken = any(isinstance(e, Retreat) and e.streak for e in r.transcript)
        if r.success:
            streak = _s(f"\u25b2 streak {ch.streak}", 51, color)
        else:  # a loss never points up: down when it cost a streak, plain when there was none to lose
            streak = _s("\u25bc streak 0", 196, color) if broken else _s("streak 0", 244, color)
        right = [*name_lines, xp_line, kens + "   " + streak]
        if r.levels:
            right.append(_s(f"LEVEL UP! Now level {ch.level}", 220, color, True))
    else:
        right = name_lines

    body = side_by_side(portrait, right)

    def wrap(lines: list[str], indent: int) -> list[str]:
        return [_s(w, 244, color, italic=True) for ln in lines for w in textwrap.wrap(ln, max(inner - indent, 20))]

    def label(item: str) -> str:
        return item_tag(item, color) + " " + _s(items.parse(item)[1], 244, color, italic=True)

    indent = " " * (pad + 3)
    gear_rows = []
    for item, slot_name in ([(ch.main_hand, "weapon"), (ch.accessory, "accessory")] if pres.show_gear else []):
        if not item:
            continue
        if r.loot == item and r.loot_action == "equipped":
            # The new find: its stats, effect and set replace the bare slot name.
            facts = item_facts(item) + ([f"Replaced {items.parse(r.replaced)[0]}"] if r.replaced else [])
            text = [label(item) + _s("  NEW!", 77, color), *wrap(facts, pad + 3)]
        else:
            text = [label(item), _s(slot_name, 244, color, italic=True)]
        gear_rows += ([""] if gear_rows else []) + side_by_side(item_icon(items.category(item), pres.pixels), text, pad)
    if r.loot and r.loot_action in ("bag", "sold") and pres.show_gear:
        status = loot_status(ch, r)
        note = "Bagged: " + status.split(": ", 1)[-1] if r.loot_action == "bag" else status
        gear_rows += [indent + label(r.loot), *[indent + ln for ln in wrap([note], pad + 3)]]
    active = items.active_set(ch.main_hand, ch.accessory) if pres.show_gear else None
    if active:
        gear_rows.append(indent + _s("+ Set: " + active.name, 213, color, True))
    if r.loot and not pres.show_gear:
        found = indent + _s("Found: ", 244, color) + label(r.loot)
        gear_rows.append(found if visible_len(found) <= inner else indent + label(r.loot))
        gear_rows += [indent + ln for ln in wrap(item_facts(r.loot), pad + 3)]
    if gear_rows:
        body += [""] + gear_rows
    parts.append("")
    return _layout(parts, pres, head + body)


def avatar_lines(ch: Character, color: bool | Backend) -> list[str]:
    rows, ramps = avatar_mod.portrait(ch.name, ch.cls)
    return render_pixels(rows, ramps, color, dither=0.3).split("\n")


def side_by_side(left: list[str], right: list[str], min_width: int = 0) -> list[str]:
    w = max([visible_len(x) for x in left] + [min_width]) + 3
    n = max(len(left), len(right))
    left = list(left) + [""] * (n - len(left))
    right = list(right) + [""] * (n - len(right))
    return [(a + " " * (w - visible_len(a)) + b).rstrip() for a, b in zip(left, right)]


def _base(ch: Character) -> int:
    return xp_for_level(ch.level)


def codex(store: Store) -> str:
    """Everything the game knows about, for the curious."""
    from .engine import ACHIEVEMENTS, KINDS, MONSTERS
    from .items import ITEMS
    from .state import CLASSES, xp_for_level

    def table(title, head, rows):
        widths = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
        line = "  ".join("{:<%d}" % w for w in widths)
        out = [f"== {title} ==", line.format(*head), line.format(*["-" * w for w in widths])]
        out += [line.format(*map(str, r)) for r in rows]
        return "\n".join(out)

    parts = []
    parts.append(table("Classes", ["Class", "Damage die", "Weapon", "Casts spells"], [[c, f"d{v[0]}", v[1], "yes" if v[2] else "no"] for c, v in sorted(CLASSES.items())]))

    def trio(attr, lv):
        vals = []
        for cls in ("Fighter", "Rogue", "Wizard"):
            probe = Character(name="probe", cls=cls, level=lv)
            vals.append(str(getattr(probe, attr)))
        return "/".join(vals)

    lv_rows = [[lv, xp_for_level(lv), trio("hp_max", lv), trio("mp_max", lv), trio("gray", lv)] for lv in range(1, 11)]
    parts.append(table("Levels 1-10 (Fighter/Rogue/Wizard)", ["Lv", "XP needed", "HP", "MP", "GRAY"], lv_rows))

    parts.append(table("Foes", ["Foe", "From Lv", "HP", "XP", "'kens"], [[m[0], m[2], m[3], m[7], m[8]] for m in MONSTERS]))
    parts.append(table("Encounters", ["Kind", "Weight"], [list(k) for k in KINDS]))
    parts.append(table("Loot", ["Item", "Slot", "Class", "Rarity", "Kind", "Damage"], [[i.name, i.slot, i.klass or "any", i.rarity, i.category, f"+{i.bonus}" if i.slot == "weapon" else "-"] for i in ITEMS]))
    parts.append(table("Sets", ["Set", "Weapon", "Accessory", "Effect"], [[s.name, s.weapon, s.accessory, s.effect] for s in items.SETS]))
    parts.append(table("Spells (Wizard with a staff)", ["Spell", "Unlocks", "MP", "Effect"], [[s.name, f"Lv {s.level}", s.mp, s.effect] for s in spells.SPELLS]))
    parts.append("== Achievements ==\n" + "\n".join(f"  - {label}" for label, _ in ACHIEVEMENTS.values()))

    heroes = sorted(store.all_characters(), key=lambda c: (-c.level, -c.xp, c.name))
    rows = [[c.name, c.cls, c.level, c.xp, f"{c.wins}/{c.losses}", c.streak, c.kens] for c in heroes]
    parts.append(table(f"Heroes in {store.root}", ["Name", "Class", "Lv", "XP", "W/L", "Streak", "'kens"], rows) if rows else f"== Heroes in {store.root} ==\n  (none yet)")
    return "\n\n".join(parts)


def sheet_md(ch: Character) -> str:
    inv = "\n".join(f"- {i}" for i in reversed(ch.inventory)) or "_Nothing else in the bag._"
    gear = "\n".join(x for x in (ch.main_hand, ch.accessory) if x) or "_Nothing equipped._"
    ach = "\n".join(f"- 🏆 {a}" for a in ch.achievements) or "_None yet._"
    kills = "\n".join(f"| {k} | {v} |" for k, v in sorted(ch.kills.items(), key=lambda kv: -kv[1])) or "| - | 0 |"
    done = ch.xp - _base(ch)
    need = ch.next_level_xp - _base(ch)
    rate = f"{100 * ch.wins // ch.encounters}%" if ch.encounters else "-"
    active = items.active_set(ch.main_hand, ch.accessory)
    set_note = f"\n\n**Set:** {active.name}. {active.effect}" if active else ""

    return f"""# {ch.name}, Level {ch.level} {ch.cls}

```text
{chr(10).join(avatar_lines(ch, False))}
```

```text
HP  {hp_bar(ch.hp_max, ch.hp_max)}
MP  {hp_bar(ch.mp_max, ch.mp_max)}
XP  {xp_bar(done, need)}
GRAY {ch.gray}
```

🪙 **{ch.kens:,} 'kens** · ⚔️ {ch.wins}W / {ch.losses}L ({rate}) · 🔥 streak {ch.streak} (best {ch.best_streak})

**Last quest:** {ch.last_encounter or '-'}

## 🏆 Achievements
{ach}

## 🛡️ Equipped
{gear}{set_note}

## 🎒 In the bag
{inv}

## 📖 Bestiary
| Foe | Slain |
|---|---|
{kills}
"""


def quest_log_md(entries: list[dict], limit: int = 50) -> str:
    rows = []
    for e in reversed(entries[-limit:]):
        icon = "\U0001F6D2" if e.get("kind") == "merchant" else ("\u2705" if e["success"] else "\u274c")
        sha = e.get("commit", "")
        commit = (f"[`{sha[:7]}`]({e['commit_url']})" if e.get("commit_url") else f"`{sha[:7]}`") if sha else "-"
        rows.append(f"| {e['ts'][:16].replace('T', ' ')} | {e['player']} | {icon} | {e['title']} | {e['xp']} | {commit} | {e.get('context', '')} |")
    head = "| When (UTC) | Hero | Result | Encounter | XP | Commit | Quest |\n|---|---|---|---|---|---|---|\n"
    return "# Quest Log\n\n" + head + "\n".join(rows) + "\n"


def _rank(i: int) -> str:
    return {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}.get(i, f"{i}.")


def _gear_link(c: Character) -> str:

    links = [f"[{items.parse(i)[0]}](lore/items/{slug(items.parse(i)[0])}.md)" for i in (c.main_hand, c.accessory) if i]
    return " \u00b7 ".join(links) or "-"


def index_md(store: Store) -> str:

    chars = sorted(store.all_characters(), key=lambda c: (-c.level, -c.xp, c.name))
    rows = "\n".join(
        f"| {_rank(i)} | [{c.name}](characters/{slug(c.name)}.svg) | {c.cls} | {c.level} | {c.xp:,} | {c.wins}/{c.losses} | {c.streak} | {_gear_link(c)} |"
        for i, c in enumerate(chars, 1)
    )
    cells = [f'<td width="50%" valign="top"><img src="characters/{slug(c.name)}.svg" alt="{c.name}" width="100%"></td>' for c in chars]
    if len(cells) % 2:
        cells.append('<td width="50%"></td>')
    cards = "<table>\n" + "\n".join("<tr>" + "".join(cells[i : i + 2]) + "</tr>" for i in range(0, len(cells), 2)) + "\n</table>"
    return f"""<p align="center"><img src="banner.svg" alt="QuestOps" width="480"></p>

# Hall of Heroes

| # | Hero | Class | Lv | XP | W/L | Streak | Equipped |
|---|---|---|---|---|---|---|---|
{rows}

{cards}

📖 [Bestiary and reliquary](lore/README.md) · 📜 [Quest log](QUESTLOG.md)
"""


def lore_md(base: str) -> str:
    """One quiet footer line linking the bestiary and reliquary and the Hall of Heroes; empty when nothing is saved to link."""
    if not base:
        return ""
    return f"\U0001F4D6 [Bestiary and reliquary]({base}lore/README.md) \u00b7 [Hall of Heroes]({base}README.md)"


def lore_line(base: str) -> str:
    """The same for a plain log, where GitHub links a bare URL."""
    return f"Lore: {base}lore/README.md" if base else ""


def _card_img(card_url: str, name: str) -> str:
    return f'\n<img src="{card_url}" alt="{name}" width="480">\n' if card_url else ""


def _summary_parts(ch: Character, r: Result, context: str, pres: Presentation) -> tuple[str, str, str, str]:
    """(icon, verdict, the story as a quote, the stats table) behind the job summary and the pull request comment."""
    story = pres.story(r)
    if pres.narrated:
        story = [wake_line(ch), *story, fade_line(ch, r.success)]
    quote = "".join(f"> {ln}  \n" for ln in ([f"Quest: {context}"] if context else []) + story)
    icon = "\u2705" if r.success else "\u274c"
    verdict = "Victory" if r.success else "Defeat"
    if not pres.show_stats:
        rows = f"| Hero | **{ch.name}** the {ch.cls} |\n" + (f"| Loot | {_loot_md(ch, r, False)} |\n" if r.loot else "")
        return icon, verdict, quote, f"| | |\n|---|---|\n{rows}"
    rate = f"{100 * ch.wins // ch.encounters}%" if ch.encounters else "-"
    rows = [
        ("Hero", f"**{ch.name}**, Level {ch.level} {ch.cls}"),
        ("XP", f"+{r.xp:,} ({ch.xp - _base(ch):,}/{ch.next_level_xp - _base(ch):,} to next level)"),
        ("'kens", f"{ch.kens:,}" + (f" ({r.kens:+,d})" if r.kens else "")),
        ("Streak", f"{ch.streak} (best {ch.best_streak})"),
        ("Record", f"{ch.wins}W / {ch.losses}L ({rate})"),
    ]
    if r.loot:
        rows.append(("Loot", _loot_md(ch, r, True)))
    active = items.active_set(ch.main_hand, ch.accessory)
    if active:
        rows.append(("Set", f"**{active.name}**: {active.effect}"))
    if r.levels:
        rows.append(("Level up", f"Now level {ch.level}"))
    for a in r.new_achievements:
        rows.append(("Achievement", f"\U0001F3C6 {a}"))
    return icon, verdict, quote, "| | |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows) + "\n"


def summary_md(ch: Character, r: Result, context: str = "", card_url: str = "", pres: Presentation | None = None, lore: str = "") -> str:
    """Job summary: plain markdown, because a code block cannot carry the pixel art's colours.
    A run that saves nothing shows the story and the hero, but no stats."""
    pres = pres or Presentation()
    icon, verdict, quote, table = _summary_parts(ch, r, context, pres)
    img = _card_img(card_url, ch.name) if pres.show_stats else ""
    return f"## {icon} QuestOps: {r.title}\n\n**{verdict}**\n\n{quote}\n{table}{img}" + (f"\n{lore}\n" if lore else "")


def comment_md(ch: Character, r: Result, context: str = "", card_url: str = "", pres: Presentation | None = None, lore: str = "") -> str:
    """The pull request comment: the hero's card and one line on how it went, with the story and stats collapsed."""
    pres = pres or Presentation()
    icon, verdict, quote, table = _summary_parts(ch, r, context, pres)
    brief = [f"**{verdict}.** {ch.name} the {ch.cls}", f"+{r.xp:,} XP", *([f"{r.kens:+,d} 'kens"] if r.kens else [])]
    if pres.show_stats:
        brief.insert(1, f"Lv {ch.level}")
        brief.append(f"streak {ch.streak}")
    if r.loot:
        name, rarity = items.parse(r.loot)
        brief.append(f"found [{name}]")
    brief += [f"\U0001F3C6 {a}" for a in r.new_achievements]
    img = _card_img(card_url, ch.name) if pres.show_stats else ""
    return (f"### {icon} QuestOps: {r.title}\n{img}\n{' · '.join(brief)}\n\n" + (f"{lore}\n\n" if lore else "") +
            f"<details><summary>The full encounter</summary>\n\n{quote}\n{table}\n</details>\n")


def _loot_md(ch: Character, r: Result, persisted: bool) -> str:
    name, rarity = items.parse(r.loot)
    return "<br>".join([f"**[{name}]** *{rarity}*", *loot_lines(ch, r, persisted)])


def _need_phrase(need: int) -> str:
    if need > DIE:
        return "legend says no roll can summon a merchant to your location"
    if need == DIE:
        return "legend says only a natural 20 can summon a merchant to your location"
    return f"legend says only {'an' if need in (8, 11, 18) else 'a'} {need} or higher can summon a merchant to your location"


def _rolled(roll: int) -> str:
    return f"Rolled {'an' if roll in (8, 11, 18) else 'a'} {roll}"


def _landing(number: str, m: Meeting) -> str:
    """The sentence about where the d20 landed, in one breath: 'It lands on 20, a natural 20! Wheels creak...'"""
    if m.summoned:
        return f"It lands on {number}{', a natural 20!' if m.roll == DIE else '.'} Wheels creak, and a cart pulls up."
    if m.roll == 1:
        return f"It lands on {number}. It skitters off the table. Somewhere, a merchant laughs."
    if m.roll > DIE // 2:
        return f"It lands on {number}. A cart rattles in the distance, then turns back."
    return f"It lands on {number}. The road stays empty."


def merchant_roll(bot: str, m: Meeting, pres: Presentation | bool | None = None, context: str = "") -> str:
    """A bot's turn: the pixel d20 with the roll on its face, the story, and (unless a sale follows) a result card."""
    from .dice import d20, ramp_for

    if not isinstance(pres, Presentation):
        pres = Presentation.detect(color=pres)
    color = pres.color
    parts: list = [Centered(banner(pres.pixels))]
    if context:
        parts.append(f"Quest: {context}")
    parts.append("")
    parts += _scene(d20(m.roll, pres.pixels, DIE), pres)
    who = _s(bot, 255, color, True)
    number = _s(str(m.roll), ramp_for(m.roll, DIE)[4], color, True)
    parts.append(f"{who} rolls a d20 for the {rainbow('Traveling Merchant', color)}.")
    parts.append(_landing(number, m))
    if m.summoned and m.found:
        return _layout(parts, pres, None)
    parts.append("")
    if m.summoned:
        parts.append("The merchant looks around, finds nobody with anything to sell, and leaves.")
        parts.append("")
        head = _s("NO SALE", 208, color, True)
        verdict = "The merchant came, but nobody had anything to sell."
    else:
        head = _s("QUIET", 244, color, True)
        verdict = _need_phrase(m.need).capitalize() + "."
    lines = [f"{head}  {_s(_rolled(m.roll), 255, color, True)}", "", *textwrap.wrap(verdict, MIN_WIDTH - 4)]
    return _layout(parts, pres, lines)


def merchant_roll_md(m: Meeting) -> str:
    if not m.summoned:
        return f"{_rolled(m.roll)} ({_need_phrase(m.need)})"
    return f"{_rolled(m.roll)} (the merchant came)" + ("" if m.found else ", but found nobody with anything to sell")


def merchant_miss_md(bot: str, m: Meeting) -> str:
    return f"## \U0001F3B2 QuestOps: {bot} rolls for the merchant\n\n{merchant_roll_md(m)}.\n"


GIFT_LINE = "It's dangerous to go alone! Take this!"


def _gift_md(ch: Character, v, bot: str, card_url: str, meeting: Meeting | None) -> str:
    name, rarity = items.parse(v.gift)
    rolled = f"{merchant_roll_md(meeting)}.\n\n" if meeting else ""
    facts = ", ".join(item_facts(v.gift)[:1])
    return (
        f"## \U0001F6D2 QuestOps: a traveling merchant\n\n"
        f"> A Traveling Merchant, summoned by {bot}, finds {ch.name} empty-handed!  \n"
        f'> "{GIFT_LINE}"\n\n'
        f"{rolled}"
        f"**{ch.name}** now wields **[{name}]** *{rarity}*{f' ({facts})' if facts else ''}.\n{_card_img(card_url, ch.name)}"
    )


def merchant_summary_md(ch: Character, v, bot: str, card_url: str = "", meeting: Meeting | None = None) -> str:
    if v.gift:
        return _gift_md(ch, v, bot, card_url, meeting)
    n = len(v.sold)
    sold = "\n".join(f"| **[{items.parse(i)[0]}]** *{items.parse(i)[1]}* | +{p:,} 'kens |" for i, p in v.sold)
    rolled = f"{merchant_roll_md(meeting)}.\n\n" if meeting else ""
    return (
        f"## \U0001F6D2 QuestOps: a traveling merchant\n\n"
        f"> A Traveling Merchant, summoned by {bot}, bumps into {ch.name}!  \n"
        f'> "I am buying anything you are not wearing. No questions asked."\n\n'
        f"{rolled}"
        f"Bought {n} item{'s' if n != 1 else ''} from **{ch.name}** for {v.total:,} 'kens ({ch.kens:,} 'kens now). The merchant has no idea what they are for either.\n\n"
        f"| Item | Price |\n|---|---|\n{sold}\n{_card_img(card_url, ch.name)}"
    )


def merchant_comment_md(ch: Character, v, bot: str, card_url: str = "", meeting: Meeting | None = None) -> str:
    """The pull request comment for a sale: the hero's card and one line, with the story and prices collapsed."""
    n = len(v.sold)
    brief = (f"A traveling merchant summoned by {bot} gifted {ch.name} a starter weapon: {items.parse(v.gift)[0]}." if v.gift
             else f"A traveling merchant summoned by {bot} bought {n} item{'s' if n != 1 else ''} from {ch.name} for {v.total:,} 'kens.")
    body = merchant_summary_md(ch, v, bot, "", meeting).split("\n\n", 1)[1]
    return f"### \U0001F6D2 QuestOps: a traveling merchant\n{_card_img(card_url, ch.name)}\n{brief}\n\n<details><summary>The full encounter</summary>\n\n{body}\n</details>\n"


def merchant_card(ch: Character, v, bot: str, pres: Presentation | None = None, banner_shown: bool = False) -> str:
    """The scene when a traveling merchant buys from a hero's bag. Skips the banner when the roll already showed it."""
    from .sprites import gift_sprite, merchant_sprite

    pres = pres or Presentation.detect()
    color = pres.color
    parts: list = [] if banner_shown else [Centered(banner(pres.pixels)), ""]
    parts += _scene(gift_sprite(pres.pixels) if v.gift else merchant_sprite(bot, pres.pixels), pres)
    if v.gift:
        parts += [f"A {rainbow('Traveling Merchant', color)}, summoned by {bot}, finds {ch.name} empty-handed!", f'"{GIFT_LINE}"', ""]
        lines = [f"{_s('MERCHANT', 208, color, True)}  {_s('A gift for ' + ch.name, 255, color, True)}", "",
                 item_tag(v.gift, color) + " " + _s(items.parse(v.gift)[1], 244, color, italic=True) + _s("  NEW!", 77, color)]
        lines += [_s(ln, 244, color, italic=True) for f in item_facts(v.gift) for ln in textwrap.wrap(f, MIN_WIDTH - 4)]
        return _layout(parts, pres, lines)
    parts.append(f"A {rainbow('Traveling Merchant', color)}, summoned by {bot}, bumps into {ch.name}!")
    parts.append('"I am buying anything you are not wearing. No questions asked."')
    parts.append("")
    n = len(v.sold)
    lines = [f"{_s('MERCHANT', 208, color, True)}  {_s('Bought ' + str(n) + ' item' + ('s' if n != 1 else '') + ' from ' + ch.name, 255, color, True)}", ""]
    for item, price in v.sold:
        name, rarity = items.parse(item)
        gain = _s(f"+{price:,} 'kens", 220, color)
        pad = max(46 - len(name) - len(rarity) - 3 - len(f"+{price:,} 'kens"), 1)
        lines.append(item_tag(item, color) + " " + _s(rarity, 244, color, italic=True) + " " * pad + gain)
    lines += ["", f"{_s(chr(0x25cf), 220, color)} {_s(f'{ch.kens:,} ' + chr(39) + 'kens', 220, color)} now ({_s(f'{v.total:+,d}', 77, color)})"]
    return _layout(parts, pres, lines)
