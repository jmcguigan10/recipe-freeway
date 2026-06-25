[[ -n "${MUSE_PIPELINE_ERRORS_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_ERRORS_SH_LOADED=1

die() {
  echo "error: $*" >&2
  exit 1
}

on_error() {
  local exit_code=$?
  echo "error: command failed: $BASH_COMMAND" >&2
  echo "stack trace:" >&2

  local i
  for ((i = 0; i < ${#FUNCNAME[@]} - 1; i++)); do
    echo "  at ${FUNCNAME[$i]} (${BASH_SOURCE[$i+1]}:${BASH_LINENO[$i]})" >&2
  done

  exit "$exit_code"
}
