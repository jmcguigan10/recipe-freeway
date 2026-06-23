#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: bash test_run.sh <pipeline-tag>

Runs freeway stages sequentially through packman-muse/scripts/pixi-local.

Environment:
  STACK_DIR    packman-muse checkout, default ./packman-muse
  START_STAGE  first zero-based freeway item to run, default 0
  END_STAGE    last zero-based freeway item to run, default 18

Examples:
  bash test_run.sh mc22308_rad2_e_pos_part0
  START_STAGE=7 END_STAGE=18 bash test_run.sh mc22308_rad2_e_pos_part0
  STACK_DIR=/scratch/me/packman-muse bash test_run.sh mc22308_rad2_e_pos_part0
USAGE
  exit 2
}

[[ $# -eq 1 ]] || usage

tag="$1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$script_dir"
stack_dir="${STACK_DIR:-$repo_root/packman-muse}"
pixi_local="$stack_dir/scripts/pixi-local"
start_stage="${START_STAGE:-0}"
end_stage="${END_STAGE:-18}"

[[ "$tag" != */* ]] || {
  echo "Pipeline tag must be a name, not a path: $tag" >&2
  exit 2
}
[[ "$start_stage" =~ ^[0-9]+$ ]] || {
  echo "START_STAGE must be a non-negative integer: $start_stage" >&2
  exit 2
}
[[ "$end_stage" =~ ^[0-9]+$ ]] || {
  echo "END_STAGE must be a non-negative integer: $end_stage" >&2
  exit 2
}
((start_stage <= end_stage)) || {
  echo "START_STAGE must be <= END_STAGE" >&2
  exit 2
}
[[ -x "$pixi_local" ]] || {
  echo "Missing executable pixi-local wrapper: $pixi_local" >&2
  echo "Set STACK_DIR or install the nested packman-muse checkout." >&2
  exit 2
}

stage_scripts=(
  00_run_g4psi.sh
  01_run_hazard_truth.sh
  02_run_mc2root.sh
  03_run_bh.sh
  04_run_sps.sh
  05_run_bm.sh
  06_run_veto.sh
  07_run_tcpv.sh
  08_run_stt.sh
  09_run_gem_hits.sh
  10_run_gem_tracks.sh
  11_run_tracklets.sh
  12_run_vertex.sh
  13_run_path_length.sh
  14_run_pbglass.sh
  15_run_cs.sh
  16_run_export_cs_events.sh
  17_run_hazard_cutflow.sh
  18_run_export_training_table.sh
)

((end_stage < ${#stage_scripts[@]})) || {
  echo "END_STAGE must be less than ${#stage_scripts[@]}: $end_stage" >&2
  exit 2
}

printf 'Pipeline tag: %s\n' "$tag"
printf 'Repository:   %s\n' "$repo_root"
printf 'Stack:        %s\n' "$stack_dir"
printf 'Stage range:  %02d..%02d\n\n' "$start_stage" "$end_stage"

for ((stage_index = start_stage; stage_index <= end_stage; stage_index++)); do
  stage_script="${stage_scripts[$stage_index]}"
  stage_path="$repo_root/src/shell/freeway/$stage_script"
  [[ -f "$stage_path" ]] || {
    echo "Missing stage script: $stage_path" >&2
    exit 2
  }

  printf '==> %02d %s\n' "$stage_index" "$stage_script"
  (
    cd "$stack_dir"
    G4PSI_PARALLEL_TASKS=1 \
    G4PSI_ENABLE_SRUN=0 \
      ./scripts/pixi-local run -e batch bash "$stage_path" "$tag"
  )
done
