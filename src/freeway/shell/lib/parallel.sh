[[ -n "${MUSE_PIPELINE_PARALLEL_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_PARALLEL_SH_LOADED=1

parallel_reset_workers() {
  parallel_worker_labels=()
  parallel_worker_roots=()
  parallel_worker_logs=()
  parallel_worker_pids=()
  parallel_worker_statuses=()
  parallel_worker_started_at=()
  parallel_worker_exit_codes=()
}

parallel_add_worker() {
  local label="$1"
  local root_path="$2"
  local log_path="$3"
  local pid="$4"

  parallel_worker_labels+=("$label")
  parallel_worker_roots+=("$root_path")
  parallel_worker_logs+=("$log_path")
  parallel_worker_pids+=("$pid")
  parallel_worker_statuses+=("running")
  parallel_worker_started_at+=("$(date +%s)")
  parallel_worker_exit_codes+=("0")
}

parallel_status_elapsed() {
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

parallel_status_root_size() {
  local root_path="$1"

  if [[ -s "$root_path" ]]; then
    du -h "$root_path" 2>/dev/null | awk '{print $1}'
  else
    printf '0\n'
  fi
}

parallel_status_bar() {
  local status="$1"
  local worker_index="$2"
  local tick="$3"
  local width=24
  local position=$(((tick + worker_index) % width))
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

parallel_render_worker_statuses() {
  local tick="$1"
  local use_tty="$2"
  local printed_lines="$3"
  local worker_count="${#parallel_worker_pids[@]}"
  local worker_index
  local label
  local status
  local elapsed
  local root_size
  local bar
  local log_name

  if [[ "$use_tty" == "1" && "$printed_lines" -gt 0 ]]; then
    printf '\033[%sA' "$printed_lines"
  fi

  for ((worker_index = 0; worker_index < worker_count; worker_index++)); do
    label="${parallel_worker_labels[$worker_index]}"
    status="${parallel_worker_statuses[$worker_index]}"
    elapsed="$(parallel_status_elapsed "${parallel_worker_started_at[$worker_index]}")"
    root_size="$(parallel_status_root_size "${parallel_worker_roots[$worker_index]}")"
    bar="$(parallel_status_bar "$status" "$worker_index" "$tick")"
    log_name="$(basename -- "${parallel_worker_logs[$worker_index]}")"

    if [[ "$use_tty" == "1" ]]; then
      printf '\r\033[K'
    fi
    printf '%s %s %-7s elapsed=%s root=%6s log=%s\n' \
      "$label" \
      "$bar" \
      "$status" \
      "$elapsed" \
      "$root_size" \
      "$log_name"
  done
}

parallel_monitor_workers() {
  local status_heading="$1"
  local status_interval="$2"
  local plain_flag_name="${3:-PARALLEL_STATUS_PLAIN}"
  local plain_flag=""
  local use_tty=0
  local printed_lines=0
  local tick=0
  local last_render=0
  local now
  local active
  local worker_count
  local worker_index
  local rc
  local failed=0

  if [[ -n "$plain_flag_name" ]]; then
    plain_flag="${!plain_flag_name:-}"
  fi
  if [[ -t 1 && "${TERM:-}" != "dumb" ]] && ! is_truthy "$plain_flag"; then
    use_tty=1
  fi

  while :; do
    active=0
    worker_count="${#parallel_worker_pids[@]}"
    for ((worker_index = 0; worker_index < worker_count; worker_index++)); do
      if [[ "${parallel_worker_statuses[$worker_index]}" != "running" ]]; then
        continue
      fi

      if kill -0 "${parallel_worker_pids[$worker_index]}" 2>/dev/null; then
        active=$((active + 1))
      elif wait "${parallel_worker_pids[$worker_index]}"; then
        parallel_worker_statuses[$worker_index]="done"
      else
        rc=$?
        parallel_worker_statuses[$worker_index]="failed"
        parallel_worker_exit_codes[$worker_index]="$rc"
        failed=1
      fi
    done

    now="$(date +%s)"
    if ((tick == 0 || active == 0 || now - last_render >= status_interval)); then
      if [[ "$use_tty" != "1" ]]; then
        printf '%s at %s\n' "$status_heading" "$(date '+%Y-%m-%d %H:%M:%S')"
      fi
      parallel_render_worker_statuses "$tick" "$use_tty" "$printed_lines"
      printed_lines="${#parallel_worker_pids[@]}"
      last_render="$now"
      tick=$((tick + 1))
    fi

    ((active > 0)) || break
    sleep 1
  done

  return "$failed"
}

parallel_report_worker_results() {
  local complete_prefix="$1"
  local failed_prefix="$2"
  local tail_lines="${3:-80}"
  local worker_count="${#parallel_worker_pids[@]}"
  local worker_index
  local label
  local log_path
  local rc

  for ((worker_index = 0; worker_index < worker_count; worker_index++)); do
    label="${parallel_worker_labels[$worker_index]}"
    log_path="${parallel_worker_logs[$worker_index]}"
    if [[ "${parallel_worker_statuses[$worker_index]}" == "done" ]]; then
      echo "$complete_prefix $label: $log_path"
    elif [[ "${parallel_worker_statuses[$worker_index]}" == "failed" ]]; then
      rc="${parallel_worker_exit_codes[$worker_index]}"
      echo "$failed_prefix $label failed with exit code $rc: $log_path" >&2
      tail -n "$tail_lines" "$log_path" >&2 || true
    fi
  done
}

parallel_reset_workers
