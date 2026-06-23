#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

git ls-files --cached --others --exclude-standard '*.sh' 'configs/*.sh' |
  while IFS= read -r file; do
    [[ -f "$file" ]] || continue
    printf '%s\n' "$file"
  done |
  sort -u |
  while IFS= read -r file; do
  case "$file" in
    src/slurm/samples/*)
      continue
      ;;
  esac

  echo "bash -n $file"
  bash -n "$file"
done
