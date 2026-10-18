# How the game works

## One run, one encounter

When a job finishes, its result decides what happens next:

| Encounter | Failing run | Passing run |
|---|---|---|
| Monster fight | Lost | Won about 90% of the time |
| Treasure chest | A mimic bites | Always loot |
| Trap | Sprung | Dodged about 80% of the time |

A failing run is always a loss. A passing run is usually a win, but the dungeon still rolls dice. The Ring of Retries makes a passing fight a sure win.

A win earns XP, 'kens and sometimes loot, and extends your streak. A loss earns a little XP, drops a tenth of your 'kens and breaks the streak. A cancelled or skipped job plays nothing. There is nothing to spend 'kens on, and nobody has a theory about what they are for, but the number going up feels correct. Balances over 10,000 roll up into **toh** ("toh 'kens", say it out loud). 'kens are bronze and a toh is silver, so 12,345 'kens reads as 1 toh 2,345 'kens. Gains, prices and the stored total stay in plain 'kens.

Each hero plays once per commit, so re-running a workflow can't farm wins or stack losses.

## Heroes

Your player name decides your class and your pixel-art face, so you get what you get. There's nothing to allocate.

| Class | Hits with | Starts with | Grows |
|---|---|---|---|
| Fighter | d10 | the most HP | sturdiest |
| Rogue | d8 | the sharpest attacks (+2 GRAY) | balanced |
| Wizard | d6, and spells | the most MP | most mana |

Every hero has three numbers, all derived from level:

- **HP:** how much punishment you take in a fight.
- **MP:** what spells cost.
- **GRAY:** short for gray hairs, the hard-won seniority added to attack and skill rolls.

Levels come slowly. Level 2 takes about 10 wins, level 5 about 300 and level 10 about 2,500. A winning streak adds up to 50% more XP.

## Monsters

Fights last three rounds. Fate decides the last one, so a passing run's final blow always lands and a failing run's never does. Tougher Senior foes appear from level 5, and Skip Level foes from level 10. They have more HP, hit harder and pay more. In colour, the room lights up to match: cold blue for Senior and red-violet for Skip Level.

The data branch's bestiary has every foe, its tiers and its lore.

## Loot

You wield one weapon and wear one accessory. A new item is equipped automatically when it's rarer than what you have; otherwise it goes in your bag. A spare of something you already own is sold on the spot for the merchant's price. Weapons are class-locked, while accessories suit anyone. When a quest finds an item, the output shows its stats, any set it belongs to, and whether it was equipped or bagged and why.

Every weapon and accessory, with its damage, rarity, effect and lore, is in the data branch's [reliquary](https://github.com/lowlydba/quest-ops/blob/questops-data/lore/README.md), or run `questops codex`.

### Sets

Wear both halves of a set and its bonus applies. The active set shows on your card. The reliquary lists every set and its bonus.

## Spells

Only Wizards cast, and only with a staff in hand. A Wizard without a staff fights bare-handed. Spells unlock by level, and each round the Wizard casts one they've unlocked and can afford. Spell damage adds the staff's bonus. The last round is always Jade.

Every spell, with its unlock level, MP cost, effect and lore, is in the data branch's [Spellbook](https://github.com/lowlydba/quest-ops/blob/questops-data/lore/spellbook.md), or run `questops codex`.

## Bots and the traveling merchant

Bots (the Actions bot, Dependabot, Renovate and friends) don't quest. Each bot run rolls a d20 instead. A natural 20 brings a Traveling Merchant, who buys up to three unequipped items from a random hero's bag for 'kens. A hero with nothing at all, no weapon, accessory or bag, can be picked too: the merchant says it's dangerous to go alone and hands over a basic weapon for their class (a Squeaky Mallet, Rusty Dagger or Intern's Staff). Every other roll, the dungeon stays quiet.

The roll is seeded by the commit, so re-running a bot's workflow gets the same number. Each bot sends its own merchant.

## The full list

`questops codex` prints every class, level threshold, foe, item, spell, set and achievement. The data branch's `lore/` pages describe each one, with its art.
