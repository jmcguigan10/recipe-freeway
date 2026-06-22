declare -gA SLURM_SIM_CONFIG=(
  [PARTITION]="defq"
  [NODES]="1"
  # Stage 00 runs one g4PSI process per task and splits N_EVENTS across them.
  [NTASKS]="100"
  [CPUS_PER_TASK]="1"
  [MEM]="16"
  [TIME]="12:00:00"
)

declare -gA SLURM_RECIPE_CONFIG=(
  [PARTITION]="defq"
  [NODES]="1"
  # Cooker stages run one cooker process per task and split their primary input tree.
  [NTASKS]="1"
  [CPUS_PER_TASK]="1"
  [MEM]="16"
  [TIME]="12:00:00"
)
