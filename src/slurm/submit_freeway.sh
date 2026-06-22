#!/usr/bin/env bash
#SBATCH --job-name=muse-freeway
# Cluster account/partition/qos are selected in configs/slurm.sh and passed to sbatch at runtime.
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=12:00:00

set -Eeuo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: submit_freeway.sh <freeway-number> <pipeline-tag>

examples:
  bash src/slurm/submit_freeway.sh 1  mc22308_rad2_e_pos_part0
  bash src/slurm/submit_freeway.sh 01 mc22308_rad2_e_pos_part0
  bash src/slurm/submit_freeway.sh 14 mc22308_rad2_e_pos_part0
USAGE
  exit 2
}

[[ $# -eq 2 ]] || usage
[[ "$1" =~ ^[0-9]+$ ]] || usage

idx=$((10#$1))
pipeline_arg="$2"

this_file="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]}")"
script_dir="$(cd -- "$(dirname -- "$this_file")" && pwd -P)"
if [[ -n "${REAL_MUSE_REPO_ROOT:-}" ]]; then
  repo_root="$(cd -- "$REAL_MUSE_REPO_ROOT" && pwd -P)"
else
  repo_root="$(cd -- "$script_dir/../.." && pwd -P)"
fi

source "$repo_root/src/shell/lib/loader.sh"
select_pipeline "$pipeline_arg"

stage="$(freeway_stage_by_index "$idx")" || usage
item="$(printf '%02d' "$idx")"
freeway_script="$repo_root/src/shell/freeway/${FREEWAY_STAGE_SCRIPT[$stage]}"

[[ -f "$freeway_script" ]] || die "missing freeway script: $freeway_script"

log_dir="$data_run_dir/slurm"
mkdir -p "$log_dir"

if [[ "${FREEWAY_SUBMIT_FREEWAY_JOB:-0}" != "1" ]]; then
  if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    echo "Detected existing Slurm job $SLURM_JOB_ID; submitting a separate freeway job instead of running inside that active allocation."
  fi

  if [[ "$stage" == "g4psi" ]]; then
    account="$sim_slurm_account"
    partition="$sim_slurm_partition"
    qos="$sim_slurm_qos"
    nodes="$sim_slurm_nodes"
    ntasks="$sim_slurm_ntasks"
    cpus_per_task="$sim_slurm_cpus_per_task"
    mem="$sim_slurm_mem"
    time_limit="$sim_slurm_time"
  else
    account="$recipe_slurm_account"
    partition="$recipe_slurm_partition"
    qos="$recipe_slurm_qos"
    nodes="$recipe_slurm_nodes"
    ntasks="$recipe_slurm_ntasks"
    cpus_per_task="$recipe_slurm_cpus_per_task"
    mem="$recipe_slurm_mem"
    time_limit="$recipe_slurm_time"
  fi

  sbatch_args=(
    --parsable
    --partition="$partition"
    --nodes="$nodes"
    --ntasks="$ntasks"
    --cpus-per-task="$cpus_per_task"
    --mem="$mem"
    --time="$time_limit"
    --job-name="freeway_${item}_${stage}_${run_tag}"
    --output="$log_dir/%x-%j.out"
    --error="$log_dir/%x-%j.err"
    --export=ALL,PIPELINE_TAG="$pipeline_tag",DATA_RUN_DIR="$data_run_dir",REAL_MUSE_REPO_ROOT="$repo_root",FREEWAY_SUBMIT_FREEWAY_JOB=1
  )
  [[ -z "$account" ]] || sbatch_args+=(--account="$account")
  [[ -z "$qos" ]] || sbatch_args+=(--qos="$qos")

  job_id="$(sbatch "${sbatch_args[@]}" "$this_file" "$item" "$pipeline_tag")"

  submitted_file="$data_run_dir/is_submitted.txt"
  touch "$submitted_file"
  grep -Fxq -- "$item $stage" "$submitted_file" || printf '%s %s\n' "$item" "$stage" >> "$submitted_file"

  printf 'Submitted freeway item %s (%s) as job: %s\n' "$item" "$stage" "$job_id"
  printf 'Data run dir: %s\n' "$data_run_dir"
  printf 'Slurm output: %s\n' "$log_dir"
  exit 0
fi

echo "Running freeway item $item ($stage) for $pipeline_tag"
echo "Runner: $freeway_script"

exec bash "$freeway_script" "$pipeline_tag"
