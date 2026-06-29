FREEWAY_STAGE_ORDER=(
  g4psi
  hazard_truth
  mc2root
  bh
  sps
  bm
  veto
  tcpv
  stt
  gem_hits
  gem_tracks
  tracklets
  vertex
  pathlength
  pbglass
  cross_section
  export_cs_events
  hazard_cutflow
  export_training_table
)

declare -gA FREEWAY_STAGE_KIND=(
  [g4psi]="g4psi"
  [hazard_truth]="helper"
  [mc2root]="cooker"
  [bh]="cooker"
  [sps]="cooker"
  [bm]="cooker"
  [veto]="cooker"
  [tcpv]="cooker"
  [stt]="cooker"
  [gem_hits]="cooker"
  [gem_tracks]="cooker"
  [tracklets]="cooker"
  [vertex]="cooker"
  [pathlength]="cooker"
  [pbglass]="cooker"
  [cross_section]="cooker"
  [export_cs_events]="helper"
  [hazard_cutflow]="helper"
  [export_training_table]="helper"
)

declare -gA FREEWAY_STAGE_SCRIPT=(
  [g4psi]="00_run_g4psi.sh"
  [hazard_truth]="01_run_hazard_truth.sh"
  [mc2root]="02_run_mc2root.sh"
  [bh]="03_run_bh.sh"
  [sps]="04_run_sps.sh"
  [bm]="05_run_bm.sh"
  [veto]="06_run_veto.sh"
  [tcpv]="07_run_tcpv.sh"
  [stt]="08_run_stt.sh"
  [gem_hits]="09_run_gem_hits.sh"
  [gem_tracks]="10_run_gem_tracks.sh"
  [tracklets]="11_run_tracklets.sh"
  [vertex]="12_run_vertex.sh"
  [pathlength]="13_run_path_length.sh"
  [pbglass]="14_run_pbglass.sh"
  [cross_section]="15_run_cs.sh"
  [export_cs_events]="16_run_export_cs_events.sh"
  [hazard_cutflow]="17_run_hazard_cutflow.sh"
  [export_training_table]="18_run_export_training_table.sh"
)

declare -gA FREEWAY_STAGE_OUTPUT=(
  [g4psi]="g4psi"
  [hazard_truth]="hazard_truth"
  [mc2root]="mmt"
  [bh]="bh"
  [sps]="sps"
  [bm]="bm"
  [veto]="veto"
  [tcpv]="tcpv"
  [stt]="stt"
  [gem_hits]="gem_hits"
  [gem_tracks]="gem_tracks"
  [tracklets]="tracked"
  [vertex]="vertex"
  [pathlength]="pathlength"
  [pbglass]="pbglass"
  [cross_section]="cross_section"
  [export_cs_events]="cross_section_events"
  [hazard_cutflow]="hazard_cutflow"
  [export_training_table]="training_candidates"
)

declare -gA FREEWAY_STAGE_OUTPUT_EXT=(
  [export_cs_events]="csv"
  [export_training_table]="parquet"
)

declare -gA FREEWAY_STAGE_TREE=(
  [g4psi]="T"
  [hazard_truth]="hazard_truth"
  [mc2root]="MMT"
  [bh]="BH"
  [sps]="SPS"
  [bm]="BM"
  [veto]="VETO"
  [tcpv]="TCPV"
  [stt]="STT"
  [gem_hits]="GEM"
  [gem_tracks]="GEMTracks"
  [tracklets]="Tracked"
  [vertex]="Vertex"
  [pathlength]="PathLength"
  [pbglass]="PbGlass"
  [cross_section]="cs"
  [hazard_cutflow]="hazard_cutflow"
)

declare -gA FREEWAY_STAGE_RECIPE=(
  [mc2root]="muse:recipes/mc2root/mcconverter.xml"
  [bh]="muse:recipes/BH/BH_detail_with_tree.xml"
  [sps]="muse:recipes/SPS/SPS_monitor_with_tree.xml"
  [bm]="muse:recipes/BM/BM_detail_with_tree.xml"
  [veto]="muse:recipes/VETO/VETO_monitor_with_tree.xml"
  #[tcpv]="muse:recipes/TCPV/TCPV_calib.xml"
  [tcpv]="muse:recipes/TCPV/TCPV_monitor_with_tree.xml"
  [stt]="muse:recipes/STT/STT.xml"
  [gem_hits]="muse:recipes/GEMini/gemini.xml"
  [gem_tracks]="muse:recipes/tracking/GEM_cmin.xml"
  [tracklets]="muse:recipes/tracking/Tracklet_Driver_cmin.xml"
  [vertex]="muse:recipes/tracking/Vertex_sim.xml"
  [pathlength]="muse:recipes/tracking/PathLength_sim.xml"
  [pbglass]="muse:recipes/PbGlass/PBG_detail.xml"
  [cross_section]="muse:recipes/analysis/cs_sim_pbg.xml"
)

declare -gA FREEWAY_STAGE_INPUTS=(
  [hazard_truth]="g4psi"
  [mc2root]="g4psi"
  [bh]="mc2root"
  [sps]="mc2root"
  [bm]="mc2root"
  [veto]="mc2root"
  [tcpv]="mc2root"
  [stt]="mc2root"
  [gem_hits]="mc2root"
  [gem_tracks]="gem_hits bh"
  [tracklets]="bh stt sps"
  [vertex]="tracklets bh sps gem_tracks veto"
  [pathlength]="bh gem_tracks tracklets sps vertex"
  [pbglass]="mc2root bh bm veto"
  [cross_section]="pathlength mc2root bh bm sps pbglass gem_tracks veto tcpv"
  [export_cs_events]="cross_section hazard_truth g4psi"
  [hazard_cutflow]="hazard_truth export_cs_events"
  [export_training_table]="hazard_truth export_cs_events"
)

declare -gA FREEWAY_STAGE_INIT=(
  [mc2root]="muse:init/all.xml"
  [bh]="env:MUSE_INIT:muse:init/all.xml"
  [sps]="env:MUSE_INIT:muse:init/all.xml"
  [bm]="env:MUSE_INIT:muse:init/all.xml"
  [veto]="env:MUSE_INIT:muse:init/all.xml"
  [tcpv]="env:MUSE_INIT:muse:init/all.xml"
  [stt]="env:MUSE_INIT:muse:init/all.xml"
  [gem_hits]="muse:init/all.xml"
)

declare -gA FREEWAY_STAGE_COOKER_CALLS=(
  [bh]="BH:setMomentum:@BEAM_MOMENTUM@"
  [tracklets]="cryptor:setMomentum:@BEAM_MOMENTUM@"
  [vertex]="VertexRecon:setMomentum:@BEAM_MOMENTUM@"
  [pathlength]="PathLength:setMomentum:@BEAM_MOMENTUM@"
  [cross_section]="cs:setMomentum:@BEAM_MOMENTUM@"
)

declare -gA FREEWAY_STAGE_REPORT_PAYLOAD=(
  [bm]="BM BM_Hits hits"
  [veto]="VETO VETO_Hits hits"
)
