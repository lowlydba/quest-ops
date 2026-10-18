"""Put a hero on a data branch checkout for the e2e merchant: one with a full bag to buy from, or with `newbie`
one with nothing at all, who gets a gift instead.

usage: python tests/e2e/seed_shopper.py <data-branch-checkout> [newbie]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from questops.state import Store  # noqa: E402

SHOPPER = "e2e-shopper"
NEWBIE = "e2e-newbie"
BAG = ["Rusty Dagger [common]", "Lucky Rubber Duck [common]", "Cloak of Mild Inconvenience [uncommon]"]

if __name__ == "__main__":
    store = Store(Path(sys.argv[1]))
    if sys.argv[2:] == ["newbie"]:
        hero = store.load(NEWBIE)
        hero.cls = "Wizard"
        hero.kens = 7
        hero.main_hand = hero.accessory = ""
        hero.inventory = []
        store.save(hero)
        print(f"seeded {NEWBIE} with nothing")
    else:
        hero = store.load(SHOPPER)
        hero.inventory = list(BAG)
        store.save(hero)
        print(f"seeded {SHOPPER} with {len(BAG)} items")
