#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

files="$(
  git ls-files --cached --others --exclude-standard src/freeway/python src/ml/python |
    while IFS= read -r file; do
      [[ -f "$file" && "$file" == *.py ]] && printf '%s\n' "$file"
    done |
    sort
)"

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

"$python_bin" - $files <<'PY'
import pathlib
import sys

failed = False
for path in sys.argv[1:]:
    try:
        source = pathlib.Path(path).read_text()
        compile(source, path, "exec")
    except SyntaxError as exc:
        failed = True
        print(f"{path}:{exc.lineno}:{exc.offset}: {exc.msg}", file=sys.stderr)

sys.exit(1 if failed else 0)
PY
