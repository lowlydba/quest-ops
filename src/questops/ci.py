"""What the CI environment tells us, and the CI-facing outputs (step summary, step outputs)."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from .state import slug


def env(*names: str, default: str = "") -> str:
    for n in names:
        if os.environ.get(n):
            return os.environ[n]
    return default


def detect_player() -> str:
    return env("QUESTOPS_PLAYER", "GITHUB_ACTOR", "GITLAB_USER_LOGIN", "BUILD_REQUESTEDFOR", "USER", "USERNAME", default="adventurer")


def detect_commit() -> tuple[str, str, bool]:
    """(sha, commit url, whether it came from CI). Falls back to the local git checkout for the log."""
    sha = env("GITHUB_SHA", "CI_COMMIT_SHA", "BUILD_SOURCEVERSION", "GIT_COMMIT", "CIRCLE_SHA1")
    in_ci = bool(sha)
    if not sha:
        try:
            out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
            sha = out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            sha = ""
    url = ""
    if sha and os.environ.get("GITHUB_REPOSITORY"):
        url = f"{env('GITHUB_SERVER_URL', default='https://github.com')}/{os.environ['GITHUB_REPOSITORY']}/commit/{sha}"
    elif sha and os.environ.get("CI_PROJECT_URL"):
        url = f"{os.environ['CI_PROJECT_URL']}/-/commit/{sha}"
    return sha, url, in_ci


def detect_run_id() -> str:
    return env("GITHUB_RUN_ID", "CI_PIPELINE_ID", "BUILD_BUILDID", "BUILD_NUMBER", default="local")


def detect_context() -> str:
    repo = env("GITHUB_REPOSITORY", "CI_PROJECT_PATH", "BUILD_REPOSITORY_NAME")
    job = env("GITHUB_WORKFLOW", "CI_JOB_NAME", "BUILD_DEFINITIONNAME")
    return " / ".join(x for x in (repo, job) if x)


@dataclass(frozen=True)
class Run:
    commit: str
    commit_url: str
    in_ci: bool
    run_id: str

    @property
    def key(self) -> str:
        """One counted encounter per hero per commit (or per run when there is no commit),
        so re-running a workflow can neither farm wins nor stack up losses."""
        return self.commit if self.in_ci else ("" if self.run_id == "local" else self.run_id)


def detect_run() -> Run:
    commit, url, in_ci = detect_commit()
    return Run(commit, url, in_ci, detect_run_id())


def is_bot(name: str) -> bool:
    """github-actions[bot], dependabot[bot], renovate[bot], and friends."""
    n = name.strip().lower()
    return n.endswith("[bot]") or n in {"github-actions", "dependabot", "renovate", "ghost"}


def is_ignored(name: str, patterns: str) -> bool:
    """Whether `name` is on a comma, space or newline separated ignore list. Names match case-insensitively,
    and `*` matches anything, so `*[bot]` skips every bot."""
    n = name.strip().lower()
    for p in re.split(r"[\s,]+", patterns.lower()):
        if p and re.fullmatch(".*".join(re.escape(part) for part in p.split("*")), n):
            return True
    return False


def data_url(dry_run: bool) -> str:
    """The base URL of the data branch's files, for links from the job log, summary and comment. Empty when
    nothing is saved there, so there is nothing to link."""
    repo = os.environ.get("QUESTOPS_DATA_REPO") or os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("QUESTOPS_DATA_BRANCH")
    if dry_run or not (repo and branch):
        return ""
    return f"{env('GITHUB_SERVER_URL', default='https://github.com')}/{repo}/blob/{branch}/"


def card_url(name: str, dry_run: bool) -> str:
    """Where the hero's SVG card will live on the data branch, for the job summary to embed."""
    base = data_url(dry_run)
    return f"{base}characters/{slug(name)}.svg?raw=true" if base else ""


def write_outputs(pairs: dict) -> None:
    """Step outputs for later workflow steps ($GITHUB_OUTPUT)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in pairs.items():
                f.write(f"{k}={v}\n")


def write_summary(markdown: str) -> None:
    """Append to the job summary ($GITHUB_STEP_SUMMARY)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown)


def write_comment(markdown: str) -> None:
    """The compact version of the summary for a pull request comment ($QUESTOPS_COMMENT_FILE, set by the action)."""
    path = os.environ.get("QUESTOPS_COMMENT_FILE")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown)
