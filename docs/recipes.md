# Recipes

Three ways to lay out the data, from the default to a leaderboard shared across repositories.

## One repository, one leaderboard

The default: every workflow and branch in the repository feeds a single `questops-data` branch.

```yaml
name: ci
on: [push, pull_request]

permissions:
  contents: write
  actions: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: lowlysre/questops@v1
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: npm test
```

A hero plays once per commit. If several jobs or workflows run the action on the same commit, the first to finish plays and the rest skip. Put the step in the job whose result you care about, usually the main test job.

## Several leaderboards in one repository

Give each leaderboard its own `data-branch`. Each branch keeps its own heroes, quest log and Hall of Heroes, so a player can be level 12 on one and level 2 on another.

```yaml
# .github/workflows/backend.yml
- uses: lowlysre/questops@v1
  with:
    data-branch: questops-backend

# .github/workflows/frontend.yml
- uses: lowlysre/questops@v1
  with:
    data-branch: questops-frontend
```

Dedupe is per branch, so the same commit can play once on each.

## One leaderboard across repositories

Several repositories can write to one data branch in a shared repository, so a player's hero follows them from repo to repo.

1. Create the shared repository, for example `your-org/questops-guild`. It can be empty: QuestOps creates the data branch on first use.
2. Get a token that can push to it. A GitHub App installed on the shared repository with **Contents: read and write** is best. A fine-grained personal access token scoped to that repository also works.
3. In every repository that plays, point `data-repo` at the shared repository and pass the token as `data-token`:

```yaml
permissions:
  contents: read
  actions: read # still needed: the job result is read from this repository

steps:
  - uses: actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510 # v3.3.0
    id: guild
    with:
      client-id: ${{ vars.QUESTOPS_APP_CLIENT_ID }}
      private-key: ${{ secrets.QUESTOPS_APP_PRIVATE_KEY }}
      repositories: questops-guild
      permission-contents: write
  - uses: lowlysre/questops@v1
    with:
      data-repo: your-org/questops-guild
      data-token: ${{ steps.guild.outputs.token }}
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  - run: npm test
```

`token` keeps reading this job's result with the run's own `github.token`. `data-token` is only used to push to the shared repository.

Multiple writers are safe. Concurrent runs never merge: a run that loses the push race throws its encounter away and replays it on the new tip, up to 10 times. Each entry in the quest log records the repository it came from. Commits differ between repositories, so dedupe still means once per commit.

> [!WARNING]
> Every repository that holds the token can rewrite the shared data branch. Scope the token to the shared repository and nothing else. Keep it out of workflows that run for pull requests from forks.

Card and badge URLs point at the shared repository. Raw URLs only work if that repository is public.
