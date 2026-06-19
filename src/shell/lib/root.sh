[[ -n "${MUSE_PIPELINE_ROOT_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_ROOT_SH_LOADED=1

stage_root() {
  local suffix="$1"
  printf '%s/%s_%s.root\n' "$data_run_dir" "$run_tag" "$suffix"
}

stage_output_root() {
  local stage="$1"
  stage_root "${FREEWAY_STAGE_OUTPUT[$stage]:-$stage}"
}

stage_input_roots() {
  local stage="$1"
  local input_stage
  local roots=()

  for input_stage in ${FREEWAY_STAGE_INPUTS[$stage]:-}; do
    roots+=("$(stage_output_root "$input_stage")")
  done

  join_by ":" "${roots[@]}"
}

particle_pid_for() {
  local particle_name="$1"

  case "$particle_name" in
    e+|positron) printf '%s\n' "-11" ;;
    e-|electron) printf '%s\n' "11" ;;
    mu+|mu_pos|muon+) printf '%s\n' "-13" ;;
    mu-|mu_neg|muon-) printf '%s\n' "13" ;;
    pi+|pion+) printf '%s\n' "211" ;;
    pi-|pion-) printf '%s\n' "-211" ;;
    *)
      echo "Unknown particle species: $particle_name" >&2
      return 2
      ;;
  esac
}

run_stack_python() {
  local script="$1"
  local timeout_seconds="${STACK_PYTHON_TIMEOUT:-${ROOT_VALIDATE_TIMEOUT:-120}}"
  local python_cmd
  shift

  python_cmd=(
    "$stack_dir/scripts/pixi-local" run -e batch bash
    "$stack_dir/scripts/stack-shell.sh"
    python "$script" "$@"
  )

  (
    cd "$stack_dir"
    if command -v timeout >/dev/null 2>&1 && [[ "$timeout_seconds" != "0" ]]; then
      timeout "$timeout_seconds" "${python_cmd[@]}"
    else
      "${python_cmd[@]}"
    fi
  )
}

validate_root_file() {
  local root_file="$1"
  local expected_tree="${2:-}"
  local log_file
  local rc
  local tmp_dir="${MUSE_PIPELINE_TMPDIR:-$repo_root/.tmp}"

  if [[ ! -s "$root_file" ]]; then
    echo "ROOT output is missing or empty: $root_file" >&2
    return 1
  fi

  mkdir -p "$tmp_dir"
  log_file="$(mktemp "$tmp_dir/validate_root.XXXXXX.log")"

  if run_stack_python "$repo_root/src/python/validate_root_file.py" \
      "$root_file" "$expected_tree" >"$log_file" 2>&1; then
    rm -f "$log_file"
    return 0
  else
    rc=$?
    cat "$log_file" >&2
    rm -f "$log_file"
    return "$rc"
  fi
}

count_root_payload() {
  local root_file="$1"
  local tree_name="$2"
  local branch_name="$3"
  local payload_field="$4"
  local stdout_log
  local stderr_log
  local rc
  local tmp_dir="${MUSE_PIPELINE_TMPDIR:-$repo_root/.tmp}"
  shift 4

  mkdir -p "$tmp_dir"
  stdout_log="$(mktemp "$tmp_dir/count_root_payload.XXXXXX.out")"
  stderr_log="$(mktemp "$tmp_dir/count_root_payload.XXXXXX.err")"

  if run_stack_python "$repo_root/src/python/count_root_payload.py" \
      "$root_file" "$tree_name" "$branch_name" "$payload_field" "$@" \
      >"$stdout_log" 2>"$stderr_log"; then
    cat "$stdout_log"
    rm -f "$stdout_log" "$stderr_log"
    return 0
  else
    rc=$?
    cat "$stdout_log"
    cat "$stderr_log" >&2
    rm -f "$stdout_log" "$stderr_log"
    return "$rc"
  fi
}

report_root_payload_count() {
  local root_file="$1"
  local tree_name="$2"
  local branch_name="$3"
  local payload_field="$4"

  count_root_payload "$root_file" "$tree_name" "$branch_name" "$payload_field" || true
}
