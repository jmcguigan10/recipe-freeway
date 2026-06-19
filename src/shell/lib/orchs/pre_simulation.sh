#!/usr/bin/env bash

[[ -n "${MUSE_PIPELINE_PRE_SIMULATION_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_PRE_SIMULATION_SH_LOADED=1

loader_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
# shellcheck source=../loader.sh
source "$loader_dir/loader.sh"
