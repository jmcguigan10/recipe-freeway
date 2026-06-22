#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

files="$(git ls-files 'src/ruby/*.rb' | sort)"

if [[ -z "$files" ]]; then
  echo "No Ruby files found."
  exit 0
fi

while IFS= read -r file; do
  echo "ruby -c $file"
  ruby -c "$file"
done <<< "$files"
