#!/usr/bin/env bash
set -Eeuo pipefail

cat <<'HELP'
MUSE pipeline command help

Simulation and freeway runs
  Dependency-aware Slurm/freeway orchestrator:
    bash src/slurm/run_freeway.sh <pipeline-tag>

  Submit one numbered freeway stage:
    bash src/slurm/submit_freeway.sh <freeway-number> <pipeline-tag>

  Run one stage directly:
    bash src/freeway/shell/freeway/<NN>_run_<stage>.sh <pipeline-tag>

  Run a local sequential smoke pass:
    bash test_run.sh <pipeline-tag>

Simulation examples
  bash src/slurm/run_freeway.sh mc22308_gem_classifier_e_pos_part0
  bash src/slurm/submit_freeway.sh 00 mc22308_gem_classifier_e_pos_part0
  bash src/freeway/shell/freeway/00_run_g4psi.sh mc22308_gem_classifier_e_pos_part0
  START_STAGE=0 END_STAGE=0 bash test_run.sh mc22308_gem_classifier_e_pos_part0

Freeway stage numbers
  00  g4psi                  -> *_g4psi.root, *_gem_classifier.csv
  01  hazard_truth           -> *_hazard_truth.root
  02  mc2root                -> *_mmt.root
  03  bh                     -> *_bh.root
  04  sps                    -> *_sps.root
  05  bm                     -> *_bm.root
  06  veto                   -> *_veto.root
  07  tcpv                   -> *_tcpv.root
  08  stt                    -> *_stt.root
  09  gem_hits               -> *_gem_hits.root
  10  gem_tracks             -> *_gem_tracks.root
  11  tracklets              -> *_tracked.root
  12  vertex                 -> *_vertex.root
  13  pathlength             -> *_pathlength.root
  14  pbglass                -> *_pbglass.root
  15  cross_section          -> *_cross_section.root
  16  export_cs_events       -> *_cross_section_events.csv
  17  hazard_cutflow         -> *_hazard_cutflow.root
  18  export_training_table  -> *_training_candidates.parquet

Simulation environment knobs
  DATA_ROOT=/path/to/data_process
      Override run output root. Default: ./data_process

  STACK_DIR=/path/to/packman-muse
      Override stack checkout. Default: ./packman-muse

  MUSE_SRC_DIR=/path/to/muse
      Override MUSE source tree. Default: $STACK_DIR/.install/src/muse

  SLURM_CLUSTER=isaac|theia
      Select configured Slurm account/partition/qos. Default: isaac

  FREEWAY_SBATCH_BIN=/path/to/sbatch
      Override sbatch executable for dry-runs or wrappers.

  G4PSI_PARALLEL_TASKS=<n>
      Override direct g4PSI worker count. Slurm defaults use SLURM_NTASKS.

  G4PSI_ENABLE_SRUN=1
      Enable nested srun launcher inside g4PSI jobs.

  G4PSI_STATUS_INTERVAL=<seconds>
      Status refresh interval for parallel g4PSI chunks. Default: 5

  G4PSI_STATUS_PLAIN=1
      Disable TTY cursor status updates.

Local smoke run environment knobs
  START_STAGE=<n>
      First zero-based stage for test_run.sh. Default: 0

  END_STAGE=<n>
      Last zero-based stage for test_run.sh. Default: 18

GEM classifier table export
  The g4PSI simulation stage writes this CSV automatically when enabled:
    data_process/<tag>/<tag>_gem_classifier.csv

  Export controls live in configs/freeway/g4psi.sh:
    G4PSI_CONFIG[gem_classifier_export]=1
    G4PSI_CONFIG[gem_classifier_exporter]=repo:src/freeway/python/gem_classifier/export_gem_classifier_table.py
    G4PSI_CONFIG[gem_classifier_output]=gem_classifier
    G4PSI_CONFIG[gem_classifier_tree]=T

  Re-export classifier rows manually from an existing g4PSI ROOT file:
    python3 src/freeway/python/gem_classifier/export_gem_classifier_table.py \
      --input-root <g4psi.root> \
      --output-csv <table.csv> \
      [--tree T] \
      [--run-tag <tag>]

ML training
  Direct script:
    python3 src/ml/python/training/training_loop.py --train-csv <table.csv> [options]

  Module form:
    python3 -m src.ml.python.training.training_loop --train-csv <table.csv> [options]

  Default ML config:
    configs/ml/default.yaml

ML training required option
  --train-csv PATH
      Training CSV from the GEM classifier table exporter.

