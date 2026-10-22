# Development

[AGENTS.md](../AGENTS.md) maps the code and lists the conventions, including the checklist for adding monsters, items, spells and sets. Run the tests with:

```sh
python -m pip install pytest coverage
python -m coverage run -m pytest      # Python, must stay at 100% line and branch coverage
python -m coverage report
node --test tests/shim/shim.test.js tests/shim/modules.test.js   # the Action's Node shim
```

If a globally installed pytest plugin interferes, set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.

The shim tests that push to a throwaway git remote need `bash` and skip on Windows. CI runs them on Linux.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request:

- **Python:** the full suite with a 100% coverage gate, on Linux, Windows and macOS, with Python 3.11 and 3.14.
- **Node shim:** tests on Node 20 and 24, with a 100% line, branch and function gate on Node 24.
- **Scripts:** shellcheck on `scripts/data-branch.sh` and a Docker build and smoke run.
- **Workflows:** [zizmor](https://docs.zizmor.sh/) with the pedantic persona.

`.github/workflows/e2e.yml` plays the real Action on GitHub against a throwaway data branch, then checks the result with `tests/e2e/verify.py`:

- Six concurrent heroes racing to push.
- Outcome detection for a passing job, a failing job and a `continue-on-error` step.
- One commit played twice.
- `persist: false` and a bot actor.
- A bot rolling a natural 20, so the merchant buys from a seeded hero's bag.
- `questops rebuild` reproducing every derived file.

Its "failing job" fails on purpose. The workflow keeps the newest run's data branches, so the card links in its job summaries still resolve.

`.github/workflows/demo.yml` is the live demo: pushes to main play one encounter into the persistent `questops-data` branch, and pull requests get a one-off encounter as a sticky comment.

For a local smoke run with [act](https://github.com/nektos/act), which can't read job results, use `act -W .github/act/e2e-act.yml`.

## Test hooks

| Variable | What it does |
|---|---|
| `QUESTOPS_MERCHANT_ODDS` | Chance of the traveling merchant, `0` to `1`. |
| `QUESTOPS_MERCHANT_ROLL` | Fixes a bot's d20 roll, `1` to `20`. |
| `QUESTOPS_RETRY_DELAY_MS` | Fixed backoff between data branch push retries. |
| `QUESTOPS_JOB_RETRY_MS` | Delay between Actions API retries while a job's steps settle (default 5000, up to 12 tries). |

## README images

`docs/img/` is generated from the game. After changing the title, sprites, scenes, cards or narration, regenerate it with:

```sh
python scripts/docs_images.py
```
