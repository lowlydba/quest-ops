"""Writing the data branch: hero cards, badges, lore, log page, Hall of Heroes."""

from __future__ import annotations

from . import pages, render, svg
from .game import MerchantRun, Quest
from .state import Character, Store, slug


def write_hero(store: Store, ch: Character) -> None:
    root = store.root
    (root / "characters").mkdir(parents=True, exist_ok=True)
    (root / "characters" / f"{slug(ch.name)}.svg").write_text(svg.card(ch), encoding="utf-8", newline="\n")
    badge_dir = root / "badges" / slug(ch.name)
    badge_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in svg.badges_json(ch).items():
        (badge_dir / f"{name}.json").write_text(payload, encoding="utf-8", newline="\n")


def write_shared(store: Store) -> None:
    """Files built from everything: the lore, the log page, the Hall of Heroes."""
    root = store.root
    for rel, content in pages.lore_files().items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            target.write_text(content, encoding="utf-8", newline="\n")
    # The quest log only ever grows, so git can safely keep both sides of a concurrent append.
    attrs = root / ".gitattributes"
    if not attrs.exists():
        attrs.write_text("log/quests.jsonl merge=union\n", encoding="utf-8", newline="\n")
    (root / "QUESTLOG.md").write_text(render.quest_log_md(store.read_log()), encoding="utf-8", newline="\n")
    (root / "README.md").write_text(render.index_md(store), encoding="utf-8", newline="\n")


def _save(store: Store, ch: Character, entry: dict) -> None:
    store.save(ch)
    store.append_log(entry)
    write_hero(store, ch)
    write_shared(store)


def persist_quest(store: Store, q: Quest) -> None:
    _save(store, q.hero, q.entry)


def persist_merchant(store: Store, m: MerchantRun) -> None:
    _save(store, m.hero, m.entry)
