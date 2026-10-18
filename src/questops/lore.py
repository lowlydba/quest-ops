"""Lore for every monster and item: the bestiary and the reliquary."""

from __future__ import annotations

# name -> (kind, sprite key, lore)
LORE = {
    "Cache Slime": (
        "monster",
        "slime",
        "Grows in the dark corners of a build agent and absorbs whatever it touches. It has never once been invalidated, and nobody remembers what it was caching.",
    ),
    "Lint Goblin": (
        "monster",
        "goblin",
        "Lives in the whitespace between your tokens and feeds on trailing spaces, unused imports and the odd stray semicolon. "
        "Harmless on its own, which is why it never is.",
    ),
    "Wraith of the Flaky Test": (
        "monster",
        "wraith",
        "Passes on Tuesdays and fails on release day. Re-running it only seems to please it. "
        "Scholars agree it is a test that was deleted but never forgiven.",
    ),
    "Ancient Wyrm of Legacy Prod": (
        "monster",
        "dragon",
        "Sleeps beneath the production database nobody dares to migrate and wakes at 4:55 on a Friday. "
        "Its hoard is uptime, and its breath is a wall of 500s.",
    ),
    "Traveling Merchant": (
        "npc",
        "merchant",
        "Wanders in whenever a bot finishes its work. Pays fair prices for anything you are not wearing, asks no questions, and has never once explained where the stock goes.",
    ),
    "Mimic": (
        "monster",
        "mimic",
        "Looks like a feature flag and behaves like a rewrite. It bites anyone who opens it without reading the diff first. Learning [Mikheit](https://frieren.fandom.com/wiki/Spells#Named_Other_Spells \"Spells\") sure would be helpful.",
    ),
    "Rusty Dagger": (
        "item",
        "dagger",
        "Found in a drawer labelled 'misc'. Still sharp enough to close a stale issue.",
    ),
    "Hotfix": (
        "item",
        "dagger",
        "Cut, patched and shipped before lunch. Nobody has reviewed it, and it is already in production.",
    ),
    "Intern's Staff": (
        "item",
        "staff",
        "Held together with tape and unearned confidence. It hits like a suggestion, but the spells still work.",
    ),
    "Staff of Eventual Consistency": (
        "item",
        "staff",
        "Its spells always land. Eventually. Possibly twice.",
    ),
    "Staff of Regex": (
        "item",
        "staff",
        "Matches every spell on the first try. About one cast in six also matches the caster, because nobody anchored the pattern.",
    ),
    "Force Merge": (
        "item",
        "mallet",
        "Pushes past a red check with the confidence of someone holding admin rights. The branch protection rule is still there; it just has a new exemption.",
    ),
    "Sudo Shiv": (
        "item",
        "dagger",
        "Asks for no permission and gets none, which turns out to be the same as having them all. Armour is mostly a policy, and policies have exceptions.",
    ),
    "Lockfile Locket": (
        "item",
        "locket",
        "Pins the first bad idea in the room to an exact version and refuses to update it. Whoever wears it has never once been surprised on a Monday.",
    ),
    "Dependabot Charm": (
        "item",
        "charm",
        "Opens a pull request every time your luck goes stale. It is usually right, and it is always loud about it.",
    ),
    "Squeaky Mallet": (
        "item",
        "mallet",
        "Squeaks on every impact. Deals real damage anyway, which is somehow worse.",
    ),
    "Hard Reset": (
        "item",
        "mallet",
        "Turns it off and on again. Mostly off.",
    ),
    "Lucky Rubber Duck": (
        "item",
        "charm",
        "Listens to your whole explanation without once interrupting. Has solved more bugs than the entire test suite. Holding it feels like ten extra years of experience, minus the back pain.",
    ),
    "Cloak of Mild Inconvenience": (
        "item",
        "cloak",
        "Grants +0 to everything. Nobody can say it does nothing, though, because it adds exactly one extra click to every attack. It is pretty useless, but at this point it is more work to take it off than to leave it on.",
    ),
    "Local Bludgeon": (
        "item",
        "bludgeon",
        "It worked on my laptop. One swing in four works on everyone else's machine, too. The rest of the time, it finds the user.",
    ),
    "Ring of Retries": (
        "item",
        "ring",
        "Whisper 'again' and the world rewinds. It works three times. Nobody remembers who owned it on the fourth.",
    ),
    "Crown of the Main Branch": (
        "item",
        "crown",
        "Whoever wears it decides what gets merged. It is heavier than it looks, and it never stops pinging. You notice an inscription on the inside of the band: \"No kings.\" How curious.",
    ),
}


