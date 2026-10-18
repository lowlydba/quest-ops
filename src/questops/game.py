"""Game flow without I/O: play a quest or a merchant visit and return what happened."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from . import items, merchant
from .ci import Run
from .engine import Result, run_encounter
from .scenes import pick_scene
from .state import Character, Store, seed_int


@dataclass
class Quest:
    hero: Character
    result: Result
    entry: dict  # the quest log line
    key: str
    outputs: dict  # step outputs


@dataclass
class MerchantRun:
    """A bot run: always a d20 roll; hero, visit and entry exist only when the merchant found a buyer."""

    meeting: merchant.Meeting
    bot: str
    outputs: dict
    hero: Character | None = None
    visit: merchant.Visit | None = None
    entry: dict | None = None

    @property
    def sold(self) -> bool:
        return self.visit is not None


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def already_played(store: Store, player: str, key: str) -> bool:
    return bool(key) and any(e.get("player") == player and e.get("key") == key for e in store.read_log())


def merchant_key(key: str) -> str:
    return f"merchant:{key}" if key else ""


def already_visited(store: Store, key: str) -> bool:
    mk = merchant_key(key)
    return bool(mk) and any(e.get("key") == mk for e in store.read_log())


def play(store: Store, player: str, win: bool, *, kind: str | None, seed: str | None, context: str, run: Run) -> Quest:
    """Play one encounter for `player`. Nothing is saved; the caller decides what to persist."""
    ch = store.load(player)
    key = seed or f"{player}|{run.run_id}|{context}|{ch.encounters}"
    rng = random.Random(seed_int(key))
    r = run_encounter(ch, win, rng, kind)
    r.scene = pick_scene(key)
    entry = {
        "ts": _now(),
        "player": ch.name,
        "success": r.success,
        "workflow": "passed" if win else "failed",
        "kind": r.kind,
        "title": r.title,
        "xp": r.xp,
        "kens": r.kens,
        "loot": r.loot,
        "context": context,
        "run": run.run_id,
        "commit": run.commit,
        "commit_url": run.commit_url,
        "key": run.key,
    }
    outputs = {"encounter": "victory" if r.success else "defeat", "title": r.title, "xp": r.xp, "level": ch.level, "player": ch.name}
    return Quest(ch, r, entry, run.key, outputs)


def play_merchant(store: Store, bot: str, context: str, run: Run) -> MerchantRun:
    """A bot rolls a d20 for the merchant. Nothing is saved; `sold` says whether anything happened."""
    meeting = merchant.visit(store, run.key)
    if meeting.found is None:
        return MerchantRun(meeting, bot, {"encounter": "skipped", "merchant_roll": meeting.roll})
    hero, v = meeting.found
    n = len(v.sold)
    title = "Gifted a starter weapon by a traveling merchant" if v.gift else f"Sold {n} item{'s' if n != 1 else ''} to a traveling merchant"
    entry = {
        "ts": _now(),
        "player": hero.name,
        "success": True,
        "workflow": "bot",
        "kind": "merchant",
        "title": title,
        "xp": 0,
        "kens": v.total,
        "loot": v.gift,
        "context": context,
        "run": run.run_id,
        "commit": run.commit,
        "commit_url": run.commit_url,
        "key": merchant_key(run.key),
        "bot": bot,
    }
    outputs = {"encounter": "merchant", "player": hero.name, "kens": v.total, "merchant_roll": meeting.roll, **({"gift": v.gift} if v.gift else {})}
    return MerchantRun(meeting, bot, outputs, hero, v, entry)
