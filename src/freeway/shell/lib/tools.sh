[[ -n "${MUSE_PIPELINE_TOOLS_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_TOOLS_SH_LOADED=1

run() {
  echo "+ $*" >&2
  "$@"
}

require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "missing required command: $cmd"
  done
}

require_env() {
  local name
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || die "required environment variable is not set: $name"
  done
}

with_dir() {
  local dir=$1
  shift

  pushd "$dir" >/dev/null || return
  "$@"
  local status=$?
  popd >/dev/null || return
  return "$status"
}

is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

join_by() {
  local delimiter="$1"
  shift

  local first=true
  local item
  for item in "$@"; do
    if [[ "$first" == true ]]; then
      first=false
    else
      printf '%s' "$delimiter"
    fi
    printf '%s' "$item"
  done
  printf '\n'
}
