"""Command line interface. Works in any CI: only flags, env vars, and a data dir."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__, ci, game, render, site
from .art import banner, color_enabled
from .engine import KINDS
from .presentation import Presentation
from .state import Store

WIN = {"success", "succeeded", "passed", "pass", "ok", "win", "true"}
LOSS = {"failure", "failed", "fail", "error", "lose", "loss", "false"}
SKIP = {"cancelled", "canceled", "skipped", "", "none"}


def cmd_rebuild(a: argparse.Namespace) -> int:
    """Regenerate every derived file (cards, badges, lore, log page, hall) from the saved data."""
    store = Store(Path(a.data_dir))
    heroes = store.all_characters()
    for ch in heroes:
        site.write_hero(store, ch)
    site.write_shared(store)
    print(f"QuestOps: rebuilt {len(heroes)} hero card{'s' if len(heroes) != 1 else ''} and the shared pages in {store.root}")
    return 0


def _resolve_outcome(a: argparse.Namespace) -> tuple[bool | None, int]:
    """(win, exit code to pass through). `win` is None when there is no encounter; the code is then the exit status."""
    command = [c for c in (a.command or []) if c != "--"] if a.command and a.command[0] == "--" else a.command
    exit_code = 0
    if command:
        # Wrap mode: the command's exit code is the outcome, and is passed through.
        try:
            exit_code = subprocess.call(command)
        except OSError as e:
            print(f"QuestOps: could not run {command[0]!r}: {e}", file=sys.stderr)
            exit_code = 127
        status = "success" if exit_code == 0 else "failure"
    else:
        status = (a.outcome or ci.env("QUESTOPS_OUTCOME")).strip().lower()
        if not status:
            a.parser.print_help()
            return None, 0
    if status in SKIP:
        print(f"QuestOps: outcome '{status}' - the dungeon stays quiet. No encounter.")
        ci.write_outputs({"encounter": "skipped"})
        return None, 0
    if status in WIN:
        return True, exit_code
    if status in LOSS:
        return False, exit_code
    print(f"QuestOps: unknown outcome '{status}'", file=sys.stderr)
    return None, 2


def _run_bot(a: argparse.Namespace, store: Store, bot: str, context: str, run: ci.Run) -> None:
    """Bots are not heroes. Mostly nothing happens; sometimes a merchant buys from a hero's bag."""
    if not a.dry_run and game.already_visited(store, run.key):
        print(f"QuestOps: the merchant already passed through on {run.key[:8]}.")
        ci.write_outputs({"encounter": "skipped"})
        return
    m = game.play_merchant(store, bot, context, run)
    pres = Presentation.detect()
    print(render.merchant_roll(bot, m.meeting, pres, context))
    if not m.sold:
        miss = render.merchant_miss_md(bot, m.meeting)
        ci.write_summary(miss)
        ci.write_comment(miss)
        ci.write_outputs(m.outputs)
        return
    print("")
    print(render.merchant_card(m.hero, m.visit, bot, pres, banner_shown=True))
    if not a.dry_run:
        site.persist_merchant(store, m)
    card = ci.card_url(m.hero.name, a.dry_run)
    ci.write_summary(render.merchant_summary_md(m.hero, m.visit, bot, card, m.meeting))
    ci.write_comment(render.merchant_comment_md(m.hero, m.visit, bot, card, m.meeting))
    ci.write_outputs(m.outputs)


