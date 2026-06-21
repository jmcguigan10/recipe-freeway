cd /home/mcguigj/proj-dir/recipe-freeway/packman-muse
TAG=mc22308_rad2_e_pos_part0

<<<<<<< Updated upstream
./scripts/pixi-local run -e batch bash ../src/shell/freeway/00_run_g4psi.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/01_run_mc2root.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/02_run_bh.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/03_run_sps.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/04_run_bm.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/05_run_veto.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/06_run_tcpv.sh "$TAG"
=======
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/00_run_g4psi.sh "$TAG"
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/01_run_mc2root.sh "$TAG"
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/02_run_bh.sh "$TAG"
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/03_run_sps.sh "$TAG"
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/04_run_bm.sh "$TAG"
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/05_run_veto.sh "$TAG"
#./scripts/pixi-local run -e batch bash ../src/shell/freeway/06_run_tcpv.sh "$TAG"
>>>>>>> Stashed changes
./scripts/pixi-local run -e batch bash ../src/shell/freeway/07_run_stt.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/08_run_gem_hits.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/09_run_gem_tracks.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/10_run_tracklets.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/11_run_vertex.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/12_run_path_length.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/13_run_pbglass.sh "$TAG"
./scripts/pixi-local run -e batch bash ../src/shell/freeway/14_run_cs.sh "$TAG"
