# QuestOps agent notes

One CI run is one text-dungeon encounter. The CLI/Action plays it, stores heroes as JSON on a data branch, and renders cards and lore pages. Python stdlib only (no runtime dependencies).

## Layout

| Path | What lives there |
|---|---|
| `src/quest-opsengine.py` | Encounters, `MONSTERS`, `TIERS` (Senior / Skip Level), `ACHIEVEMENTS`; records a typed transcript |
| `src/quest-opsfight.py` | One monster fight (3 rounds, fate decides the last): spells, weapon quirks, accessory effects and set bonuses |
| `src/quest-opsspells.py` | `SPELLS` (unlock level, MP, effect); only a Wizard holding a staff casts |
| `src/quest-opsevents.py` | Transcript events (`Art`, `Narration`, `Round`, `Retreat`); every renderer consumes these |
| `src/quest-opsitems.py` | `ITEMS` (`Item`: name, rarity, category, slot, class, damage bonus), `SETS` (weapon + accessory pairs), rarity weights, equip rules (weapons are class-locked) |
| `src/quest-opslore.py` | `LORE` (every monster and item), `ROOM_LORE` (every scene), `SPELL_LORE`, `ITEM_EFFECTS`, `TIER_LORE` |
| `src/quest-opssprites.py` | Pixel sprites and palettes (`SPRITES`, `MONSTER_RAMPS`, `MONSTER_TIERS`, `ITEM_SPRITES`); builds pixel grids |
| `src/quest-opspixels.py` | Pixel grid (`Px`) and swappable cell backends: `half` (default), `square`, `plain`; coalesces same-colour runs. `QUESTOPS_PIXELS=half\|square\|plain` overrides (never auto-switched in CI) |
| `src/quest-opsscenes.py` | Background scenes a monster stands in (`SCENES`: corridor, torches, stairs, castle; `suit` swaps the castle for blue stone behind the slime and the wyrm), computed in RGB and snapped to xterm-256; `TIER_LIGHT` tints the stone per tier. `game.play` picks one with `pick_scene` from its own hash of the seed, so the dice are untouched; colour output only |
| `src/quest-opspages.py` | Generates every lore page and image (`lore_files`): bestiary, reliquary (with Sets), `lore/spellbook.md`, the merchant's page |
| `src/quest-opsmerchant.py` | The traveling merchant: a bot run rolls a d20 and only a natural 20 summons it (`QUESTOPS_MERCHANT_ODDS` maps to a threshold; prices in `items.SELL_PRICE`) |
| `src/quest-opsrender.py`, `art.py`, `svg.py`, `title.py` | Terminal card, layout helpers, character card SVG, hall of heroes, title |
| `src/quest-opspresentation.py` | `Presentation`: ephemeral (`--dry-run`) / colour / pixel backend, and the one place that decides what is shown and how wide |
| `src/quest-opscli.py` | argparse and wiring only |
| `src/quest-opsgame.py` | `play()` / `play_merchant()` return a `Quest` / `MerchantRun` (hero, result, log entry, outputs); no I/O |
| `src/quest-opssite.py` | Writes the data branch: cards, badges, lore, log page, hall; saves the hero and appends the log |
| `src/quest-opsci.py` | CI environment detection, step summary and step outputs |
| `dist/index.js`, `action.yml` | GitHub Action shim (post-job hook) |

## When you change items, monsters, tiers or achievements

Lore pages must always match the game. For **any** add, rename, removal or rule change to an item, set, monster (including its tiers), achievement, spell or mechanic, do all of these in the same change:

