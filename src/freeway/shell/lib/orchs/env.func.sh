[[ -n "${MUSE_PIPELINE_ENV_FUNC_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_ENV_FUNC_SH_LOADED=1

select_pipeline() {
  local requested="${1:-${PIPELINE_TAG:-}}"
  local expected_data_run_dir

  if [[ -z "$requested" ]]; then
    echo "Pipeline tag is required." >&2
    echo "Use a tag such as: mc22308_rad2_e_pos_part0" >&2
    exit 2
  fi
  if [[ "$requested" == */* ]]; then
    echo "Pipeline tag must be a name, not a path: $requested" >&2
    exit 2
  fi

  pipeline_tag="$requested"
  run_tag="$pipeline_tag"
  data_root="${DATA_ROOT:-$repo_root/data_process}"
  expected_data_run_dir="$data_root/$run_tag"

  if [[ -n "${DATA_RUN_DIR:-}" && "$DATA_RUN_DIR" != "$expected_data_run_dir" ]]; then
    echo "DATA_RUN_DIR does not match pipeline tag." >&2
    echo "  expected: $expected_data_run_dir" >&2
    echo "  got:      $DATA_RUN_DIR" >&2
    exit 2
  fi

  data_run_dir="$expected_data_run_dir"

  load_pipeline_configs
  apply_physics_config
  apply_slurm_config

  export PIPELINE_TAG="$pipeline_tag"
  export RUN_TAG="$run_tag"
  export DATA_RUN_DIR="$data_run_dir"
}

require_pipeline_selected() {
  if [[ -z "${pipeline_tag:-}" || -z "${data_run_dir:-}" ]]; then
    echo "Pipeline config has not been selected." >&2
    exit 2
  fi
}

create_data_run_dir() {
  require_pipeline_selected
  mkdir -p "$data_run_dir"
  snapshot_configs
}

resolve_data_run_dir() {
  require_pipeline_selected

  if [[ ! -d "$data_run_dir" ]]; then
    echo "Data run directory does not exist: $data_run_dir" >&2
    echo "Run src/freeway/shell/freeway/00_run_g4psi.sh $pipeline_tag first, or submit freeway item 00." >&2
    exit 2
  fi

  snapshot_configs
}
