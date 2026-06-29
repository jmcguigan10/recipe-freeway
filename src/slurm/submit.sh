#!/usr/bin/env bash
#SBATCH --job-name=muse-relay
# Cluster account/partition/qos are selected in configs/slurm/slurm.sh and passed to sbatch at runtime.
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=12:00:00

set -euo pipefail
