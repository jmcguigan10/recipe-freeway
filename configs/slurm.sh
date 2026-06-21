declare -gA SLURM_SIM_CONFIG=(
  [PARTITION]="defq"
  [NODES]="1"
  # Stage 00 runs one g4PSI process per task and splits N_EVENTS across them.
  [NTASKS]="4"
  [CPUS_PER_TASK]="1"
  [MEM]="16"
  [TIME]="12:00:00"
)

declare -gA SLURM_RECIPE_CONFIG=(
  [PARTITION]="defq"
  [NODES]="1"
  [NTASKS]="1"
  [CPUS_PER_TASK]="2"
  [MEM]="16G"
  [TIME]="12:00:00"
)
