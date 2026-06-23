#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../../.." && pwd -P)"
source "$repo_root/src/shell/lib/loader.sh"

[[ $# -le 1 ]] || freeway_usage "$0"
select_pipeline "${1:-}"
resolve_data_run_dir

g4psi_root="$(stage_output_root g4psi)"
hazard_truth_root="$(stage_output_root hazard_truth)"
cross_section_root="$(stage_output_root cross_section)"
events_csv="$(stage_output_path export_cs_events)"
summary_json="$data_run_dir/${run_tag}_cross_section_summary.json"
tmp_events_csv="$data_run_dir/.${run_tag}_cross_section_events.$$.$RANDOM.tmp.csv"
tmp_summary_json="$data_run_dir/.${run_tag}_cross_section_summary.$$.$RANDOM.tmp.json"
particle_pid="$(particle_pid_for "$particle")"

for input in "$g4psi_root" "$hazard_truth_root" "$cross_section_root"; do
  require_file "$input"
done

cleanup() {
  rm -f "$tmp_events_csv" "$tmp_summary_json"
}
trap cleanup EXIT

STACK_PYTHON_TIMEOUT="${EXPORT_CS_EVENTS_TIMEOUT:-0}" \
  run_stack_python "$repo_root/src/python/export_cross_section_events.py" \
    --cross-section-root "$cross_section_root" \
    --hazard-truth-root "$hazard_truth_root" \
    --g4psi-root "$g4psi_root" \
    --events-csv "$tmp_events_csv" \
    --summary-json "$tmp_summary_json" \
    --reported-events-csv "$events_csv" \
    --reported-summary-json "$summary_json" \
    --run-tag "$run_tag" \
    --particle "$particle" \
    --particle-pid "$particle_pid"

[[ -f "$tmp_events_csv" ]] || die "missing cross-section events CSV: $tmp_events_csv"
[[ -s "$tmp_summary_json" ]] || die "missing cross-section summary JSON: $tmp_summary_json"

mv -f "$tmp_events_csv" "$events_csv"
mv -f "$tmp_summary_json" "$summary_json"
trap - EXIT
