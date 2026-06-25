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
