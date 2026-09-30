#!/usr/bin/env bash
# Prepare an upstream merge locally; never push or publish.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Commit or stash existing changes before syncing upstream.' >&2
  exit 1
fi
ref="${1:-main}"
if [[ "$ref" == -* ]] || ! git check-ref-format "refs/heads/$ref"; then
  echo 'Expected an upstream branch or tag name.' >&2
  exit 1
fi
git fetch --no-tags https://github.com/tw93/Kaku.git "$ref"
upstream_sha="$(git rev-parse FETCH_HEAD)"
if git merge-base --is-ancestor "$upstream_sha" HEAD; then
  echo "Already includes upstream $ref ($upstream_sha)."
  exit 0
fi
branch="sync/upstream-${upstream_sha:0:12}"
git switch -c "$branch"
if ! git merge --no-ff "$upstream_sha" -m "Merge Kaku upstream $ref (${upstream_sha:0:12})"; then
  echo "Merge conflicts remain on $branch. Resolve them preserving Windows adaptations, then commit." >&2
  exit 1
fi
echo "Prepared $branch with upstream $upstream_sha. Review and run Windows Build before release."
