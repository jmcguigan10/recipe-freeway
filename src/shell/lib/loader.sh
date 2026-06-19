[[ -n "${MUSE_PIPELINE_LOADER_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_LOADER_SH_LOADED=1

loader_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$loader_dir/../../.." && pwd -P)"

require_supported_bash() {
  if (( BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2) )); then
    echo "error: this pipeline uses Bash associative arrays and requires Bash 4.2+." >&2
    echo "hint: run through packman-muse/scripts/pixi-local or put Bash 5 earlier on PATH." >&2
    return 2
  fi
}

source_project_lib() {
  local name="$1"
  local path="$repo_root/src/shell/lib/$name"

  [[ -f "$path" ]] || {
    echo "error: missing project library: $path" >&2
    return 2
  }

  # shellcheck source=/dev/null
  source "$path"
}

load_muse_pipeline_shell() {
  [[ -n "${MUSE_PIPELINE_SHELL_LOADED:-}" ]] && return 0

  require_supported_bash || return $?
  MUSE_PIPELINE_SHELL_LOADED=1

  source_project_lib errors.sh || return $?
  source_project_lib tools.sh || return $?
  source_project_lib paths.sh || return $?
  source_project_lib config.sh || return $?
  source_project_lib root.sh || return $?
  source_project_lib orchs/env.func.sh || return $?
  source_project_lib orchs/cooker.func.sh || return $?
  source_project_lib orchs/g4psi.func.sh || return $?
  source_project_lib freeway.sh || return $?
}

load_muse_pipeline_shell
