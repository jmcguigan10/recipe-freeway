if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  job_id="$(
    sbatch \
      --parsable \
      --partition="$recipe_slurm_partition" \
      --nodes="$recipe_slurm_nodes" \
      --ntasks="$recipe_slurm_ntasks" \
      --cpus-per-task="$recipe_slurm_cpus_per_task" \
      --mem="$recipe_slurm_mem" \
      --time="$recipe_slurm_time" \
      --job-name="relay_${stage}_${run_tag}" \
      --output="$log_dir/%x-%j.out" \
      --error="$log_dir/%x-%j.err" \
      --export=ALL,PIPELINE_TAG="$pipeline_tag",DATA_RUN_DIR="$data_run_dir",REAL_MUSE_REPO_ROOT="$repo_root" \
      "$0" "$stage" "$pipeline_tag"
  )"

  submitted_file="$data_run_dir/is_submitted.txt"
  touch "$submitted_file"
  if ! grep -Fxq -- "$stage" "$submitted_file"; then
    printf '%s\n' "$stage" >> "$submitted_file"
  fi

  printf 'Submitted relay stage %s as job: %s\n' "$stage" "$job_id"
  printf 'Data run dir: %s\n' "$data_run_dir"
  printf 'Slurm output: %s\n' "$log_dir"
  exit 0
fi