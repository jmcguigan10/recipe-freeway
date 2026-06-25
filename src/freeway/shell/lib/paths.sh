[[ -n "${MUSE_PIPELINE_PATHS_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_PATHS_SH_LOADED=1

stack_dir="${STACK_DIR:-$repo_root/packman-muse}"
muse_src_dir="${MUSE_SRC_DIR:-$stack_dir/.install/src/muse}"
project_helper_dir="$repo_root/src/freeway/shell/helpers"

resolve_path_spec() {
  local spec="$1"
  local env_name
  local fallback
  local value

  case "$spec" in
    "")
      return 1
      ;;
    env:*:*)
      value="${spec#env:}"
      env_name="${value%%:*}"
      fallback="${value#*:}"
      if [[ -n "${!env_name:-}" ]]; then
        printf '%s\n' "${!env_name}"
      else
        resolve_path_spec "$fallback"
      fi
      ;;
    repo:*)
      printf '%s/%s\n' "$repo_root" "${spec#repo:}"
      ;;
    stack:*)
      printf '%s/%s\n' "$stack_dir" "${spec#stack:}"
      ;;
    muse:*)
      printf '%s/%s\n' "$muse_src_dir" "${spec#muse:}"
      ;;
    /*)
      printf '%s\n' "$spec"
      ;;
    *)
      printf '%s/%s\n' "$repo_root" "$spec"
      ;;
  esac
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || die "required file not found: $path"
}

require_dir() {
  local path="$1"
  [[ -d "$path" ]] || die "required directory not found: $path"
}
