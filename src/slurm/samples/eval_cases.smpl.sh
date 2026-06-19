stage="${1:-}"
[[ -n "$stage" ]] || usage
[[ $# -le 2 ]] || usage

case "$stage" in
  hazard_truth) script="run_hazard_truth.sh" ;;
  chamber_veto) script="run_chamber_veto.sh" ;;
  mmt) script="run-mc2root.sh" ;;
  bh) script="run_bh.sh" ;;
  bm) script="run_bm.sh" ;;
  sps) script="run_sps.sh" ;;
  stt) script="run_stt.sh" ;;
  tcpv) script="run_tcpv.sh" ;;
  veto) script="run_veto.sh" ;;
  gem_hits) script="run_gem_hits.sh" ;;
  gem_tracks) script="run_gem_tracks.sh" ;;
  tracked) script="run_tracklets.sh" ;;
  vertex) script="run_vertex.sh" ;;
  pathlength) script="run_path_length.sh" ;;
  pbglass) script="run_pbglass.sh" ;;
  cross_section) script="run_cs.sh" ;;
  accepted_events) script="run_accepted_events.sh" ;;
  hazard_cutflow) script="run_hazard_cutflow.sh" ;;
  hazard_tables) script="run_hazard_tables.sh" ;;
  *)
    echo "Unknown relay stage: $stage" >&2
    usage
    ;;
esac