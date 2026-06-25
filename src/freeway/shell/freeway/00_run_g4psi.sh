#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck source=../lib/loader.sh
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../../../.." && pwd -P)"
source "$repo_root/src/freeway/shell/lib/loader.sh"

freeway_stage_main "g4psi" "$@"
