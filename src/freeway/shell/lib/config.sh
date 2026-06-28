[[ -n "${MUSE_PIPELINE_CONFIG_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_CONFIG_SH_LOADED=1

pipeline_config_names=(physics slurm g4psi recipes)
freeway_snapshot_config_names=(physics g4psi recipes)

reset_config_hashes() {
  unset PHYSICS_CONFIG
  unset SLURM_SIM_CONFIG
  unset SLURM_RECIPE_CONFIG
  unset G4PSI_CONFIG
  unset FREEWAY_STAGE_KIND
  unset FREEWAY_STAGE_SCRIPT
  unset FREEWAY_STAGE_OUTPUT
  unset FREEWAY_STAGE_OUTPUT_EXT
  unset FREEWAY_STAGE_TREE
  unset FREEWAY_STAGE_RECIPE
  unset FREEWAY_STAGE_INPUTS
  unset FREEWAY_STAGE_INIT
  unset FREEWAY_STAGE_COOKER_CALLS
  unset FREEWAY_STAGE_REPORT_PAYLOAD

  FREEWAY_STAGE_ORDER=()

  declare -gA PHYSICS_CONFIG
  declare -gA SLURM_SIM_CONFIG
  declare -gA SLURM_RECIPE_CONFIG
  declare -gA G4PSI_CONFIG
  declare -gA FREEWAY_STAGE_KIND
  declare -gA FREEWAY_STAGE_SCRIPT
  declare -gA FREEWAY_STAGE_OUTPUT
  declare -gA FREEWAY_STAGE_OUTPUT_EXT
  declare -gA FREEWAY_STAGE_TREE
  declare -gA FREEWAY_STAGE_RECIPE
  declare -gA FREEWAY_STAGE_INPUTS
  declare -gA FREEWAY_STAGE_INIT
  declare -gA FREEWAY_STAGE_COOKER_CALLS
  declare -gA FREEWAY_STAGE_REPORT_PAYLOAD
}

require_config_file() {
  local config_file="$1"
  [[ -f "$config_file" ]] || die "required config file not found: $config_file"
}

repo_config_file_for() {
  local name="$1"

  case "$name" in
    physics|g4psi|recipes)
      printf '%s/configs/freeway/%s.sh\n' "$repo_root" "$name"
      ;;
    slurm)
      printf '%s/configs/slurm/slurm.sh\n' "$repo_root"
      ;;
    *)
      die "unknown config name: $name"
      ;;
  esac
}

snapshot_config_file_for() {
  local name="$1"
  printf '%s/configs/freeway/%s.sh\n' "$data_run_dir" "$name"
}

legacy_snapshot_config_file_for() {
  local name="$1"
  printf '%s/configs/%s.sh\n' "$data_run_dir" "$name"
}

config_file_for() {
  local name="$1"
  local snapshot
  local legacy_snapshot

  # Slurm queues and accounts are execution-environment config, not run provenance.
  # Use the current repo config so old run snapshots do not break resubmission.
  if [[ "$name" == "slurm" ]]; then
    repo_config_file_for "$name"
    return
  fi

  if [[ -n "${data_run_dir:-}" ]]; then
    snapshot="$(snapshot_config_file_for "$name")"
    legacy_snapshot="$(legacy_snapshot_config_file_for "$name")"
    if [[ -f "$snapshot" ]]; then
      printf '%s\n' "$snapshot"
      return
    fi
    if [[ -f "$legacy_snapshot" ]]; then
      printf '%s\n' "$legacy_snapshot"
      return
    fi
  fi

  repo_config_file_for "$name"
}

source_config_file() {
  local name="$1"
  local config_file

  config_file="$(config_file_for "$name")"
  require_config_file "$config_file"

  # shellcheck source=/dev/null
  source "$config_file"
}

load_pipeline_configs() {
  local name

  reset_config_hashes
  for name in "${pipeline_config_names[@]}"; do
    source_config_file "$name" || return $?
  done
}

snapshot_configs() {
  local snapshot_config_dir="$data_run_dir/configs/freeway"
  local name
  local source_file
  local target_file
  local legacy_target_file

  mkdir -p "$snapshot_config_dir"
  for name in "${freeway_snapshot_config_names[@]}"; do
    source_file="$(repo_config_file_for "$name")"
    target_file="$(snapshot_config_file_for "$name")"
    legacy_target_file="$(legacy_snapshot_config_file_for "$name")"
    require_config_file "$source_file"

    # Existing flat snapshots are old run provenance. Keep using them instead of
    # creating a new-format snapshot from current repo defaults.
    if [[ -f "$legacy_target_file" && ! -f "$target_file" ]]; then
      continue
    fi

    [[ -f "$target_file" ]] || cp "$source_file" "$target_file"
  done
}

