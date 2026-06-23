#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../../.." && pwd -P)"
source "$repo_root/src/shell/lib/loader.sh"

[[ $# -le 1 ]] || freeway_usage "$0"
select_pipeline "${1:-}"
resolve_data_run_dir

hazard_truth_root="$(stage_output_root hazard_truth)"
hazard_cutflow_root="$(stage_output_root hazard_cutflow)"
events_csv="$(stage_output_path export_cs_events)"
summary_json="$data_run_dir/${run_tag}_cross_section_summary.json"
output_parquet="$(stage_output_path export_training_table)"
output_csv="${output_parquet%.parquet}.csv"
output_summary_json="$data_run_dir/${run_tag}_training_summary.json"
tmp_parquet="$data_run_dir/.${run_tag}_training_candidates.$$.$RANDOM.tmp.parquet"
tmp_csv="$data_run_dir/.${run_tag}_training_candidates.$$.$RANDOM.tmp.csv"
tmp_summary_json="$data_run_dir/.${run_tag}_training_summary.$$.$RANDOM.tmp.json"

for input in "$hazard_truth_root" "$hazard_cutflow_root" "$events_csv" "$summary_json"; do
  require_file "$input"
done

cleanup() {
  rm -f "$tmp_parquet" "$tmp_csv" "$tmp_summary_json"
}
trap cleanup EXIT

STACK_PYTHON_TIMEOUT="${EXPORT_TRAINING_TABLE_TIMEOUT:-0}" \
  run_stack_python "$repo_root/src/python/export_training_table.py" \
    --hazard-truth-root "$hazard_truth_root" \
    --hazard-cutflow-root "$hazard_cutflow_root" \
    --events-csv "$events_csv" \
    --summary-json "$summary_json" \
    --output-csv "$tmp_csv" \
    --output-parquet "$tmp_parquet" \
    --output-summary-json "$tmp_summary_json" \
    --reported-output-csv "$output_csv" \
    --reported-output-parquet "$output_parquet" \
    --reported-output-summary-json "$output_summary_json" \
    --hazard-truth-parquet "$data_run_dir/${run_tag}_hazard_truth.parquet" \
    --hazard-cutflow-parquet "$data_run_dir/${run_tag}_hazard_cutflow.parquet"

[[ -s "$tmp_csv" ]] || die "missing training CSV output: $tmp_csv"
[[ -s "$tmp_parquet" ]] || die "missing training Parquet output: $tmp_parquet"
[[ -s "$tmp_summary_json" ]] || die "missing training summary JSON output: $tmp_summary_json"

mv -f "$tmp_csv" "$output_csv"
mv -f "$tmp_parquet" "$output_parquet"
mv -f "$tmp_summary_json" "$output_summary_json"
trap - EXIT
