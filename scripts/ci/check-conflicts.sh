#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

status=0
while IFS= read -r file; do
  if grep -nE '^(<<<<<<<|=======|>>>>>>>)($| .*)' "$file"; then
    status=1
  fi
done < <(git ls-files)

if ((status != 0)); then
  echo "Merge conflict markers found." >&2
fi

exit "$status"
