#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../../.." && pwd -P)"
source "$repo_root/src/shell/lib/loader.sh"

[[ $# -le 1 ]] || freeway_usage "$0"
select_pipeline "${1:-}"
resolve_data_run_dir

hazard_truth_root="$(stage_output_root hazard_truth)"
events_csv="$(stage_output_path export_cs_events)"
summary_json="$data_run_dir/${run_tag}_cross_section_summary.json"
output_root="$(stage_output_root hazard_cutflow)"
output_csv="${output_root%.root}.csv"
tmp_root="$data_run_dir/.${run_tag}_hazard_cutflow.$$.$RANDOM.tmp.root"
tmp_csv="$data_run_dir/.${run_tag}_hazard_cutflow.$$.$RANDOM.tmp.csv"

for input in "$hazard_truth_root" "$events_csv" "$summary_json"; do
  require_file "$input"
done

cleanup() {
  rm -f "$tmp_root" "$tmp_csv"
}
trap cleanup EXIT

STACK_PYTHON_TIMEOUT="${HAZARD_CUTFLOW_TIMEOUT:-0}" \
  run_stack_python "$repo_root/src/python/export_hazard_cutflow.py" \
    --hazard-truth-root "$hazard_truth_root" \
    --events-csv "$events_csv" \
    --summary-json "$summary_json" \
    --output-root "$tmp_root" \
    --output-csv "$tmp_csv" \
    --reported-output-root "$output_root" \
    --reported-output-csv "$output_csv"

validate_root_file "$tmp_root" "hazard_cutflow"
[[ -s "$tmp_csv" ]] || die "missing hazard_cutflow CSV output: $tmp_csv"

mv -f "$tmp_root" "$output_root"
mv -f "$tmp_csv" "$output_csv"
trap - EXIT
