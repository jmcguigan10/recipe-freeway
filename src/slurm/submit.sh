#!/usr/bin/env bash
#SBATCH --job-name=muse-relay
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=12:00:00

set -euo pipefail