1. **Game data**: edit `items.py` / `engine.py` / `spells.py` / `fight.py`. A new item needs a slot (`weapon` or `accessory`), a class if it is a weapon, and an icon category in `sprites.ITEM_SPRITES`; a new weapon family also needs a line in `lore.CATEGORY_NOTES`; a new monster needs `SPRITES`, `MONSTER_RAMPS` and (for variants) `MONSTER_TIERS`; a new spell needs a `spells.SPELLS` entry (unlock level, MP, effect); a new set goes in `items.SETS` with its two-sentence lore; a new scene needs a `lore.ROOM_LORE` entry (title and two sentences) and a variant goes in `lore.ROOM_VARIANTS`.
2. **Lore**: add or update the entry in `lore.LORE` (two sentences, dry CI humour); every spell needs a two-sentence `lore.SPELL_LORE` entry. If the item changes how a fight plays, add its rule to `lore.ITEM_EFFECTS`. If tiers change, update `lore.TIER_LORE` and the thresholds in `engine.TIERS` and `pages.py` text.
3. **Pages**: never hand-edit generated files. `pages.lore_files()` builds `lore/README.md` (including the Sets section), `lore/spellbook.md`, `lore/monsters/*`, `lore/items/*`, `lore/rooms/*` and `lore/img/*`, including every tier's sprite and every room's picture. Run a quest against a scratch `--data-dir` to regenerate them and look at the result (bestiary index, the entry page, variants table, reliquary row, spellbook, sets).
4. **Docs and output**: update `docs/gameplay.md` (and the README pitch if it no longer holds) when rules change, run `python scripts/docs_images.py` if art, cards or narration changed, and check `questops codex` lists the change (it prints foes, loot, sets and spells). Active sets show on the terminal card, the job summary and the SVG card.
5. **Tests**: `tests/test_lore.py` fails when an item, monster or room lacks lore, an icon, a sprite or a picture; `tests/test_extras.py` covers spell and set lore. Add a test for any new mechanic (`tests/test_fight.py` uses a scripted `Dice` rng for fight rules).

If a step does not apply, say why in the PR description.

## Conventions

- Content is deliberately small and carefully chosen. Avoid generic fantasy filler and D&D-isms; prefer CI/engineering humour.
- Currency is written `'kens` (lowercase, leading apostrophe).
- The terminal card uses single-width glyphs only; emojis belong in markdown pages.
- A failed run is always a loss. A passing run is a sure win in a chest, about 80% in a trap (`TRAP_WIN_ODDS`) and about 90% in a monster fight (`WIN_ODDS`); the Ring of Retries makes the fight certain.
- One counted encounter per hero per commit (or run). Bots are skipped.
- Never merge on the data branch. `scripts/data-branch.sh push` exits 75 when another run won the race, and the Action shim pulls and redoes the quest on the new tip. Derived files must be rebuildable from `characters/*.json` and `log/quests.jsonl` (`questops rebuild`); lore pages are static.
- Sprites are pixel art with 256 colours; keep output UTF-8. Never emit truecolor, and never fake a pixel with a bare space (log viewers drop its background). Terminals draw two colours per half-block cell (`half`), but GitHub's log viewer paints a background over the whole line and a glyph over a shorter box, so in GitHub Actions every cell is one colour (`solid`). Draw key details (eyes, mouths, teeth) at least 2 pixels tall on even rows so they survive `solid`, and draw small text as a `pixels.Label`, not as pixels.
- Bots never play. They roll a d20 (`merchant.visit`, seeded by the commit or run): only a natural 20 triggers the merchant (`merchant.py`), and the roll is printed with an ASCII die, written to the step summary and to the `merchant_roll` step output. The Actions bot has a hand-drawn merchant, others are generated in `sprites.merchant_look`. Keep NPC looks (hat and beard) distinct from player portraits.
- Terminal narration colours are applied in `render.colorize_narration`, never in engine text; plain, dry-run and markdown output never contain escapes.
- Classes start with different HP, MP and GRAY (`state.CLASS_STATS`). Achievements use `natural_gray` (level only).

## Checks

[docs/development.md](docs/development.md) has the commands, the CI and e2e coverage, and the test hooks. In short:

```sh
python -m coverage run -m pytest   # then: python -m coverage report (must stay at 100%)
node --test tests/shim/shim.test.js tests/shim/modules.test.js   # the Action shim; the git tests need bash on Linux
```

If a globally installed pytest plugin interferes, run with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

Docs: `README.md` is the product page (pitch, quick start, art). Setup and operations live in `docs/setup.md`, rules in `docs/gameplay.md` and contributor notes in `docs/development.md`.
