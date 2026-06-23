#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

# shellcheck source=../shell/lib/loader.sh
source "$repo_root/src/shell/lib/loader.sh"
# shellcheck source=lib/freeway_state.sh
source "$repo_root/src/slurm/lib/freeway_state.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") <pipeline-tag>

Submits every ready freeway stage for the selected pipeline tag.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if (($# != 1)); then
  usage >&2
  exit 2
fi

select_pipeline "$1"
create_data_run_dir

if ! freeway_acquire_lock; then
  exit 0
fi

submitted_count=0
complete_count=0
waiting_count=0
pending_count=0

printf 'Freeway orchestrator: %s\n' "$pipeline_tag"
printf 'Data run dir:        %s\n\n' "$data_run_dir"

for index in "${!FREEWAY_STAGE_ORDER[@]}"; do
  stage="${FREEWAY_STAGE_ORDER[$index]}"
  item="$(printf '%02d' "$index")"
  output_path="$(stage_output_path "$stage")"

  if freeway_stage_output_exists "$stage"; then
    printf 'complete  %-2s %-22s %s\n' "$item" "$stage" "$output_path"
    complete_count=$((complete_count + 1))
  elif freeway_stage_is_submitted "$item" "$stage"; then
    printf 'waiting   %-2s %-22s submitted, output missing\n' "$item" "$stage"
    waiting_count=$((waiting_count + 1))
  elif freeway_stage_dependencies_ready "$stage"; then
    freeway_submit_stage "$index" "$stage"
    submitted_count=$((submitted_count + 1))
  else
    missing_dependencies="$(freeway_stage_missing_dependencies "$stage")"
    printf 'pending   %-2s %-22s waiting for %s\n' "$item" "$stage" "$missing_dependencies"
    pending_count=$((pending_count + 1))
  fi
done

printf '\nSummary: %s submitted, %s complete, %s waiting, %s pending\n' \
  "$submitted_count" \
  "$complete_count" \
  "$waiting_count" \
  "$pending_count"
