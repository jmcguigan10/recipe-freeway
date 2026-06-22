#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$repo_root"

if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2))); then
  echo "orchestrator dry-run requires Bash 4.2+; found $BASH_VERSION" >&2
  exit 2
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

fake_sbatch="$tmp_dir/fake-sbatch"
fake_log="$tmp_dir/fake-sbatch.log"
data_root="$tmp_dir/data"
sim_tag="ci_pr_dry_run"
recipe_tag="ci_pr_recipe_dry_run"
sim_output_log="$tmp_dir/run_freeway_sim.out"
recipe_output_log="$tmp_dir/run_freeway_recipe.out"

cat > "$fake_sbatch" <<'FAKE_SBATCH'
#!/usr/bin/env bash
set -Eeuo pipefail

{
  printf 'CALL\n'
  for arg in "$@"; do
    printf '%s\n' "$arg"
  done
} >> "${FAKE_SBATCH_LOG:?}"

printf '12345'
FAKE_SBATCH
chmod +x "$fake_sbatch"

FAKE_SBATCH_LOG="$fake_log" \
DATA_ROOT="$data_root" \
FREEWAY_SBATCH_BIN="$fake_sbatch" \
  bash src/slurm/run_freeway.sh "$sim_tag" > "$sim_output_log"

grep -q 'submitted 00 g4psi' "$sim_output_log"
grep -q 'pending   01 mc2root' "$sim_output_log"
grep -q 'Summary: 1 submitted' "$sim_output_log"

grep -q '^--job-name=freeway_00_g4psi_ci_pr_dry_run$' "$fake_log"
grep -q '^--ntasks=100$' "$fake_log"
grep -q '^--mem=16$' "$fake_log"
grep -q '/src/slurm/freeway_stage_job.sh$' "$fake_log"
grep -q '^00$' "$fake_log"
grep -q '^ci_pr_dry_run$' "$fake_log"

[[ -f "$data_root/$sim_tag/configs/physics.sh" ]]
[[ -f "$data_root/$sim_tag/is_submitted.txt" ]]
grep -q '^00 g4psi 12345 ' "$data_root/$sim_tag/is_submitted.txt"

: > "$fake_log"
mkdir -p "$data_root/$recipe_tag"
printf 'fake g4psi output\n' > "$data_root/$recipe_tag/${recipe_tag}_g4psi.root"

FAKE_SBATCH_LOG="$fake_log" \
DATA_ROOT="$data_root" \
FREEWAY_SBATCH_BIN="$fake_sbatch" \
  bash src/slurm/run_freeway.sh "$recipe_tag" > "$recipe_output_log"

grep -q 'complete  00 g4psi' "$recipe_output_log"
grep -q 'submitted 01 mc2root' "$recipe_output_log"
grep -q 'pending   02 bh' "$recipe_output_log"
grep -q 'Summary: 1 submitted' "$recipe_output_log"

grep -q '^--job-name=freeway_01_mc2root_ci_pr_recipe_dry_run$' "$fake_log"
grep -q '^--ntasks=1$' "$fake_log"
grep -q '^--mem=16$' "$fake_log"
grep -q '/src/slurm/freeway_stage_job.sh$' "$fake_log"
grep -q '^01$' "$fake_log"
grep -q '^ci_pr_recipe_dry_run$' "$fake_log"

[[ -f "$data_root/$recipe_tag/configs/recipes.sh" ]]
[[ -f "$data_root/$recipe_tag/is_submitted.txt" ]]
grep -q '^01 mc2root 12345 ' "$data_root/$recipe_tag/is_submitted.txt"

echo "Orchestrator dry-run OK"
