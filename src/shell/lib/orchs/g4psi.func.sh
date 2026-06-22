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

  with_dir "$stack_dir" \
    "${launcher[@]}" \
    "$stack_dir/scripts/pixi-local" run -e batch bash \
      "$stack_dir/scripts/stack-shell.sh" \
      g4PSI "$rad_flag" "$macro_path"
}

run_g4psi_single_task_stage() {
  local rendered_rootfile
  local g4psi_stage="g4psi"

  rendered_rootfile="$(render_g4psi_macro)"

  echo "Generated macro: $generated_macro"
  echo "Data run dir:    $data_run_dir"
  echo "Run tag:         $run_tag"
  echo "ROOT output:     $rendered_rootfile"

  run_g4psi_macro
  validate_root_file "$rendered_rootfile" "${FREEWAY_STAGE_TREE[$g4psi_stage]}"
}

g4psi_status_elapsed() {
  local started_at="$1"
  local now
  local elapsed

  now="$(date +%s)"
  elapsed=$((now - started_at))
  printf '%02d:%02d:%02d\n' \
    "$((elapsed / 3600))" \
    "$(((elapsed % 3600) / 60))" \
    "$((elapsed % 60))"
}

g4psi_status_root_size() {
  local root_path="$1"

  if [[ -s "$root_path" ]]; then
    du -h "$root_path" 2>/dev/null | awk '{print $1}'
  else
    printf '0\n'
  fi
}

g4psi_status_bar() {
  local status="$1"
  local chunk_index="$2"
  local tick="$3"
  local width=24
  local position=$(((tick + chunk_index) % width))
  local bar=""
  local i

  for ((i = 0; i < width; i++)); do
    case "$status" in
      done)
        bar+="="
        ;;
      failed)
        bar+="!"
        ;;
      *)
        if ((i == position)); then
          bar+=">"
        else
          bar+="."
        fi
        ;;
    esac
  done

  printf '[%s]\n' "$bar"
}

g4psi_render_chunk_statuses() {
  local worker_count="$1"
  local tick="$2"
  local use_tty="$3"
  local printed_lines="$4"
  local chunk_index
  local chunk_label
  local status
  local elapsed
  local root_size
  local bar

  if [[ "$use_tty" == "1" && "$printed_lines" -gt 0 ]]; then
    printf '\033[%sA' "$printed_lines"
  fi

  for ((chunk_index = 0; chunk_index < worker_count; chunk_index++)); do
    chunk_label="$(printf 'chunk%02d' "$chunk_index")"
    status="${chunk_statuses[$chunk_index]}"
    elapsed="$(g4psi_status_elapsed "${chunk_started_at[$chunk_index]}")"
    root_size="$(g4psi_status_root_size "${chunk_roots[$chunk_index]}")"
    bar="$(g4psi_status_bar "$status" "$chunk_index" "$tick")"

    if [[ "$use_tty" == "1" ]]; then
      printf '\r\033[K'
    fi
    printf '%s %s %-7s elapsed=%s root=%6s log=%s\n' \
      "$chunk_label" \
      "$bar" \
      "$status" \
      "$elapsed" \
      "$root_size" \
      "$(basename -- "${chunk_logs[$chunk_index]}")"
  done
}

g4psi_monitor_chunks() {
  local worker_count="$1"
  local status_interval="$2"
  local use_tty=0
  local printed_lines=0
  local tick=0
  local last_render=0
  local now
  local active
  local chunk_index
  local rc
  local failed=0

  if [[ -t 1 && "${TERM:-}" != "dumb" ]] && ! is_truthy "${G4PSI_STATUS_PLAIN:-0}"; then
    use_tty=1
  fi

  while :; do
    active=0
    for ((chunk_index = 0; chunk_index < worker_count; chunk_index++)); do
      if [[ "${chunk_statuses[$chunk_index]}" != "running" ]]; then
        continue
      fi

      if kill -0 "${pids[$chunk_index]}" 2>/dev/null; then
        active=$((active + 1))
      elif wait "${pids[$chunk_index]}"; then
        chunk_statuses[$chunk_index]="done"
      else
        rc=$?
        chunk_statuses[$chunk_index]="failed"
        chunk_exit_codes[$chunk_index]="$rc"
        failed=1
      fi
    done

    now="$(date +%s)"
    if ((tick == 0 || active == 0 || now - last_render >= status_interval)); then
      if [[ "$use_tty" != "1" ]]; then
        printf 'g4PSI chunk status at %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
      fi
      g4psi_render_chunk_statuses "$worker_count" "$tick" "$use_tty" "$printed_lines"
      printed_lines="$worker_count"
      last_render="$now"
      tick=$((tick + 1))
    fi

    ((active > 0)) || break
    sleep 1
  done

  return "$failed"
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
  local rc
  local pids=()
  local chunk_roots=()
  local chunk_logs=()
  local chunk_statuses=()
  local chunk_started_at=()
  local chunk_exit_codes=()
  local status_interval

  mkdir -p "$chunk_dir"
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
    pids+=("$!")
    chunk_roots+=("$chunk_root")
    chunk_logs+=("$chunk_log")
    chunk_statuses+=("running")
    chunk_started_at+=("$(date +%s)")
    chunk_exit_codes+=("0")
  done

  g4psi_monitor_chunks "$worker_count" "$status_interval" || failed=1

  for chunk_index in "${!pids[@]}"; do
    if [[ "${chunk_statuses[$chunk_index]}" == "done" ]]; then
      echo "Finished chunk$(printf '%02d' "$chunk_index"): ${chunk_logs[$chunk_index]}"
    elif [[ "${chunk_statuses[$chunk_index]}" == "failed" ]]; then
      rc="${chunk_exit_codes[$chunk_index]}"
      echo "g4PSI chunk$(printf '%02d' "$chunk_index") failed with exit code $rc: ${chunk_logs[$chunk_index]}" >&2
      tail -n 80 "${chunk_logs[$chunk_index]}" >&2 || true
    fi
  done

  ((failed == 0)) || return 1

  for chunk_root in "${chunk_roots[@]}"; do
    validate_root_file "$chunk_root" "${FREEWAY_STAGE_TREE[$g4psi_stage]}"
  done

  merge_root_files "$rootfile" "${FREEWAY_STAGE_TREE[$g4psi_stage]}" "${chunk_roots[@]}"

  for chunk_root in "${chunk_roots[@]}"; do
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
