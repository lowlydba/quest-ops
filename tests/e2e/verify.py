"""Assertions for the e2e workflow: read the data branch the scenario jobs wrote to and check it.

usage: python tests/e2e/verify.py <data-branch-checkout> [<merchant-branch-checkout> [<gift-branch-checkout>]]
"""
import json
import subprocess
import sys
from pathlib import Path

HEROES = [f"e2e-hero-{n}" for n in range(1, 7)]
failures = []


def check(ok, message):
    print(f"{'ok  ' if ok else 'FAIL'} {message}")
    if not ok:
        failures.append(message)


def main(root, merchant_root=None, gift_root=None):
    root = Path(root)
    lines = (root / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()
    played = [e for e in map(json.loads, filter(None, lines)) if e.get("kind") != "merchant"]
    by_player = {}
    for e in played:
        by_player.setdefault(e["player"], []).append(e)

    for hero in HEROES:
        check(len(by_player.get(hero, [])) == 1, f"race: {hero} has exactly one log entry")
        check((root / "characters" / f"{hero}.json").is_file(), f"race: {hero} has a character sheet")
        check((root / "characters" / f"{hero}.svg").is_file(), f"race: {hero} has a card")

    def first(name):
        return by_player.get(name, [{}])[0]

    # a passing run can still lose a fight or a trap, so check what the workflow did, not the encounter
    check(first("e2e-win").get("workflow") == "passed", "auto-detect: a passing job counts as passed")
    check(first("e2e-lose").get("workflow") == "failed" and first("e2e-lose").get("success") is False, "auto-detect: a failing job is a loss")
    check(first("e2e-soft").get("workflow") == "passed", "auto-detect: continue-on-error counts as a pass")
    check(len(by_player.get("e2e-dup", [])) == 1, "dedupe: two plays of one commit count once")
    check(not (root / "characters" / "e2e-dry.json").exists(), "persist=false writes nothing")
    check(not [p for p in by_player if "bot" in p.lower()], "bots never play")
    check(not list((root / "characters").glob("*bot*")), "bots get no character sheet")

    for page in ("README.md", "QUESTLOG.md", "lore/README.md"):
        check((root / page).is_file(), f"derived page {page} exists")

    subprocess.run([sys.executable, "-m", "questops", "rebuild", "--data-dir", str(root)], check=True)
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout
    check(not dirty.strip(), f"rebuild reproduces every derived file (dirty: {dirty.strip()!r})")

    if merchant_root:
        check_merchant(Path(merchant_root))
    if gift_root:
        check_gift(Path(gift_root))

    if failures:
        print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
        return 1
    return 0


def check_merchant(root):
    """A natural 20 brought the merchant, who bought from the seeded shopper's bag."""
    lines = (root / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()
    sales = [e for e in map(json.loads, filter(None, lines)) if e.get("kind") == "merchant"]
    check(len(sales) == 1, "merchant: a natural 20 made exactly one sale")
    sale = sales[0] if sales else {}
    check(sale.get("bot") == "e2e-merchant[bot]" and sale.get("player") == "e2e-shopper", "merchant: the bot's merchant met the shopper")
    shopper = json.loads((root / "characters" / "e2e-shopper.json").read_text(encoding="utf-8"))
    check(len(shopper.get("inventory", [])) < 3 and shopper.get("kens", 0) == sale.get("kens", -1) + 10, "merchant: the bag shrank and the 'kens were paid")
    check(not list((root / "characters").glob("*bot*")), "merchant: the bot got no character sheet")


def check_gift(root):
    """A natural 20 brought the merchant to a hero with nothing, who was given a class weapon."""
    lines = (root / "log" / "quests.jsonl").read_text(encoding="utf-8").splitlines()
    gifts = [e for e in map(json.loads, filter(None, lines)) if e.get("kind") == "merchant"]
    check(len(gifts) == 1 and gifts[0].get("player") == "e2e-newbie" and gifts[0].get("loot") == "Intern's Staff [common]", "gift: the merchant gave the empty-handed hero a staff")
    newbie = json.loads((root / "characters" / "e2e-newbie.json").read_text(encoding="utf-8"))
    check(newbie.get("main_hand") == "Intern's Staff [common]" and newbie.get("kens") == 7, "gift: the staff is equipped and no 'kens changed hands")


def main_cli(argv):
    return main(argv[1], argv[2] if len(argv) > 2 else None, argv[3] if len(argv) > 3 else None)


if __name__ == "__main__":
    sys.exit(main_cli(sys.argv))
