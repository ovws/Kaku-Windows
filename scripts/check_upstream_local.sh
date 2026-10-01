#!/usr/bin/env bash
# Local upstream check: update a tracking ref without changing the working branch.
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch --no-tags https://github.com/tw93/Kaku.git '+refs/heads/main:refs/remotes/kaku-upstream/main'
upstream_sha="$(git rev-parse refs/remotes/kaku-upstream/main)"
if git merge-base --is-ancestor "$upstream_sha" HEAD; then
  echo "UP_TO_DATE $upstream_sha"
else
  echo "UPDATE_AVAILABLE $upstream_sha"
  git log --oneline HEAD..refs/remotes/kaku-upstream/main
fi
