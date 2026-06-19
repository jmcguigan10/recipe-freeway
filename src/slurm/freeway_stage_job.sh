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
Usage: $(basename "$0") <stage-item> <pipeline-tag>

Runs one numbered freeway stage, then reruns the Slurm freeway orchestrator.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if (($# != 2)); then
  usage >&2
  exit 2
fi

item="$1"
pipeline_tag_arg="$2"

select_pipeline "$pipeline_tag_arg"
resolve_data_run_dir

[[ "$item" =~ ^[0-9][0-9]$ ]] || die "stage item must be two digits: $item"
stage="$(freeway_stage_by_index "$((10#$item))")" || die "unknown freeway stage item: $item"
freeway_script="${FREEWAY_STAGE_SCRIPT[$stage]:-}"
[[ -n "$freeway_script" ]] || die "no script configured for freeway stage: $stage"

stage_script="$repo_root/src/shell/freeway/$freeway_script"
[[ -f "$stage_script" ]] || die "required freeway script not found: $stage_script"

printf 'Freeway job: %s %s\n' "$item" "$stage"
printf 'Pipeline tag: %s\n' "$pipeline_tag"
printf 'Data run dir: %s\n\n' "$data_run_dir"

rc=0
bash "$stage_script" "$pipeline_tag" || rc=$?

printf '\nRerunning freeway orchestrator...\n'
bash "$repo_root/src/slurm/run_freeway.sh" "$pipeline_tag" || true

exit "$rc"
