[[ -n "${MUSE_PIPELINE_COOKER_FUNC_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_COOKER_FUNC_SH_LOADED=1

run_cooker() {
  export TMPDIR="${MUSE_PIPELINE_TMPDIR:-$repo_root/.tmp}"
  mkdir -p "$TMPDIR"

  with_dir "$stack_dir" \
    "$stack_dir/scripts/pixi-local" run -e batch bash \
      "$stack_dir/scripts/stack-shell.sh" \
      bash "$project_helper_dir/run-with-g4-preload.sh" \
        "$muse_src_dir" \
        cooker \
        "$@"
}

run_cooker_root() {
  local output_root=$1
  local expected_tree=$2
  shift 2

  local output_dir
  local output_base
  local tmp_root
  local rc

  output_dir="$(dirname -- "$output_root")"
  output_base="$(basename -- "$output_root")"

  mkdir -p "$output_dir"
  tmp_root="$(mktemp "$output_dir/.${output_base}.XXXXXX.tmp")"

  if run_cooker "$@" "$tmp_root"; then
    :
  else
    rc=$?
    rm -f "$tmp_root"
    return "$rc"
  fi

  if validate_root_file "$tmp_root" "$expected_tree"; then
    :
  else
    rc=$?
    rm -f "$tmp_root"
    return "$rc"
  fi

  if mv -f "$tmp_root" "$output_root"; then
    :
  else
    rc=$?
    rm -f "$tmp_root"
    return "$rc"
  fi
}
<<<<<<< Updated upstream
=======

run_cooker_root_range() {
  local output_root=$1
  local expected_tree=$2
  local start_entry=$3
  local entry_count=$4
  local recipe=$5
  shift 5

  local output_dir
  local output_base
  local tmp_root
  local rc

  output_dir="$(dirname -- "$output_root")"
  output_base="$(basename -- "$output_root")"

  mkdir -p "$output_dir"
  tmp_root="$(mktemp "$output_dir/.${output_base}.XXXXXX.tmp")"

  if run_cooker "$recipe" --start "$start_entry" --num "$entry_count" "$@" "$tmp_root"; then
    :
  else
    rc=$?
    rm -f "$tmp_root"
    return "$rc"
  fi

  if validate_root_file "$tmp_root" "$expected_tree"; then
    :
  else
    rc=$?
    rm -f "$tmp_root"
    return "$rc"
  fi

  if mv -f "$tmp_root" "$output_root"; then
    :
  else
    rc=$?
    rm -f "$tmp_root"
    return "$rc"
  fi
}

run_cooker_parallel_root() {
  local stage="$1"
  local output_root="$2"
  local expected_tree="$3"
  local recipe="$4"
  local worker_count="$5"
  local total_entries="$6"
  shift 6

  local chunk_dir="$data_run_dir/cooker_chunks/$stage"
  local base_entries=$((total_entries / worker_count))
  local extra_entries=$((total_entries % worker_count))
  local chunk_index
  local chunk_entries
  local start_entry=0
  local chunk_label
  local chunk_root
  local chunk_log
  local chunk_tmp_dir
  local failed=0
  local status_interval
  local merge_mode

  mkdir -p "$chunk_dir"
  parallel_reset_workers
  status_interval="$(cooker_positive_int_value "COOKER_STATUS_INTERVAL" "${COOKER_STATUS_INTERVAL:-5}")"

  echo "Cooker parallel tasks: $worker_count"
  echo "Total input entries:   $total_entries"
  echo "Merged ROOT output:    $output_root"
  echo "Chunk work dir:        $chunk_dir"

  for ((chunk_index = 0; chunk_index < worker_count; chunk_index++)); do
    chunk_entries="$base_entries"
    if ((chunk_index < extra_entries)); then
      chunk_entries=$((chunk_entries + 1))
    fi

    chunk_label="$(printf 'chunk%02d' "$chunk_index")"
    chunk_root="$chunk_dir/${run_tag}_${stage}_${chunk_label}.root"
    chunk_log="$chunk_dir/${run_tag}_${stage}_${chunk_label}.log"
    chunk_tmp_dir="$chunk_dir/tmp_$chunk_label"

    rm -f "$chunk_root"
    mkdir -p "$chunk_tmp_dir"
    echo "Starting $chunk_label: start=$start_entry entries=$chunk_entries root=$chunk_root"

    MUSE_PIPELINE_TMPDIR="$chunk_tmp_dir" \
      run_cooker_root_range "$chunk_root" "$expected_tree" "$start_entry" "$chunk_entries" "$recipe" "$@" >"$chunk_log" 2>&1 &
    parallel_add_worker "$chunk_label" "$chunk_root" "$chunk_log" "$!"

    start_entry=$((start_entry + chunk_entries))
  done

  parallel_monitor_workers "$stage cooker chunk status" "$status_interval" COOKER_STATUS_PLAIN || failed=1
  parallel_report_worker_results "Finished" "Cooker" 80

  ((failed == 0)) || return 1

  for chunk_root in "${parallel_worker_roots[@]}"; do
    validate_root_file "$chunk_root" "$expected_tree"
  done

  merge_mode="${FREEWAY_STAGE_MERGE_MODE[$stage]:-full}"
  case "$merge_mode" in
    full)
      merge_root_files "$output_root" "$expected_tree" "${parallel_worker_roots[@]}"
      ;;
    tree)
      merge_root_tree_files "$output_root" "$expected_tree" "${parallel_worker_roots[@]}"
      ;;
    *)
      die "unknown ROOT merge mode for $stage: $merge_mode"
      ;;
  esac
  validate_root_file "$output_root" "$expected_tree"

  for chunk_root in "${parallel_worker_roots[@]}"; do
    rm -f "$chunk_root"
  done

  echo "Merged cooker ROOT output: $output_root"
}

run_cooker_stage_root() {
  local stage="$1"
  local output_root="$2"
  local expected_tree="$3"
  local recipe="$4"
  shift 4

  local requested_tasks
  local worker_count
  local primary_root
  local primary_tree
  local total_entries

  requested_tasks="$(cooker_parallel_tasks "$stage")"

  if ((requested_tasks == 1)); then
    run_cooker_root "$output_root" "$expected_tree" "$recipe" "$@"
    return $?
  fi

  primary_root="$(stage_primary_input_root "$stage")"
  primary_tree="$(stage_primary_input_tree "$stage")"
  total_entries="$(root_tree_entries "$primary_root" "$primary_tree")"
  [[ "$total_entries" =~ ^[0-9]+$ ]] || die "could not determine input entry count for $stage: $total_entries"

  if ((total_entries == 0)); then
    echo "Primary input $primary_root:$primary_tree has zero entries; running $stage serially."
    run_cooker_root "$output_root" "$expected_tree" "$recipe" "$@"
    return $?
  fi

  worker_count="$requested_tasks"
  if ((worker_count > total_entries)); then
    worker_count="$total_entries"
  fi

  if ((worker_count != requested_tasks)); then
    echo "Requested $requested_tasks cooker tasks for $stage, but only $total_entries input entries are available; using $worker_count task(s)."
  fi

  if ((worker_count == 1)); then
    run_cooker_root "$output_root" "$expected_tree" "$recipe" "$@"
  else
    run_cooker_parallel_root "$stage" "$output_root" "$expected_tree" "$recipe" "$worker_count" "$total_entries" "$@"
  fi
}
>>>>>>> Stashed changes
