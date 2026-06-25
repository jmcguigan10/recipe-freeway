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
source src/freeway/shell/lib/errors.sh
source src/freeway/shell/lib/orchs/g4psi.func.sh

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

check_no_cooker_parallel_knob() {
  local matches

  matches="$(grep -R -n 'COOKER_PARALLEL' README.md test_run.sh src configs 2>/dev/null || true)"
  [[ -z "$matches" ]] || fail "COOKER_PARALLEL references should not exist: $matches"
}

slurm_cluster_values() {
  local cluster="$1"

  SLURM_CLUSTER="$cluster" "$BASH" -c '
    set -Eeuo pipefail
    cd "$1"
    source configs/slurm.sh
    printf "%s|%s|%s|%s|%s|%s|%s|%s\n" \
      "${SLURM_SIM_CONFIG[ACCOUNT]:-}" \
      "${SLURM_SIM_CONFIG[PARTITION]:-}" \
      "${SLURM_SIM_CONFIG[QOS]:-}" \
      "${SLURM_SIM_CONFIG[NTASKS]:-}" \
      "${SLURM_RECIPE_CONFIG[ACCOUNT]:-}" \
      "${SLURM_RECIPE_CONFIG[PARTITION]:-}" \
      "${SLURM_RECIPE_CONFIG[QOS]:-}" \
      "${SLURM_RECIPE_CONFIG[NTASKS]:-}"
  ' -- "$repo_root"
}

check_slurm_cluster_config() {
  local actual
  local invalid_output

  actual="$(slurm_cluster_values isaac)" || fail "SLURM_CLUSTER=isaac should load"
  [[ "$actual" == "isaac-utk0307|condo-slagergr|condo|48|isaac-utk0307|condo-slagergr|condo|1" ]] || \
    fail "unexpected ISAAC Slurm config: $actual"

  actual="$(slurm_cluster_values theia)" || fail "SLURM_CLUSTER=theia should load"
  [[ "$actual" == "|defq||48||defq||1" ]] || \
    fail "unexpected Theia Slurm config: $actual"

  if invalid_output="$(slurm_cluster_values invalid 2>&1)"; then
    fail "invalid Slurm cluster should fail"
  fi
  [[ "$invalid_output" == *"unknown SLURM_CLUSTER: invalid"* ]] || \
    fail "invalid Slurm cluster error was unclear: $invalid_output"
}

