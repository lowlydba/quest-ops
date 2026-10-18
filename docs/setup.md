# Setup and configuration

## GitHub Actions

```yaml
permissions:
  contents: write # saves your hero to the data branch
  actions: read # reads how the job went

steps:
  - uses: lowlysre/questops@v1
  - run: npm test
```

Put the step anywhere in the job. The main step only arms a post step. The encounter runs in that post step, after every other step has finished (`post-if: always()`). It reads the job's step results from the Actions API:

- **Failure:** any step failed.
- **Cancelled:** any step was cancelled. Nothing is played.
- **Success:** every step passed.

A step with `continue-on-error: true` counts as passed, matching how GitHub reports the job.

The encounter appears in three places:

- The log of the post step, named after the action.
- The job summary, as markdown.
- The data branch, unless `persist` is `false`.

QuestOps runs on Linux runners. It needs `python3` 3.11 or newer, plus `bash` and `git`, which GitHub's Ubuntu runners already have.

### Inputs

| Input | Default | What it does |
|---|---|---|
| `outcome` | `auto` | `success` or `failure` overrides the result. `auto` reads it from the Actions API, which needs `actions: read`. |
| `player` | the workflow actor | Hero name. A name always gets the same class and face. |
| `ignore` | | Players and bots that never play, separated by commas, spaces or newlines. Names match case-insensitively and `*` matches anything, so `*[bot], octocat` keeps every bot and octocat out of the dungeon. Nothing is played or saved for them, and a bot on the list never rolls for the merchant. |
| `data-branch` | `questops-data` | Branch that stores heroes, the quest log and the generated pages. |
| `data-repo` | this repository | `owner/repo` that holds the data branch. Point several repositories at one to share a leaderboard ([recipe](recipes.md#one-leaderboard-across-repositories)). |
| `data-token` | `token` | Token that pushes the data branch. Another repository needs a GitHub App token or a fine-grained PAT with contents write there. |
| `persist` | `true` | `false` plays a one-off encounter: nothing is saved, and the story has no stats, streaks or gear. |
| `comment` | `false` | `true` posts the encounter on a pull request as one compact comment, the hero's card and a one-line result with the story collapsed, that later runs edit instead of adding another. Does nothing outside pull request events. Needs `pull-requests: write`, which pull requests from forks never get, so there it only warns. The card only shows when the run is saved (`persist`). |
| `summary` | `true` | `false` keeps the encounter out of the job summary page. The job log and the pull request comment are unaffected. |
| `kind` | `random` | Force an encounter: `combat`, `treasure` or `trap`. |
| `seed` | | Fix the dice for a reproducible run. |
| `token` | `github.token` | Reads the job result and pushes the data branch. |

### Permissions

| Permission | Why |
|---|---|
| `contents: write` | Pushes the data branch. Not needed with `persist: false`. |
| `actions: read` | Reads this job's step results. Not needed when `outcome` is set. |
| `pull-requests: write` | Posts the pull request comment. Only needed with `comment: true`. |

If a ruleset or branch protection covers every branch, exclude the data branch, or the push is rejected.

Pull requests from forks get a read-only token, so the push fails with a warning. To give fork contributors a one-off encounter instead, use:

```yaml
- uses: lowlysre/questops@v1
  with:
    persist: ${{ github.event.pull_request.head.repo.fork != true }}
```

## The data branch

QuestOps creates the branch on first use, as an orphan branch with no shared history:

| Path | Contents |
|---|---|
| `README.md` | The Hall of Heroes: a leaderboard and every hero's card. |
| `QUESTLOG.md` | The last 50 encounters, linked to their commits. |
| `characters/<hero>.json` | The saved hero. This and the quest log are the source of truth. |
| `characters/<hero>.svg` | The character card. |
| `badges/<hero>/{level,kens,streak,record}.json` | shields.io endpoint badges. |
| `log/quests.jsonl` | Every encounter, one JSON object per line. |
| `lore/` | The bestiary and reliquary, with every monster and item, and their pixel art. |

Everything except the hero JSON and the quest log is generated. `questops rebuild --data-dir <checkout>` regenerates it all from those two.

### Embedding cards and badges

```markdown
![hero](https://raw.githubusercontent.com/OWNER/REPO/questops-data/characters/you.svg)
![level](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FOWNER%2FREPO%2Fquestops-data%2Fbadges%2Fyou%2Flevel.json)
```

Hero file names are the lowercase hero name, with anything other than letters, digits, `.`, `_` and `-` replaced by `-`.

> [!NOTE]
> Raw URLs only work for public repositories. In a private repository, the data branch's `README.md` still shows every card.

### Concurrent runs

Parallel jobs race to push the data branch. QuestOps never merges. Each run pulls the latest tip, plays its encounter and pushes. If another run pushed first, the attempt is thrown away and replayed on top of the new tip, up to 10 times with a growing random backoff. Only the attempt that sticks is printed and written to the job summary. The quest log also carries `merge=union` as a safety net.

Each hero plays once per commit. Re-running a workflow, or two jobs in one workflow, can neither farm wins nor stack losses. Without a commit, the run id is the key.

## Other CI systems and local use

Install from a checkout with `pip install .`, straight from GitHub with `pipx install git+https://github.com/lowlydba/questops`, or build the Docker image. QuestOps is not published to PyPI or a container registry yet. The CLI detects the player, commit and run from GitHub Actions, GitLab CI, Azure Pipelines and Jenkins environment variables. detects the player, commit and run from GitHub Actions, GitLab CI, Azure Pipelines and Jenkins environment variables.

```sh
bash scripts/data-branch.sh pull ./data questops-data "$REPO_URL"
questops quest --outcome "$CI_JOB_STATUS" --data-dir ./data
bash scripts/data-branch.sh push ./data questops-data
```

In GitLab, run these in `after_script`, where `CI_JOB_STATUS` holds the job result. `--outcome` accepts the usual words: `success`, `passed` and `ok` for a win, `failure`, `failed` and `error` for a loss, and `cancelled` or `skipped` for no encounter. `data-branch.sh push` exits with 75 when another run pushed first. Pull and replay in that case.

To let a command's exit code decide the fight, wrap it. The exit code is passed through:

```sh
questops quest -- make test
```

| Command | What it does |
|---|---|
| `questops quest` | Play an encounter. Takes `--outcome`, or a command after `--`. With neither, prints help. |
| `questops show --player <hero>` | Print a character sheet. |
| `questops codex` | List classes, levels, foes, loot, achievements and the heroes in a data dir. |
| `questops rebuild` | Regenerate cards, badges, lore and pages from the saved data. |

Common `quest` flags are `--player`, `--data-dir`, `--kind combat|treasure|trap`, `--seed`, `--context` (the label in the quest log) and `--dry-run` (a one-off encounter that saves nothing).

### Docker

```sh
docker build -t questops .
docker run --rm -v "$PWD/data:/data" questops quest --outcome success --player alice
```

The image keeps its data in `/data`. Arguments replace the default command, which is `quest --dry-run --outcome success`: with none, the image plays a one-off winning encounter and saves nothing. To keep heroes, mount a volume and pass your own `quest` arguments, as above. The image needs `git` and `bash` for `scripts/data-branch.sh`, so it includes both.

## Environment variables

| Variable | What it does |
|---|---|
| `QUESTOPS_PLAYER` | Hero name, ahead of the CI actor and `$USER`. |
| `QUESTOPS_OUTCOME` | Outcome when `--outcome` isn't given. |
| `QUESTOPS_DATA_DIR` | Default `--data-dir`. |
| `QUESTOPS_ALLOW_BOTS` | Any value lets bot accounts play like heroes. |
| `QUESTOPS_IGNORE` | Default `--ignore`: players and bots that never play, as in the action's `ignore` input. |
| `QUESTOPS_COLOR` | `1` forces colour and `0` turns it off. `NO_COLOR` and `FORCE_COLOR` are honoured too. |
| `QUESTOPS_PIXELS` | Pixel style when colour is on: `half` (default in terminals), `solid` (default in GitHub Actions, one colour per text cell so the log viewer can't smear it), `square` (larger) or `plain` (shade glyphs). |
| `QUESTOPS_GIT_NAME`, `QUESTOPS_GIT_EMAIL` | Author of data branch commits. |

## Terminals and colour

Pixel art uses half-block characters in 256 colours, so it needs a UTF-8 terminal. In GitHub Actions each character cell is one colour, because GitHub's log viewer smears two-colour cells; terminals get two pixels of colour per cell. Colour is on in CI logs and interactive terminals, and off when piped. With colour on, each monster stands in one of four scenes: a carpeted corridor, a torch-lit wall, a stair landing or a castle corridor drawn like an early-90s raycaster (red brick, or dark blue stone behind the slime and the wyrm, whose colours clash with red). Without colour, sprites fall back to shade glyphs and the scene is skipped.

On Windows PowerShell 5.1, piped output shows garbled blocks like `ΓûÆ`. Run `[Console]::OutputEncoding = [Text.Encoding]::UTF8` first. QuestOps itself always writes UTF-8.

## Troubleshooting

Problems show up as warnings in the post step. They never fail your job.

| Warning | Fix |
|---|---|
| `jobs API returned 403 (does the token have actions: read?)` | Add `actions: read`, or set `outcome`. |
| `could not identify the current job` | The Actions API didn't list this job on this runner. Set `outcome` to skip detection. |
| `could not push the data branch` | Add `contents: write`, or with `data-repo`, check `data-token` can write there. Also check rulesets on the data branch, or fork pull requests (see [Permissions](#permissions)). |
| `gave up after repeated races for the data branch` | More than 10 runs pushed at once. The next run catches up, since nothing is lost but this encounter. |
| `python3 not found on this runner` | Install Python 3.11 or newer, for example with `actions/setup-python`. |
