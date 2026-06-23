SLURM_CLUSTER="${SLURM_CLUSTER:-isaac}"

declare -gA SLURM_CLUSTER_ACCOUNT=(
  [isaac]="isaac-utk0307"
  [theia]=""
)

declare -gA SLURM_CLUSTER_PARTITION=(
  [isaac]="condo-slagergr"
  [theia]="defq"
)

declare -gA SLURM_CLUSTER_QOS=(
  [isaac]="condo"
  [theia]=""
)

if [[ -z "${SLURM_CLUSTER_PARTITION[$SLURM_CLUSTER]+set}" ]]; then
  echo "error: unknown SLURM_CLUSTER: $SLURM_CLUSTER" >&2
  echo "hint: use one of: isaac, theia" >&2
  return 2
fi

declare -gA SLURM_SIM_CONFIG=(
  [ACCOUNT]="${SLURM_CLUSTER_ACCOUNT[$SLURM_CLUSTER]}"
  [PARTITION]="${SLURM_CLUSTER_PARTITION[$SLURM_CLUSTER]}"
  [QOS]="${SLURM_CLUSTER_QOS[$SLURM_CLUSTER]}"
  [NODES]="1"
  # Stage 00 runs one g4PSI process per task and splits N_EVENTS across them.
  [NTASKS]="4"
  [CPUS_PER_TASK]="1"
  [MEM]="16G"
  [TIME]="12:00:00"
)

declare -gA SLURM_RECIPE_CONFIG=(
  [ACCOUNT]="${SLURM_CLUSTER_ACCOUNT[$SLURM_CLUSTER]}"
  [PARTITION]="${SLURM_CLUSTER_PARTITION[$SLURM_CLUSTER]}"
  [QOS]="${SLURM_CLUSTER_QOS[$SLURM_CLUSTER]}"
  [NODES]="1"
  [NTASKS]="1"
  [CPUS_PER_TASK]="1"
  [MEM]="16G"
  [TIME]="12:00:00"
)
