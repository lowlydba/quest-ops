# How the game works

## One run, one encounter

When a job finishes, its result decides what happens next:

| Encounter | Failing run | Passing run |
|---|---|---|
| Monster fight | Lost | Won about 90% of the time |
| Treasure chest | A mimic bites | Always loot |
| Trap | Sprung | Dodged about 80% of the time |

A failing run is always a loss. A passing run is usually a win, but the dungeon still rolls dice. The Ring of Retries makes a passing fight a sure win.

A win earns XP, 'kens and sometimes loot, and extends your streak. A loss earns a little XP, drops a tenth of your 'kens and breaks the streak. A cancelled or skipped job plays nothing. There is nothing to spend 'kens on, and nobody has a theory about what they are for, but the number going up feels correct.

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

| Weapon | Class | Rarity | Damage | Effect |
|---|---|---|---|---|
| Rusty Dagger | Rogue | common | +2 | |
| Hotfix | Rogue | rare | +5 | About one swing in eight backfires on you. |
| Sudo Shiv | Rogue | legendary | +7 | Your first attack each fight ignores armour and can't miss. |
| Squeaky Mallet | Fighter | common | +2 | |
| Local Bludgeon | Fighter | uncommon | +0 | Each round, a 25% chance of a one-hit KO. Otherwise it backfires. |
| Hard Reset | Fighter | rare | +6 | |
| Force Merge | Fighter | rare | +4 | Once per fight, ignores one failing result: a miss becomes a hit, or a hit on you is waved through. |
| Intern's Staff | Wizard | common | +0 | Lets a Wizard cast. |
| Staff of Regex | Wizard | rare | +1 | Spells cost 1 MP less, but about one cast in six matches too much and hurts you too. |
| Staff of Eventual Consistency | Wizard | rare | +2 | Lets a Wizard cast. |

| Accessory | Rarity | Effect |
|---|---|---|
| Lucky Rubber Duck | common | +1 GRAY. |
| Dependabot Charm | uncommon | Once per fight, a missed attack is rerolled. |
| Cloak of Mild Inconvenience | uncommon | Takes 1 off every hit you take. |
| Ring of Retries | rare | A passing fight is always won in round 3, at -2 to hit in the first two rounds. It can't rescue a failing run. |
| Lockfile Locket | rare | Blocks the first hit a foe lands on you each fight. |
| Crown of the Main Branch | legendary | +1 to hit. |

### Sets

Wear both halves of a set and its bonus applies. The active set shows on your card.

| Set | Weapon + accessory | Bonus |
|---|---|---|
| Hotfix Friday | Hotfix + Cloak of Mild Inconvenience | Hotfix backfires are absorbed. |
| Dependency Hell | Staff of Regex + Lockfile Locket | "Matches too much" never hurts you. |
| Retry Loop | Hard Reset + Ring of Retries | No -2 to hit from the Ring. |
| Pair Programming | Squeaky Mallet + Lucky Rubber Duck | +1 to hit in round 1. |
| Zero Trust | Sudo Shiv + Lockfile Locket | Every attack ignores armour. |

## Spells

Only Wizards cast, and only with a staff in hand. A Wizard without a staff fights bare-handed. Spells unlock by level, and each round the Wizard casts one they've unlocked and can afford. Spell damage adds the staff's bonus. The last round is always Jade.

| Spell | Unlocks | MP | Effect |
|---|---|---|---|
| Jade | Lv 1 | 2 | A plain bolt. About half the time it leaves the foe Weary, which looks dramatic and does nothing. |
| Confuse | Lv 2 | 2 | No damage, but the foe's attack this round misses. |
| Hard Block | Lv 3 | 2 | No damage, but a ward absorbs the foe's attack this round. |
| Refactor | Lv 4 | 3 | The staff becomes a random other weapon for a round. Next round you attack with it, quirks included, then it reverts. |
| Supply Chain Attack | Lv 5 | 4 | Two hits in one round. The second hits harder if the first landed. |
| Pre-commit | Lv 6 | 5 | Gather energy this round. Next round's attack is a guaranteed critical. |
| Zoltraak | Lv 7 | 4 | One big hit, about twice a normal hit's damage dice. |

## Bots and the traveling merchant

Bots (the Actions bot, Dependabot, Renovate and friends) don't quest. Each bot run rolls a d20 instead. A natural 20 brings a Traveling Merchant, who buys up to three unequipped items from a random hero's bag for 'kens. A hero with nothing at all, no weapon, accessory or bag, can be picked too: the merchant says it's dangerous to go alone and hands over a basic weapon for their class (a Squeaky Mallet, Rusty Dagger or Intern's Staff). Every other roll, the dungeon stays quiet.

The roll is seeded by the commit, so re-running a bot's workflow gets the same number. Each bot sends its own merchant.

## The full list

`questops codex` prints every class, level threshold, foe, item, spell, set and achievement. The data branch's `lore/` pages describe each one, with its art.