def cmd_run(a: argparse.Namespace) -> int:
    win, exit_code = _resolve_outcome(a)
    if win is None:
        return exit_code
    player = a.player or ci.detect_player()
    if ci.is_ignored(player, a.ignore or ""):
        print(f"QuestOps: {player} is on the ignore list. The dungeon pretends not to notice.")
        ci.write_outputs({"encounter": "skipped"})
        return exit_code
    context = a.context if a.context is not None else ci.detect_context()
    store = Store(Path(a.data_dir))
    run = ci.detect_run()
    if ci.is_bot(player) and not os.environ.get("QUESTOPS_ALLOW_BOTS"):
        _run_bot(a, store, player, context, run)
        return exit_code
    if not a.dry_run and game.already_played(store, player, run.key):
        print(f"QuestOps: {player} already quested on {run.key[:8]}. Re-runs don't count twice.")
        ci.write_outputs({"encounter": "skipped"})
        return exit_code

    pres = Presentation.detect(ephemeral=a.dry_run)
    q = game.play(store, player, win, kind=a.kind, seed=a.seed, context=context, run=run)
    print(render.transcript(q.hero, q.result, context, pres))
    base = ci.data_url(a.dry_run)
    if base:
        print(render.lore_line(base))
    if not a.dry_run:
        site.persist_quest(store, q)
    card, lore = ci.card_url(q.hero.name, a.dry_run), render.lore_md(base)
    ci.write_summary(render.summary_md(q.hero, q.result, context, card, pres, lore))
    ci.write_comment(render.comment_md(q.hero, q.result, context, card, pres, lore))
    ci.write_outputs(q.outputs)
    return exit_code


def cmd_codex(a: argparse.Namespace) -> int:
    print(render.codex(Store(Path(a.data_dir))))
    return 0


def cmd_show(a: argparse.Namespace) -> int:
    store = Store(Path(a.data_dir))
    ch = store.load(a.player or ci.detect_player())
    print(render.sheet_md(ch))
    return 0


class _Parser(argparse.ArgumentParser):
    """Show the title banner above help output."""

    def format_help(self) -> str:
        return banner(color_enabled()) + "\n\n" + super().format_help()


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="questops", description="One CI encounter, one text dungeon RPG.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("quest", aliases=["run"], help="go on a quest (usage: questops quest [options] -- <command>)")
    r.add_argument("command", nargs=argparse.REMAINDER, help="command to wrap; its exit code decides the fight and is passed through")
    r.add_argument("--outcome", help="instead of wrapping a command: success|failure (cancelled/skipped = no encounter); env QUESTOPS_OUTCOME")
    r.add_argument("--player", help="hero name (default: CI actor / $USER)")
    r.add_argument("--ignore", default=os.environ.get("QUESTOPS_IGNORE", ""), help="players and bots that never play, separated by commas or spaces; * matches anything (e.g. '*[bot], octocat'); env QUESTOPS_IGNORE")
    r.add_argument("--data-dir", default=os.environ.get("QUESTOPS_DATA_DIR", ".questops-data"))
    r.add_argument("--seed", help="fix the RNG for reproducible runs")
    r.add_argument("--kind", choices=["random"] + [k for k, _ in KINDS], default="random")
    r.add_argument("--context", help="label for the quest log (default: repo / workflow)")
    r.add_argument("--dry-run", action="store_true", help="print only; do not write data")
    r.set_defaults(fn=cmd_run, parser=r)

    c = sub.add_parser("codex", help="list classes, levels, foes, loot, achievements and heroes")
    c.add_argument("--data-dir", default=os.environ.get("QUESTOPS_DATA_DIR", ".questops-data"))
    c.set_defaults(fn=cmd_codex)

    rb = sub.add_parser("rebuild", help="regenerate cards, badges, lore and pages from the saved data")
    rb.add_argument("--data-dir", default=os.environ.get("QUESTOPS_DATA_DIR", ".questops-data"))
    rb.set_defaults(fn=cmd_rebuild)

    s = sub.add_parser("show", help="print a character sheet")
    s.add_argument("--player")
    s.add_argument("--data-dir", default=os.environ.get("QUESTOPS_DATA_DIR", ".questops-data"))
    s.set_defaults(fn=cmd_show)
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = build_parser()
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        parser.print_help()
        return 0
    a = parser.parse_args(args)
    return a.fn(a)
