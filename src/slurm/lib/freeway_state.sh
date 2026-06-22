#!/usr/bin/env bash

if [[ -n "${MUSE_PIPELINE_SLURM_FREEWAY_STATE_SH_LOADED:-}" ]]; then
  return 0
fi
MUSE_PIPELINE_SLURM_FREEWAY_STATE_SH_LOADED=1

freeway_submitted_file() {
  printf '%s/is_submitted.txt\n' "$data_run_dir"
}

freeway_lock_dir() {
  printf '%s/.run_freeway.lock\n' "$data_run_dir"
}

freeway_acquire_lock() {
  local lock_dir
  lock_dir="$(freeway_lock_dir)"

  if mkdir "$lock_dir" 2>/dev/null; then
    {
      printf 'pid=%s\n' "$$"
      printf 'host=%s\n' "${HOSTNAME:-unknown}"
      printf 'started_at=%s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    } > "$lock_dir/owner"
    trap 'freeway_release_lock' EXIT
    return 0
  fi

  echo "Another freeway orchestrator is already running for $pipeline_tag."
  if [[ -f "$lock_dir/owner" ]]; then
    sed 's/^/  /' "$lock_dir/owner" || true
  fi
  return 1
}

freeway_release_lock() {
  local lock_dir
  lock_dir="$(freeway_lock_dir)"

  if [[ -d "$lock_dir" ]]; then
    rm -f "$lock_dir/owner"
    rmdir "$lock_dir" 2>/dev/null || true
  fi
}

freeway_stage_is_submitted() {
  local item="$1"
  local stage="$2"
  local file

  file="$(freeway_submitted_file)"
  [[ -f "$file" ]] || return 1

  awk -v item="$item" -v stage="$stage" '
    NF == 0 || $1 ~ /^#/ { next }
    (NF == 1 && $1 == stage) || ($1 == item && $2 == stage) { found = 1 }
    END { exit(found ? 0 : 1) }
  ' "$file"
}

freeway_mark_submitted() {
  local item="$1"
  local stage="$2"
  local job_id="$3"
  local file

  file="$(freeway_submitted_file)"
  if [[ ! -f "$file" ]]; then
    printf '# item stage job_id submitted_at\n' > "$file"
  fi

  if freeway_stage_is_submitted "$item" "$stage"; then
    return 0
  fi

  printf '%s %s %s %s\n' \
    "$item" \
    "$stage" \
    "$job_id" \
    "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$file"
}

freeway_stage_output_exists() {
  local stage="$1"
  [[ -s "$(stage_output_root "$stage")" ]]
}

freeway_stage_missing_dependencies() {
  local stage="$1"
  local dep
  local missing=()

  for dep in ${FREEWAY_STAGE_INPUTS[$stage]:-}; do
    if ! freeway_stage_output_exists "$dep"; then
      missing+=("$dep")
    fi
  done

  if ((${#missing[@]})); then
    join_by ', ' "${missing[@]}"
  fi
}

freeway_stage_dependencies_ready() {
  [[ -z "$(freeway_stage_missing_dependencies "$1")" ]]
}

freeway_slurm_resources_for_stage() {
  local stage="$1"

  if [[ "$stage" == "g4psi" ]]; then
    freeway_slurm_account="$sim_slurm_account"
    freeway_slurm_partition="$sim_slurm_partition"
    freeway_slurm_qos="$sim_slurm_qos"
    freeway_slurm_nodes="$sim_slurm_nodes"
    freeway_slurm_ntasks="$sim_slurm_ntasks"
    freeway_slurm_cpus_per_task="$sim_slurm_cpus_per_task"
    freeway_slurm_mem="$sim_slurm_mem"
    freeway_slurm_time="$sim_slurm_time"
  else
    freeway_slurm_account="$recipe_slurm_account"
    freeway_slurm_partition="$recipe_slurm_partition"
    freeway_slurm_qos="$recipe_slurm_qos"
    freeway_slurm_nodes="$recipe_slurm_nodes"
    freeway_slurm_ntasks="$recipe_slurm_ntasks"
    freeway_slurm_cpus_per_task="$recipe_slurm_cpus_per_task"
    freeway_slurm_mem="$recipe_slurm_mem"
    freeway_slurm_time="$recipe_slurm_time"
  fi
}

freeway_submit_stage() {
  local index="$1"
  local stage="$2"
  local item
  local log_dir
  local job_name
  local job_id
  local sbatch_bin
  local -a sbatch_args

  item="$(printf '%02d' "$index")"
  log_dir="$data_run_dir/slurm"
  job_name="freeway_${item}_${stage}_${run_tag}"
  sbatch_bin="${FREEWAY_SBATCH_BIN:-sbatch}"

  mkdir -p "$log_dir"
  freeway_slurm_resources_for_stage "$stage"

  sbatch_args=(
    --parsable
    --job-name="$job_name"
    --partition="$freeway_slurm_partition"
    --nodes="$freeway_slurm_nodes"
    --ntasks="$freeway_slurm_ntasks"
    --cpus-per-task="$freeway_slurm_cpus_per_task"
    --mem="$freeway_slurm_mem"
    --time="$freeway_slurm_time"
    --output="$log_dir/%x-%j.out"
    --error="$log_dir/%x-%j.err"
    --export=ALL,PIPELINE_TAG="$pipeline_tag",DATA_RUN_DIR="$data_run_dir",REAL_MUSE_REPO_ROOT="$repo_root"
  )
  [[ -z "$freeway_slurm_account" ]] || sbatch_args+=(--account="$freeway_slurm_account")
  [[ -z "$freeway_slurm_qos" ]] || sbatch_args+=(--qos="$freeway_slurm_qos")

  job_id="$("$sbatch_bin" "${sbatch_args[@]}" "$repo_root/src/slurm/freeway_stage_job.sh" "$item" "$pipeline_tag")"

  freeway_mark_submitted "$item" "$stage" "$job_id"
  printf 'submitted %-2s %-14s job %s\n' "$item" "$stage" "$job_id"
}
