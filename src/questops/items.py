"""The loot table: weapons (class-locked) and accessories (anyone), one of each equipped."""

from __future__ import annotations

from typing import NamedTuple


class Item(NamedTuple):
    name: str
    rarity: str
    category: str  # picks the icon and, for weapons, the weapon family
    slot: str  # "weapon" or "accessory"
    klass: str  # weapons only: the class that can wield it; "" for accessories
    bonus: int  # weapons only: flat damage added to every hit
    gray: int = 0  # accessories only: extra GRAY, no gray hairs required


# Staffs are weak but the wielder keeps casting spells; daggers and mallets hit hard.
ITEMS = [
    Item("Rusty Dagger", "common", "dagger", "weapon", "Rogue", 2),
    Item("Hotfix", "rare", "dagger", "weapon", "Rogue", 5),
    Item("Intern's Staff", "common", "staff", "weapon", "Wizard", 0),
    Item("Staff of Eventual Consistency", "rare", "staff", "weapon", "Wizard", 2),
    Item("Staff of Regex", "rare", "staff", "weapon", "Wizard", 1),
    Item("Squeaky Mallet", "common", "mallet", "weapon", "Fighter", 2),
    Item("Local Bludgeon", "uncommon", "bludgeon", "weapon", "Fighter", 0),
    Item("Hard Reset", "rare", "mallet", "weapon", "Fighter", 6),
    Item("Force Merge", "rare", "mallet", "weapon", "Fighter", 4),
    Item("Sudo Shiv", "legendary", "dagger", "weapon", "Rogue", 7),
    Item("Lucky Rubber Duck", "common", "charm", "accessory", "", 0, 1),
    Item("Dependabot Charm", "uncommon", "charm", "accessory", "", 0),
    Item("Cloak of Mild Inconvenience", "uncommon", "cloak", "accessory", "", 0),
    Item("Ring of Retries", "rare", "ring", "accessory", "", 0),
    Item("Lockfile Locket", "rare", "locket", "accessory", "", 0),
    Item("Crown of the Main Branch", "legendary", "crown", "accessory", "", 0),
]


class ItemSet(NamedTuple):
    name: str
    weapon: str
    accessory: str
    effect: str
    lore: str


# A weapon and an accessory worn together: the pair adds a bonus in combat.
SETS = [
    ItemSet("Hotfix Friday", "Hotfix", "Cloak of Mild Inconvenience",
            "Hotfix backfires are absorbed: no damage to you.",
            "Ship it on Friday, wrap it in a cloak, and call the incident 'mild'. The postmortem has been rescheduled indefinitely."),
    ItemSet("Dependency Hell", "Staff of Regex", "Lockfile Locket",
            "The Staff of Regex's 'matches too much' never hurts you.",
            "The lockfile pins every wildcard to a version nobody dares to bump. It is stable, in the way a fossil is stable."),
    ItemSet("Retry Loop", "Hard Reset", "Ring of Retries",
            "Removes the Ring of Retries' -2 to hit in the early rounds.",
            "Turn it off, rewind it, turn it off again. Eventually the loop exits, mostly out of embarrassment."),
    ItemSet("Pair Programming", "Squeaky Mallet", "Lucky Rubber Duck",
            "+1 to hit in round 1.",
            "One of you types and the other squeaks. Somehow the first commit is still the best one."),
    ItemSet("Zero Trust", "Sudo Shiv", "Lockfile Locket",
            "Ignores armour for the whole fight: your attacks cannot miss.",
            "Verify everything, pin everything, and stab anyone who asks for a token. Nobody has ever filed a ticket about it twice."),
]


def active_set(main_hand: str, accessory: str) -> ItemSet | None:
    """The set completed by the equipped weapon and accessory, if any."""
    weapon, worn = parse(main_hand)[0], parse(accessory)[0]
    return next((s for s in SETS if s.weapon == weapon and s.accessory == worn), None)
RARITY_WEIGHT = {"common": 50, "uncommon": 28, "rare": 14, "legendary": 2}
# What the traveling merchant pays for an unequipped item, in 'kens.
SELL_PRICE = {"common": 15, "uncommon": 45, "rare": 140, "legendary": 600}
RARITY_RANK = {"common": 0, "uncommon": 1, "rare": 2, "legendary": 3}
_BY_NAME = {i.name: i for i in ITEMS}


def label(name: str, rarity: str) -> str:
    return f"{name} [{rarity}]"


def parse(item: str) -> tuple[str, str]:
    """'Ring of Retries [rare]' -> ('Ring of Retries', 'rare')."""
    name, _, rest = item.rpartition(" [")
    return (name, rest.rstrip("]")) if name else (item, "common")


def find(item: str) -> Item | None:
    return _BY_NAME.get(parse(item)[0])


def category(item: str) -> str:
    found = find(item)
    return found.category if found else "charm"


def slot(item: str) -> str:
    found = find(item)
    return found.slot if found else "accessory"


def bonus(item: str) -> int:
    found = find(item)
    return found.bonus if found else 0


def gray_bonus(item: str) -> int:
    found = find(item) if item else None
    return found.gray if found else 0


def usable(item: str, klass: str) -> bool:
    """Accessories suit everyone; a weapon only suits its class."""
    found = find(item)
    return not found or found.slot == "accessory" or found.klass == klass


def rank(item: str) -> int:
    return RARITY_RANK.get(parse(item)[1], 0)


def sell_price(item: str) -> int:
    """What an item fetches, from the traveling merchant or the classifieds."""
    return SELL_PRICE.get(parse(item)[1], 15)


def better(new: str, current: str) -> bool:
    """A new item replaces the equipped one only if it is strictly rarer."""
    return not current or rank(new) > rank(current)