apply_physics_config() {
  run_nr="${PHYSICS_CONFIG[RUN_NR]:-22308}"
  particle="${PHYSICS_CONFIG[PARTICLE]:-e+}"
  particle_tag="${PHYSICS_CONFIG[PARTICLE_TAG]:-e_pos}"
  part="${PHYSICS_CONFIG[PART]:-0}"
  beam_momentum="${PHYSICS_CONFIG[BEAM_MOMENTUM]:-159.279}"
  n_events="${PHYSICS_CONFIG[N_EVENTS]:-675847}"
  seed_1="${PHYSICS_CONFIG[SEED_1]:-1778753222}"
  seed_2="${PHYSICS_CONFIG[SEED_2]:-1778753290}"
  rad_mode="${PHYSICS_CONFIG[RAD_MODE]:-rad2}"
  store_t0="${PHYSICS_CONFIG[STORE_T0]:-false}"
  rad_mode="${rad_mode#--}"
  case "$rad_mode" in
    ""|none|off|false|0)
      rad_mode="none"
      rad_flag=""
      ;;
    rad|rad1|rad2|rad3)
      rad_flag="--$rad_mode"
      ;;
    *)
      die "PHYSICS_CONFIG[RAD_MODE] must be one of none, rad, rad1, rad2, or rad3: $rad_mode"
      ;;
  esac

  RUN_NR="$run_nr"
  PARTICLE="$particle"
  PARTICLE_TAG="$particle_tag"
  PART="$part"
  BEAM_MOMENTUM="$beam_momentum"
  N_EVENTS="$n_events"
  SEED_1="$seed_1"
  SEED_2="$seed_2"
  RAD_MODE="$rad_mode"
  STORE_T0="$store_t0"
}

validate_slurm_mem() {
  local name="$1"
  local value="$2"

  [[ "$value" =~ ^[1-9][0-9]*([KMGT])?$ ]] || \
    die "$name must be a positive integer with optional Slurm memory unit like 16, 16000M, 16G, or 1T: $value"
}

apply_slurm_config() {
  sim_slurm_account="${SLURM_SIM_CONFIG[ACCOUNT]:-}"
  sim_slurm_partition="${SLURM_SIM_CONFIG[PARTITION]:-defq}"
  sim_slurm_qos="${SLURM_SIM_CONFIG[QOS]:-}"
  sim_slurm_nodes="${SLURM_SIM_CONFIG[NODES]:-1}"
  sim_slurm_ntasks="${SLURM_SIM_CONFIG[NTASKS]:-1}"
  sim_slurm_cpus_per_task="${SLURM_SIM_CONFIG[CPUS_PER_TASK]:-1}"
  sim_slurm_mem="${SLURM_SIM_CONFIG[MEM]:-16}"
  sim_slurm_time="${SLURM_SIM_CONFIG[TIME]:-12:00:00}"

  recipe_slurm_account="${SLURM_RECIPE_CONFIG[ACCOUNT]:-}"
  recipe_slurm_partition="${SLURM_RECIPE_CONFIG[PARTITION]:-defq}"
  recipe_slurm_qos="${SLURM_RECIPE_CONFIG[QOS]:-}"
  recipe_slurm_nodes="${SLURM_RECIPE_CONFIG[NODES]:-1}"
  recipe_slurm_ntasks="${SLURM_RECIPE_CONFIG[NTASKS]:-1}"
  recipe_slurm_cpus_per_task="${SLURM_RECIPE_CONFIG[CPUS_PER_TASK]:-1}"
  recipe_slurm_mem="${SLURM_RECIPE_CONFIG[MEM]:-16}"
  recipe_slurm_time="${SLURM_RECIPE_CONFIG[TIME]:-12:00:00}"

  validate_slurm_mem "SLURM_SIM_CONFIG[MEM]" "$sim_slurm_mem"
  validate_slurm_mem "SLURM_RECIPE_CONFIG[MEM]" "$recipe_slurm_mem"
}
