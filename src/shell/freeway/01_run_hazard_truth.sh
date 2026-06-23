#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../../.." && pwd -P)"
source "$repo_root/src/shell/lib/loader.sh"

[[ $# -le 1 ]] || freeway_usage "$0"
select_pipeline "${1:-}"
resolve_data_run_dir

input_root="$(stage_output_root g4psi)"
output_root="$(stage_output_root hazard_truth)"
output_csv="${output_root%.root}.csv"
tmp_root="$data_run_dir/.${run_tag}_hazard_truth.$$.$RANDOM.tmp.root"
tmp_csv="$data_run_dir/.${run_tag}_hazard_truth.$$.$RANDOM.tmp.csv"
particle_pid="$(particle_pid_for "$particle")"

require_file "$input_root"

cleanup() {
  rm -f "$tmp_root" "$tmp_csv"
}
trap cleanup EXIT

STACK_PYTHON_TIMEOUT="${HAZARD_TRUTH_TIMEOUT:-0}" \
  run_stack_python "$repo_root/src/python/export_hazard_truth.py" \
    --input-root "$input_root" \
    --output-root "$tmp_root" \
    --output-csv "$tmp_csv" \
    --run-tag "$run_tag" \
    --particle "$particle" \
    --particle-pid "$particle_pid" \
    --momentum-mev "$beam_momentum"

validate_root_file "$tmp_root" "hazard_truth"
[[ -s "$tmp_csv" ]] || die "missing hazard_truth CSV output: $tmp_csv"

mv -f "$tmp_root" "$output_root"
mv -f "$tmp_csv" "$output_csv"
trap - EXIT