# Items that change how a fight plays out. Everything else is for show.
# The rooms a foe can stand in (scenes.SCENES): scenery only, so no mechanics, just a title and two sentences.
ROOM_LORE = {
    "corridor": (
        "The Carpeted Corridor",
        "A long stone passage with a red runner that nobody has vacuumed since the last migration. The far end is dark in the way unmonitored services are dark.",
    ),
    "torches": (
        "The Torch Hall",
        "Two sconces flicker on a wall of old stone, the last evidence of a lighting migration that never finished. Everything here is warm, and nothing is documented.",
    ),
    "stairs": (
        "The Stair Landing",
        "A landing partway up a flight of stairs, with a daylit doorway at the top and stained glass that nobody owns. Everyone agrees it leads somewhere, and nobody has filed a ticket to find out where.",
    ),
    "castle": (
        "The Castle Corridor",
        "A brick corridor with flat grey floors and a steel door set into the right wall, built like a game from 1992. It ends in black, because the roadmap does.",
    ),
}
ROOM_VARIANTS = {"bluestone": ("castle", "Slimes and wyrms prefer the same corridor in dark blue stone, which clashes less with their complexions.")}

ITEM_EFFECTS = {
    "Lucky Rubber Duck": "+1 GRAY, no gray hairs required. Achievements still count only the GRAY you earned.",
    "Ring of Retries": "On a passing run, round 3 always ends the fight in your favour. The first two rounds are harder (-2 to hit). It cannot rescue a failing run.",
    "Cloak of Mild Inconvenience": "Every hit a foe lands on you does 1 less damage (never below 0).",
    "Crown of the Main Branch": "+1 to hit.",
    "Staff of Regex": "Spells cost 1 MP less (never below 1), but about one cast in six matches too much and also hits you.",
    "Force Merge": "Once per fight it ignores one failing result: your first miss becomes a hit, or the first hit against you is waved through, whichever comes first. It does not overrule fate on the last round.",
    "Sudo Shiv": "Your first attack each fight ignores armour and cannot miss.",
    "Lockfile Locket": "Blocks the first hit the foe lands on you each fight (never the finishing blow of a lost fight).",
    "Dependabot Charm": "Once per fight, a missed attack is rerolled. Dependabot bumps the roll.",
    "Hotfix": "Hits for +5, but about one swing in eight backfires on you. It shipped without review.",
    "Local Bludgeon": "Each round there is a 25% chance of a one-hit KO. Otherwise the swing backfires and you take the damage.",
}

# name -> lore for every spell in `spells.SPELLS` (unlock level, MP and effect come from the spell itself).
SPELL_LORE = {
    "Jade": "The first spell every Wizard learns, because it compiles on the first try. It does what the label says, and sometimes the foe looks tired afterwards.",
    "Confuse": "Feeds the foe a stack trace with no line numbers. It stumbles for a turn, which is the usual reaction.",
    "Hard Block": "A required review from someone who is on holiday. Nothing gets through until the round is over.",
    "Refactor": "Renames the staff, extracts a weapon from it and swears the behaviour is unchanged. The new weapon is gone again by the next round, as with every refactor.",
    "Supply Chain Attack": "Hits the foe, then the foe's dependencies, each link a little harder than the last. Nobody audited the second strike either.",
    "Pre-commit": "Spends a whole round running hooks and stays very still while it does. Whatever comes out next is formatted, linted and guaranteed to be critical.",
    "Zoltraak": "An old spell with a very short syntax and no known flags. It is one big hit and no subtlety, which is the point.",
}

# What each weapon family means in a fight (every weapon also lists its flat damage bonus).
CATEGORY_NOTES = {
    "dagger": "No spells, but every hit lands harder.",
    "mallet": "No spells, but every hit lands harder.",
    "bludgeon": "No spells, and a gamble every swing.",
    "staff": "A weak weapon, but only a Wizard holding a staff can cast spells.",
}

# Higher tiers: the same creature, promoted.
TIER_LORE = {
    1: "Has been here longer than the linter config and has opinions about your variable names.",
    2: "Only appears when someone two levels up needs 'a quick sync'. Nobody has left one cleanly.",
}


def lore_for(name: str) -> tuple[str, str, str]:
    return LORE.get(name, ("item", "charm", "Nothing is known about this one yet."))