ML training options
  --config PATH
      YAML config file. Default: configs/ml/default.yaml. CLI values override
      values loaded from YAML.

  --output-dir PATH
      Artifact directory. Default: artifacts/gem_classifier

  --val-csv PATH
      Optional validation CSV. If omitted, split --train-csv.

  --val-fraction FLOAT
      Validation split fraction when --val-csv is omitted. Default: 0.2

  --calibration-fraction FLOAT
      Optional third split used for post-hoc calibration and final plots.

  --split-strategy random|event-hash
      Split rows randomly or by deterministic hash of --split-column.

  --split-column NAME
      Column used by event-hash splitting. Default: event_index.

  --epochs N
      Number of training epochs. Default: 20

  --batch-size N
      Mini-batch size. Default: 1024

  --lr FLOAT
      AdamW learning rate. Default: 1e-3

  --weight-decay FLOAT
      AdamW weight decay. Default: 0.0

  --hidden-dims LIST
      Comma-separated MLP hidden dimensions. Default: 64,64

  --dropout FLOAT
      Dropout probability. Default: 0.1

  --seed N
      Reproducibility seed for split/shuffle/torch. Default: 1337

  --num-workers N
      DataLoader workers. Default: 0

  --device DEVICE
      Device override. By default CUDA is required. Use --device cpu only for
      debug runs on non-CUDA machines.

  --threshold FLOAT
      Sigmoid threshold for validation metrics. Default: 0.5

  --pos-weight auto|none|w1,w2,...
      BCEWithLogits positive weights. Default: auto

  --pos-weight-max FLOAT
      Optional cap applied to auto positive weights.

  --checkpoint-metric NAME
      Metric column used for best.pt and early stopping. Default: val_loss.
      For rare labels prefer val_macro_auroc.

  --checkpoint-mode min|max
      Whether lower or higher checkpoint metric is better. Default: min.

  --early-stopping-patience N
      Stop after N epochs without checkpoint metric improvement. 0 disables it.

  --calibrate-pos-weight-logits / --no-calibrate-pos-weight-logits
      For probability metrics and plots, subtract log(pos_weight) from logits
      trained with weighted BCE. Enabled by default.

  --save-plots / --no-save-plots
      Save plot artifacts under <output-dir>/plots at the end of training.
      Enabled by default.

  --plot-validation-predictions / --no-plot-validation-predictions
      Save a sampled validation logits/probabilities/targets CSV for the best checkpoint.
      Enabled by default.

  --save-full-validation-predictions / --no-save-full-validation-predictions
      Save the full validation prediction CSV. Disabled by default because it can be large.

  --prediction-sample-size N
      Maximum sampled prediction rows to save, keeping all positives first. Default: 250000.

  --edge-band-mm FLOAT
      Geometry edge band width used in regime diagnostics. Default: 5.

  --near-band-mm FLOAT
      Geometry near band upper edge used in regime diagnostics. Default: 20.

  --plot-bins N
      Number of bins for calibration and rate plots. Default: 20

  --feature-columns LIST
      Comma-separated or YAML-list input columns. Supports derived geometry
      features such as x_at_gem0_mm and gem0_edge_margin_mm.

  --target-columns LIST
      Comma-separated or YAML-list binary targets. Supports derived miss labels
      such as miss_gem0_primary.

  --geometry-config PATH
      YAML detector geometry constants required by derived geometry features.

ML training artifacts
  best.pt
  latest.pt
  metrics.csv
  config.json
  calibration.json
  summary_tables/per_label_metrics.csv
  summary_tables/regime_metrics.csv
  summary_tables/topk_lift.csv
  summary_tables/calibration_bins.csv
  plots/index.json
  plots/loss_curves.png
  plots/roc_curves.png
  plots/pr_curves.png
  plots/calibration_curves.png
  plots/predicted_vs_observed_bins.png
  plots/edge_margin_rate_curves.png
  plots/xy_acceptance_heatmaps.png
  plots/validation_predictions.csv

ML training examples
  python3 src/ml/python/training/training_loop.py \
    --train-csv data_process/<tag>/<tag>_gem_classifier.csv \
    --output-dir data_process/<tag>/ml/gem_classifier \
    --epochs 50 \
    --batch-size 4096

  python3 src/ml/python/training/training_loop.py \
    --train-csv /tmp/gem_classifier.csv \
    --output-dir /tmp/gem_classifier_debug \
    --epochs 2 \
    --batch-size 32 \
    --device cpu

  python3 src/ml/python/training/training_loop.py \
    --config configs/ml/discrete_pre_detector.yaml \
    --geometry-config configs/ml/geometry.yaml \
    --train-csv data_process/<tag>/<tag>_gem_classifier.csv \
    --output-dir data_process/<tag>/ml/discrete_pre_detector

  python3 src/ml/python/training/training_loop.py \
    --config configs/ml/primary_miss_pre_detector.yaml \
    --train-csv data_process/<tag>/<tag>_gem_classifier.csv \
    --output-dir data_process/<tag>/ml/primary_miss_pre_detector

  python3 -m src.ml.python.data.enrich_gem_classifier \
    --input-csv data_process/<tag>/<tag>_gem_classifier.csv \
    --geometry-config configs/ml/geometry.yaml \
    --output-parquet data_process/<tag>/ml/<tag>_gem_classifier_enriched.parquet

Related config files
  configs/freeway/physics.sh
      Run number, particle, beam momentum, event count, seeds, and RAD_MODE.

  configs/freeway/g4psi.sh
      g4PSI macro template, renderer, generated macro directory, and GEM
      classifier CSV export controls.

  configs/slurm/slurm.sh
      Slurm account/partition/qos/resources for simulation and recipe stages.

  configs/freeway/recipes.sh
      Freeway stage order, output names, tree names, recipes, and dependencies.

  configs/ml/*.yaml
      Modular ML defaults loaded by --config.
HELP
