#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

files="$(git ls-files 'src/python/*.py' | sort)"

if [[ -z "$files" ]]; then
  echo "No Python files found."
  exit 0
fi

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "error: neither python3 nor python is available" >&2
  exit 1
fi

"$python_bin" -m py_compile $files
