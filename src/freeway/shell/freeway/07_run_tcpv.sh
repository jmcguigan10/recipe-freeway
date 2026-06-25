#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../../../.." && pwd -P)"
source "$repo_root/src/freeway/shell/lib/loader.sh"

freeway_stage_main "tcpv" "$@"
