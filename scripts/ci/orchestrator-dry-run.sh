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
tag="ci_pr_dry_run"
output_log="$tmp_dir/run_freeway.out"

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
  "$BASH" src/slurm/run_freeway.sh "$tag" > "$output_log"

grep -q 'submitted 00 g4psi' "$output_log"
grep -q 'pending   01 hazard_truth' "$output_log"
grep -q 'Summary: 1 submitted' "$output_log"

grep -q '^--job-name=freeway_00_g4psi_ci_pr_dry_run$' "$fake_log"
grep -q '^--partition=condo-slagergr$' "$fake_log"
grep -q '^--ntasks=4$' "$fake_log"
grep -q '^--mem=16G$' "$fake_log"
grep -q '^--account=isaac-utk0307$' "$fake_log"
grep -q '^--qos=condo$' "$fake_log"
grep -q '/src/slurm/freeway_stage_job.sh$' "$fake_log"
grep -q '^00$' "$fake_log"
grep -q '^ci_pr_dry_run$' "$fake_log"

[[ -f "$data_root/$tag/configs/physics.sh" ]]
[[ -f "$data_root/$tag/is_submitted.txt" ]]
grep -q '^00 g4psi 12345 ' "$data_root/$tag/is_submitted.txt"

echo "Orchestrator dry-run OK"