[[ ${#FREEWAY_STAGE_ORDER[@]} -gt 0 ]] || fail "FREEWAY_STAGE_ORDER is empty"

expected_stage_order=(
  g4psi
  hazard_truth
  mc2root
  bh
  sps
  bm
  veto
  tcpv
  stt
  gem_hits
  gem_tracks
  tracklets
  vertex
  pathlength
  pbglass
  cross_section
  export_cs_events
  hazard_cutflow
  export_training_table
)

[[ ${#FREEWAY_STAGE_ORDER[@]} -eq ${#expected_stage_order[@]} ]] || \
  fail "FREEWAY_STAGE_ORDER must have ${#expected_stage_order[@]} stages"
for index in "${!expected_stage_order[@]}"; do
  [[ "${FREEWAY_STAGE_ORDER[$index]}" == "${expected_stage_order[$index]}" ]] || \
    fail "stage $index should be ${expected_stage_order[$index]}, got ${FREEWAY_STAGE_ORDER[$index]}"
done

declare -A stage_seen=()
declare -A stage_index_by_name=()

for index in "${!FREEWAY_STAGE_ORDER[@]}"; do
  stage="${FREEWAY_STAGE_ORDER[$index]}"
  item="$(printf '%02d' "$index")"
  kind="${FREEWAY_STAGE_KIND[$stage]:-cooker}"
  ext="${FREEWAY_STAGE_OUTPUT_EXT[$stage]:-root}"

  [[ -n "$stage" ]] || fail "empty stage name at index $index"
  [[ -z "${stage_seen[$stage]:-}" ]] || fail "duplicate stage in FREEWAY_STAGE_ORDER: $stage"
  stage_seen[$stage]=1
  stage_index_by_name[$stage]="$index"

  case "$kind" in
    g4psi|cooker|helper) ;;
    *) fail "$stage has invalid FREEWAY_STAGE_KIND: $kind" ;;
  esac
  case "$ext" in
    root|csv|parquet) ;;
    *) fail "$stage has invalid FREEWAY_STAGE_OUTPUT_EXT: $ext" ;;
  esac

  [[ -n "${FREEWAY_STAGE_KIND[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_KIND"
  [[ -n "${FREEWAY_STAGE_SCRIPT[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_SCRIPT"
  [[ -f "src/freeway/shell/freeway/${FREEWAY_STAGE_SCRIPT[$stage]}" ]] || fail "$stage script not found: ${FREEWAY_STAGE_SCRIPT[$stage]}"
  [[ "${FREEWAY_STAGE_SCRIPT[$stage]}" == "${item}_"* ]] || fail "$stage script must start with $item: ${FREEWAY_STAGE_SCRIPT[$stage]}"
  [[ -n "${FREEWAY_STAGE_OUTPUT[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_OUTPUT"

  if [[ "$ext" == "root" ]]; then
    [[ -n "${FREEWAY_STAGE_TREE[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_TREE"
  fi

  if [[ "$kind" == "cooker" ]]; then
    [[ -n "${FREEWAY_STAGE_RECIPE[$stage]:-}" ]] || fail "$stage missing FREEWAY_STAGE_RECIPE"
    [[ "${FREEWAY_STAGE_RECIPE[$stage]}" == muse:* ]] || fail "$stage recipe must use muse: prefix"
  else
    [[ -z "${FREEWAY_STAGE_RECIPE[$stage]:-}" ]] || fail "$stage must not have FREEWAY_STAGE_RECIPE"
  fi
done

for stage in "${!FREEWAY_STAGE_KIND[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_KIND has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_SCRIPT[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_SCRIPT has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_OUTPUT[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_OUTPUT has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_OUTPUT_EXT[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_OUTPUT_EXT has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_TREE[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_TREE has unknown stage: $stage"
done
for stage in "${!FREEWAY_STAGE_RECIPE[@]}"; do
  [[ -n "${stage_seen[$stage]:-}" ]] || fail "FREEWAY_STAGE_RECIPE has unknown stage: $stage"
  [[ "${FREEWAY_STAGE_KIND[$stage]:-}" == "cooker" ]] || fail "$stage recipe belongs to non-cooker stage"
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

recipe_ntasks="${SLURM_RECIPE_CONFIG[NTASKS]:-}"
recipe_cpus="${SLURM_RECIPE_CONFIG[CPUS_PER_TASK]:-}"
[[ "$recipe_ntasks" == "1" ]] || fail "SLURM_RECIPE_CONFIG[NTASKS] must stay 1 for serial cooker stages"
[[ "$recipe_cpus" == "1" ]] || fail "SLURM_RECIPE_CONFIG[CPUS_PER_TASK] must stay 1 for serial cooker stages"

store_t0="${PHYSICS_CONFIG[STORE_T0]:-}"
case "$store_t0" in
  ""|0|1|true|TRUE|false|FALSE|yes|YES|no|NO|y|Y|n|N|on|ON|off|OFF)
    ;;
  *)
    fail "PHYSICS_CONFIG[STORE_T0] must be truthy/falsey if set: $store_t0"
    ;;
esac

grep -q 'source_project_lib parallel.sh' src/freeway/shell/lib/loader.sh || fail "loader.sh must load parallel.sh"
check_g4psi_parallel_task_selection
check_no_cooker_parallel_knob
check_slurm_cluster_config

echo "Config graph OK: ${#FREEWAY_STAGE_ORDER[@]} stages"
