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
source src/shell/lib/errors.sh
source src/shell/lib/orchs/g4psi.func.sh
source src/shell/lib/orchs/cooker.func.sh

check_g4psi_parallel_task_selection() {
  local actual

  grep -q 'G4PSI_PARALLEL_TASKS=1' test_run.sh || fail "test_run.sh must force serial g4PSI"
  if grep -q 'G4PSI_PARALLEL_TASKS=.*G4PSI_PARALLEL_TASKS' test_run.sh; then
    fail "test_run.sh must not pass through caller-provided G4PSI_PARALLEL_TASKS"
  fi

  unset G4PSI_PARALLEL_TASKS
  unset SLURM_JOB_ID
  unset SLURM_NTASKS
  sim_slurm_ntasks=100
  actual="$(g4psi_parallel_tasks)"
  [[ "$actual" == "1" ]] || fail "direct g4PSI runs must default to 1 task, got $actual"

  G4PSI_PARALLEL_TASKS=3
  actual="$(g4psi_parallel_tasks)"
  [[ "$actual" == "3" ]] || fail "G4PSI_PARALLEL_TASKS override should win, got $actual"
  unset G4PSI_PARALLEL_TASKS

  SLURM_JOB_ID=123
  SLURM_NTASKS=4
  actual="$(g4psi_parallel_tasks)"
  [[ "$actual" == "4" ]] || fail "Slurm g4PSI runs should use SLURM_NTASKS, got $actual"
  unset SLURM_NTASKS

  sim_slurm_ntasks=5
  actual="$(g4psi_parallel_tasks)"
  [[ "$actual" == "5" ]] || fail "Slurm g4PSI runs should fall back to sim_slurm_ntasks, got $actual"

  unset SLURM_JOB_ID
}

check_cooker_parallel_task_selection() {
  local actual

  grep -q 'COOKER_PARALLEL_TASKS=1' test_run.sh || fail "test_run.sh must force serial cooker stages"
  if grep -q 'COOKER_PARALLEL_TASKS=.*COOKER_PARALLEL_TASKS' test_run.sh; then
    fail "test_run.sh must not pass through caller-provided COOKER_PARALLEL_TASKS"
  fi

  unset COOKER_PARALLEL_TASKS
  unset SLURM_JOB_ID
  unset SLURM_NTASKS
  recipe_slurm_ntasks=100
  actual="$(cooker_parallel_tasks mc2root)"
  [[ "$actual" == "1" ]] || fail "direct cooker runs must default to 1 task, got $actual"

  FREEWAY_STAGE_PARALLEL_TASKS[bh]=2
  actual="$(cooker_parallel_tasks bh)"
  [[ "$actual" == "2" ]] || fail "per-stage cooker parallel override should win, got $actual"
  unset 'FREEWAY_STAGE_PARALLEL_TASKS[bh]'

  COOKER_PARALLEL_TASKS=3
  actual="$(cooker_parallel_tasks mc2root)"
  [[ "$actual" == "3" ]] || fail "COOKER_PARALLEL_TASKS override should win, got $actual"
  unset COOKER_PARALLEL_TASKS

  SLURM_JOB_ID=123
  SLURM_NTASKS=4
  actual="$(cooker_parallel_tasks mc2root)"
  [[ "$actual" == "4" ]] || fail "Slurm cooker runs should use SLURM_NTASKS, got $actual"
  unset SLURM_NTASKS

  recipe_slurm_ntasks=5
  actual="$(cooker_parallel_tasks mc2root)"
  [[ "$actual" == "5" ]] || fail "Slurm cooker runs should fall back to recipe_slurm_ntasks, got $actual"

  unset SLURM_JOB_ID
}

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
for stage in "${!FREEWAY_STAGE_PARALLEL_TASKS[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_PARALLEL_TASKS has unknown stage: $stage"
  [[ "${FREEWAY_STAGE_PARALLEL_TASKS[$stage]}" =~ ^[1-9][0-9]*$ ]] || fail "FREEWAY_STAGE_PARALLEL_TASKS[$stage] must be a positive integer: ${FREEWAY_STAGE_PARALLEL_TASKS[$stage]}"
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
[[ -f src/python/root_tree_entries.py ]] || fail "missing root_tree_entries.py helper"
check_g4psi_parallel_task_selection
check_cooker_parallel_task_selection

echo "Config graph OK: ${#FREEWAY_STAGE_ORDER[@]} stages"
