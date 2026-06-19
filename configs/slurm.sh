declare -gA SLURM_SIM_CONFIG=(
  [PARTITION]="defq"
  [NODES]="1"
  [NTASKS]="1"
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
