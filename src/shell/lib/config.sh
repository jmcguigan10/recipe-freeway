[[ -n "${MUSE_PIPELINE_CONFIG_SH_LOADED:-}" ]] && return 0
MUSE_PIPELINE_CONFIG_SH_LOADED=1

pipeline_config_names=(physics slurm g4psi recipes)

reset_config_hashes() {
  unset PHYSICS_CONFIG
  unset SLURM_SIM_CONFIG
  unset SLURM_RECIPE_CONFIG
  unset G4PSI_CONFIG
  unset FREEWAY_STAGE_SCRIPT
  unset FREEWAY_STAGE_OUTPUT
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
  declare -gA FREEWAY_STAGE_SCRIPT
  declare -gA FREEWAY_STAGE_OUTPUT
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

config_file_for() {
  local name="$1"
  local snapshot="${data_run_dir:-}/configs/$name.sh"

  if [[ -n "${data_run_dir:-}" && -f "$snapshot" ]]; then
    printf '%s\n' "$snapshot"
  else
    printf '%s/configs/%s.sh\n' "$repo_root" "$name"
  fi
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
    source_config_file "$name"
  done
}

snapshot_configs() {
  local snapshot_config_dir="$data_run_dir/configs"
  local name
  local source_file
  local target_file

  mkdir -p "$snapshot_config_dir"
  for name in "${pipeline_config_names[@]}"; do
    source_file="$repo_root/configs/$name.sh"
    target_file="$snapshot_config_dir/$name.sh"
    require_config_file "$source_file"
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
  rad_mode="${rad_mode#--}"
  rad_flag="--$rad_mode"

  RUN_NR="$run_nr"
  PARTICLE="$particle"
  PARTICLE_TAG="$particle_tag"
  PART="$part"
  BEAM_MOMENTUM="$beam_momentum"
  N_EVENTS="$n_events"
  SEED_1="$seed_1"
  SEED_2="$seed_2"
  RAD_MODE="$rad_mode"
}

apply_slurm_config() {
  sim_slurm_partition="${SLURM_SIM_CONFIG[PARTITION]:-defq}"
  sim_slurm_nodes="${SLURM_SIM_CONFIG[NODES]:-1}"
  sim_slurm_ntasks="${SLURM_SIM_CONFIG[NTASKS]:-1}"
  sim_slurm_cpus_per_task="${SLURM_SIM_CONFIG[CPUS_PER_TASK]:-1}"
  sim_slurm_mem="${SLURM_SIM_CONFIG[MEM]:-16G}"
  sim_slurm_time="${SLURM_SIM_CONFIG[TIME]:-12:00:00}"

  recipe_slurm_partition="${SLURM_RECIPE_CONFIG[PARTITION]:-defq}"
  recipe_slurm_nodes="${SLURM_RECIPE_CONFIG[NODES]:-1}"
  recipe_slurm_ntasks="${SLURM_RECIPE_CONFIG[NTASKS]:-1}"
  recipe_slurm_cpus_per_task="${SLURM_RECIPE_CONFIG[CPUS_PER_TASK]:-1}"
  recipe_slurm_mem="${SLURM_RECIPE_CONFIG[MEM]:-16G}"
  recipe_slurm_time="${SLURM_RECIPE_CONFIG[TIME]:-12:00:00}"
}
