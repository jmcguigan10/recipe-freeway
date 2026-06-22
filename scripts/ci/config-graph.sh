#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2))); then
  echo "config graph check requires Bash 4.2+; found $BASH_VERSION" >&2
  exit 2
fi

fail() {
  echo "config graph check failed: $*" >&2
  exit 1
}

source configs/physics.sh
source configs/slurm.sh
source configs/g4psi.sh
source configs/recipes.sh

[[ ${#FREEWAY_STAGE_ORDER[@]} -gt 0 ]] || fail "FREEWAY_STAGE_ORDER is empty"

declare -A stage_seen=()
declare -A stage_index_by_name=()

for index in "${!FREEWAY_STAGE_ORDER[@]}"; do
  stage="${FREEWAY_STAGE_ORDER[$index]}"
  [[ -n "$stage" ]] || fail "empty stage name at index $index"
  [[ -z "${stage_seen[$stage]:-}" ]] || fail "duplicate stage in FREEWAY_STAGE_ORDER: $stage"
  stage_seen[$stage]=1
  stage_index_by_name[$stage]="$index"

  [[ -n "${FREEWAY_STAGE_SCRIPT[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_SCRIPT"
  [[ -f "src/shell/freeway/${FREEWAY_STAGE_SCRIPT[$stage]}" ]] || fail "$stage script not found: ${FREEWAY_STAGE_SCRIPT[$stage]}"
  [[ -n "${FREEWAY_STAGE_OUTPUT[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_OUTPUT"
  [[ -n "${FREEWAY_STAGE_TREE[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_TREE"

  if [[ "$stage" != "g4psi" ]]; then
    [[ -n "${FREEWAY_STAGE_RECIPE[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_RECIPE"
    [[ "${FREEWAY_STAGE_RECIPE[$stage]}" == muse:* ]] || fail "$stage recipe must use muse: prefix"
  fi
done

for stage in "${!FREEWAY_STAGE_SCRIPT[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_SCRIPT has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_OUTPUT[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_OUTPUT has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_TREE[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_TREE has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_RECIPE[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_RECIPE has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_INPUTS[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_INPUTS has unknown stage: $stage"
  for dep in ${FREEWAY_STAGE_INPUTS[$stage]}; do
    [[ -n "${stage_seen[$dep]:-}" ]] || fail "$stage depends on unknown stage: $dep"
    ((stage_index_by_name[$dep] < stage_index_by_name[$stage])) || fail "$stage dependency $dep must appear earlier in FREEWAY_STAGE_ORDER"
  done
done
for stage in "${!FREEWAY_STAGE_INIT[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_INIT has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_COOKER_CALLS[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_COOKER_CALLS has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_REPORT_PAYLOAD[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_REPORT_PAYLOAD has unknown stage: $stage"
done

for name in SLURM_SIM_CONFIG SLURM_RECIPE_CONFIG; do
  mem="$(eval "printf '%s' \"\${${name}[MEM]:-}\"")"
  [[ "$mem" =~ ^[1-9][0-9]*([KMGT])?$ ]] || fail "${name}[MEM] must be a positive integer with optional Slurm memory unit: $mem"

  ntasks="$(eval "printf '%s' \"\${${name}[NTASKS]:-}\"")"
  [[ "$ntasks" =~ ^[1-9][0-9]*$ ]] || fail "${name}[NTASKS] must be a positive integer: $ntasks"

  cpus="$(eval "printf '%s' \"\${${name}[CPUS_PER_TASK]:-}\"")"
  [[ "$cpus" =~ ^[1-9][0-9]*$ ]] || fail "${name}[CPUS_PER_TASK] must be a positive integer: $cpus"
done

store_t0="${PHYSICS_CONFIG[STORE_T0]:-}"
case "$store_t0" in
  ""|0|1|true|TRUE|false|FALSE|yes|YES|no|NO|y|Y|n|N|on|ON|off|OFF)
    ;;
  *)
    fail "PHYSICS_CONFIG[STORE_T0] must be truthy/falsey if set: $store_t0"
    ;;
esac

grep -q 'source_project_lib parallel.sh' src/shell/lib/loader.sh || fail "loader.sh must load parallel.sh"

echo "Config graph OK: ${#FREEWAY_STAGE_ORDER[@]} stages"
