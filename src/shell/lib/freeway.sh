[[ -n "${MUSE_PIPELINE_FREEWAY_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_FREEWAY_SH_LOADED=1

freeway_usage() {
  local script_name="${1:-freeway-stage.sh}"
  echo "usage: $script_name <pipeline-tag>" >&2
  exit 2
}

require_freeway_stage() {
  local stage="$1"
  [[ -n "${FREEWAY_STAGE_OUTPUT[$stage]:-}" ]] || die "unknown freeway stage: $stage"
}

freeway_stage_by_index() {
  local idx="$1"
  (( idx >= 0 && idx < ${#FREEWAY_STAGE_ORDER[@]} )) || return 1
  printf '%s\n' "${FREEWAY_STAGE_ORDER[$idx]}"
}

describe_freeway_stage() {
  local stage="$1"
  local recipe="${2:-}"
  local inputs="${3:-}"
  local output="${4:-}"

  echo "Freeway stage:  $stage"
  echo "Pipeline tag:   $pipeline_tag"
  echo "Data run dir:   $data_run_dir"
  [[ -n "$recipe" ]] && echo "Recipe:         $recipe"
  [[ -n "$inputs" ]] && echo "Inputs:         $inputs"
  [[ -n "$output" ]] && echo "Output:         $output"
}

run_freeway_recipe_stage() {
  local stage="$1"
  local recipe
  local input_roots
  local output_root
  local expected_tree
  local init_path=""
  local init_spec
  local call_spec
  local cooker_call
  local report_spec
  local report=()
  local cooker_args=()

  require_freeway_stage "$stage"

  recipe="$(resolve_path_spec "${FREEWAY_STAGE_RECIPE[$stage]}")"
  input_roots="$(stage_input_roots "$stage")"
  output_root="$(stage_output_root "$stage")"
  expected_tree="${FREEWAY_STAGE_TREE[$stage]}"

  require_file "$recipe"
  init_spec="${FREEWAY_STAGE_INIT[$stage]:-}"
  if [[ -n "$init_spec" ]]; then
    init_path="$(resolve_path_spec "$init_spec")"
    cooker_args+=("-i" "$init_path")
  fi
  call_spec="${FREEWAY_STAGE_COOKER_CALLS[$stage]:-}"
  for cooker_call in $call_spec; do
    cooker_call="${cooker_call//@BEAM_MOMENTUM@/$BEAM_MOMENTUM}"
    cooker_args+=("-c" "$cooker_call")
  done
  cooker_args+=("$input_roots")

  describe_freeway_stage "$stage" "$recipe" "$input_roots" "$output_root"

  run_cooker_stage_root "$stage" "$output_root" "$expected_tree" \
    "$recipe" "${cooker_args[@]}"

  report_spec="${FREEWAY_STAGE_REPORT_PAYLOAD[$stage]:-}"
  if [[ -n "$report_spec" ]]; then
    read -r -a report <<< "$report_spec"
    report_root_payload_count "$output_root" "${report[0]}" "${report[1]}" "${report[2]}"
  fi
}

run_freeway_stage() {
  local stage="$1"
  local script_name
  shift

  script_name="${1:-$0}"
  [[ $# -gt 0 ]] && shift

  [[ $# -le 1 ]] || freeway_usage "$script_name"

  select_pipeline "${1:-}"
  require_freeway_stage "$stage"

  if [[ "$stage" == "g4psi" ]]; then
    create_data_run_dir
    describe_freeway_stage "$stage" "" "" "$(stage_output_root g4psi)"
    run_g4psi_stage
  else
    resolve_data_run_dir
    run_freeway_recipe_stage "$stage"
  fi
}

freeway_stage_main() {
  local stage="$1"
  shift
  run_freeway_stage "$stage" "$0" "$@"
}
