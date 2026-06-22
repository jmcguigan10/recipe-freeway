[[ -n "${MUSE_PIPELINE_G4PSI_FUNC_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_G4PSI_FUNC_SH_LOADED=1

prepare_g4psi_config() {
  template="$(resolve_path_spec "${G4PSI_CONFIG[template]:-repo:templates/g4psi/muse.mac.erb}")"
  generated_dir="$(resolve_path_spec "${G4PSI_CONFIG[generated_dir]:-repo:macros/generated}")"
  generated_macro="$generated_dir/$run_tag.mac"
  rootfile="$(stage_output_root g4psi)"

  require_file "$template"
}

g4psi_positive_int_value() {
  local name="$1"
  local raw_value="$2"
  local value

  [[ "$raw_value" =~ ^[0-9]+$ ]] || die "$name must be a positive integer: $raw_value"
  value=$((10#$raw_value))
  ((value > 0)) || die "$name must be a positive integer: $raw_value"
  printf '%s\n' "$value"
}

g4psi_integer_value() {
  local name="$1"
  local raw_value="$2"
  local value

  [[ "$raw_value" =~ ^-?[0-9]+$ ]] || die "$name must be an integer: $raw_value"
  if [[ "$raw_value" == -* ]]; then
    value=$((-10#${raw_value#-}))
  else
    value=$((10#$raw_value))
  fi
  printf '%s\n' "$value"
}

g4psi_parallel_tasks() {
  local raw_tasks="${G4PSI_PARALLEL_TASKS:-}"

  if [[ -z "$raw_tasks" ]]; then
    raw_tasks="${SLURM_NTASKS:-}"
  fi
  if [[ -z "$raw_tasks" ]]; then
    raw_tasks="${sim_slurm_ntasks:-1}"
  fi

  g4psi_positive_int_value "g4PSI parallel task count" "$raw_tasks"
}

g4psi_chunk_seed() {
  local base_seed
  local chunk_index="$2"

  base_seed="$(g4psi_integer_value "$1" "$3")"
  printf '%s\n' "$((base_seed + chunk_index * 1009))"
}

render_g4psi_macro() {
  local macro_path="${1:-$generated_macro}"
  local macro_rootfile="${2:-$rootfile}"
  local macro_run_tag="${3:-$run_tag}"
  local macro_n_events="${4:-$n_events}"
  local macro_seed_1="${5:-$seed_1}"
  local macro_seed_2="${6:-$seed_2}"

  with_dir "$stack_dir" \
    "$stack_dir/scripts/pixi-local" run -e batch \
      ruby "$repo_root/src/ruby/render_macro.rb" \
        --template "$template" \
        --output "$macro_path" \
        --output-dir "$data_run_dir" \
        --rootfile "$macro_rootfile" \
        --run-tag "$macro_run_tag" \
        --run-nr "$run_nr" \
        --particle "$particle" \
        --particle-tag "$particle_tag" \
        --part "$part" \
        --beam-momentum "$beam_momentum" \
        --n-events "$macro_n_events" \
        --seed-1 "$macro_seed_1" \
        --seed-2 "$macro_seed_2"
}

run_g4psi_macro() {
  local macro_path="${1:-$generated_macro}"
  local launcher=()
  local launcher_mode="direct"
  local g4psi_args=("$rad_flag")

  if [[ -n "${SLURM_JOB_ID:-}" ]] && is_truthy "${G4PSI_ENABLE_SRUN:-0}" && command -v srun >/dev/null 2>&1; then
    case "${SLURM_STEP_ID:-}" in
      ""|batch|extern)
        launcher=(srun --overlap --exact --nodes=1 --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK:-1}")
        launcher_mode="srun --overlap --exact"
        ;;
      *)
        echo "Detected active Slurm step ${SLURM_STEP_ID}; running g4PSI directly to avoid a nested srun step."
        ;;
    esac
  fi

  echo "g4PSI launcher: $launcher_mode"

  if is_truthy "${STORE_T0:-}"; then
    g4psi_args+=("--T0")
  fi
  g4psi_args+=("$macro_path")

  with_dir "$stack_dir" \
    "${launcher[@]}" \
    "$stack_dir/scripts/pixi-local" run -e batch bash \
      "$stack_dir/scripts/stack-shell.sh" \
      g4PSI "${g4psi_args[@]}"
}

validate_g4psi_root_file() {
  local root_file="$1"

  validate_root_file "$root_file" "${FREEWAY_STAGE_TREE[g4psi]}"
  if is_truthy "${STORE_T0:-}"; then
    validate_root_file "$root_file" T0
  fi
}

run_g4psi_single_task_stage() {
  local rendered_rootfile

  rendered_rootfile="$(render_g4psi_macro)"

  echo "Generated macro: $generated_macro"
  echo "Data run dir:    $data_run_dir"
  echo "Run tag:         $run_tag"
  echo "ROOT output:     $rendered_rootfile"

  run_g4psi_macro
  validate_g4psi_root_file "$rendered_rootfile"
}

run_g4psi_parallel_task_stage() {
  local worker_count="$1"
  local total_events="$2"
  local g4psi_stage="g4psi"
  local chunk_dir="$data_run_dir/g4psi_chunks"
  local base_events=$((total_events / worker_count))
  local extra_events=$((total_events % worker_count))
  local chunk_index
  local chunk_events
  local chunk_label
  local chunk_run_tag
  local chunk_macro
  local chunk_root
  local chunk_log
  local chunk_seed_1
  local chunk_seed_2
  local rendered_rootfile
  local failed=0
  local status_interval

  mkdir -p "$chunk_dir"
  parallel_reset_workers
  status_interval="$(g4psi_positive_int_value "G4PSI_STATUS_INTERVAL" "${G4PSI_STATUS_INTERVAL:-5}")"

  echo "g4PSI parallel tasks: $worker_count"
  echo "Total events:         $total_events"
  echo "Merged ROOT output:   $rootfile"
  echo "Chunk work dir:       $chunk_dir"

  for ((chunk_index = 0; chunk_index < worker_count; chunk_index++)); do
    chunk_events="$base_events"
    if ((chunk_index < extra_events)); then
      chunk_events=$((chunk_events + 1))
    fi

    chunk_label="$(printf 'chunk%02d' "$chunk_index")"
    chunk_run_tag="${run_tag}_${chunk_label}"
    chunk_macro="$generated_dir/$chunk_run_tag.mac"
    chunk_root="$chunk_dir/${chunk_run_tag}_g4psi.root"
    chunk_log="$chunk_dir/${chunk_run_tag}.log"
    chunk_seed_1="$(g4psi_chunk_seed "SEED_1" "$chunk_index" "$seed_1")"
    chunk_seed_2="$(g4psi_chunk_seed "SEED_2" "$chunk_index" "$seed_2")"

    rm -f "$chunk_root"
    rendered_rootfile="$(render_g4psi_macro \
      "$chunk_macro" \
      "$chunk_root" \
      "$chunk_run_tag" \
      "$chunk_events" \
      "$chunk_seed_1" \
      "$chunk_seed_2")"

    echo "Starting $chunk_label: events=$chunk_events seed_1=$chunk_seed_1 seed_2=$chunk_seed_2 root=$rendered_rootfile"

    run_g4psi_macro "$chunk_macro" >"$chunk_log" 2>&1 &
    parallel_add_worker "$chunk_label" "$chunk_root" "$chunk_log" "$!"
  done

  parallel_monitor_workers "g4PSI chunk status" "$status_interval" G4PSI_STATUS_PLAIN || failed=1
  parallel_report_worker_results "Finished" "g4PSI" 80

  ((failed == 0)) || return 1

  for chunk_root in "${parallel_worker_roots[@]}"; do
    validate_g4psi_root_file "$chunk_root"
  done

  merge_root_files "$rootfile" "${FREEWAY_STAGE_TREE[$g4psi_stage]}" "${parallel_worker_roots[@]}"
  validate_g4psi_root_file "$rootfile"

  for chunk_root in "${parallel_worker_roots[@]}"; do
    rm -f "$chunk_root"
  done

  echo "Merged g4PSI ROOT output: $rootfile"
}

run_g4psi_stage() {
  local requested_tasks
  local total_events
  local worker_count

  prepare_g4psi_config

  mkdir -p "$(dirname -- "$generated_macro")"
  mkdir -p "$data_run_dir"

  requested_tasks="$(g4psi_parallel_tasks)"
  total_events="$(g4psi_positive_int_value "N_EVENTS" "$n_events")"
  worker_count="$requested_tasks"
  if ((worker_count > total_events)); then
    worker_count="$total_events"
  fi

  if ((worker_count != requested_tasks)); then
    echo "Requested $requested_tasks g4PSI tasks, but only $total_events events are configured; using $worker_count task(s)."
  fi

  if ((worker_count == 1)); then
    run_g4psi_single_task_stage
  else
    run_g4psi_parallel_task_stage "$worker_count" "$total_events"
  fi
}
