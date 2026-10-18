#!/usr/bin/env bash
# Sync the QuestOps data branch. Works with any git host/CI.
#   data-branch.sh pull <dir> [branch] [remote_url]
#   data-branch.sh push <dir> [branch] [message]   (exit 75: lost a race, pull and redo)
# Auth comes from the remote URL or the CI's existing git credentials.
set -euo pipefail

cmd="${1:?pull|push}"; dir="${2:?dir}"; branch="${3:-questops-data}"

case "$cmd" in
  pull)
    url="${4:-$(git config --get remote.origin.url)}"
    rm -rf "$dir"
    if git ls-remote --exit-code --heads "$url" "$branch" >/dev/null 2>&1; then
      git clone --quiet --depth 1 --branch "$branch" "$url" "$dir"
    else
      mkdir -p "$dir"
      git -C "$dir" init --quiet
      git -C "$dir" checkout --quiet --orphan "$branch"
      git -C "$dir" remote add origin "$url"
    fi
    ;;
  push)
    msg="${4:-questops: update character sheet}"
    cd "$dir"
    git config user.name  "${QUESTOPS_GIT_NAME:-QuestOps Bot}"
    git config user.email "${QUESTOPS_GIT_EMAIL:-questops@users.noreply.local}"
    git add -A
    if git diff --cached --quiet; then echo "questops: nothing to commit"; exit 0; fi
    git commit --quiet -m "$msg"
    # Never merge: if another run pushed first, report it (exit 75) and let the caller start over
    # from the new tip, so concurrent runs cannot conflict over generated files.
    if out="$(git push origin "HEAD:$branch" 2>&1)"; then exit 0; fi
    if grep -qiE "rejected|non-fast-forward|fetch first|failed to update ref" <<<"$out"; then
      echo "questops: another run pushed first" >&2; exit 75
    fi
    echo "$out" >&2; exit 1
    ;;
  *) echo "usage: $0 pull|push <dir> [branch]" >&2; exit 2 ;;
esac
