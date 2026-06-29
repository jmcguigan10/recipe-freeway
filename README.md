# Recipe Freeway

`recipe-freeway` is a lightweight orchestration layer around a local
`packman-muse` build. It generates a g4PSI ROOT file and then runs the MUSE
cooker recipes in dependency order through Slurm.

This repository does not vendor or build MUSE. The ROOT, Geant4, g4PSI, MUSE,
cooker, and Pixi runtime all come from a sibling or nested `packman-muse`
checkout.

## Repository Layout

Expected checkout shape:

```text
recipe-freeway/
  configs/                 pipeline defaults
  data_process/            per-run outputs and copied config snapshots
  macros/generated/        generated g4PSI macros
  packman-muse/            default local stack checkout
  src/freeway/python/              ROOT validation and payload-count helpers
  src/freeway/ruby/                g4PSI macro renderer
  src/freeway/shell/               stage runners and shared shell library
  src/ml/python/                   PyTorch ML models and datasets
  src/slurm/               Slurm freeway orchestrator
  templates/g4psi/         g4PSI macro template
  test_run.sh              manual sequential smoke runner
```

Default paths are:

```text
STACK_DIR    = ./packman-muse
MUSE_SRC_DIR = ./packman-muse/.install/src/muse
DATA_ROOT    = ./data_process
```

Override those with environment variables when the stack or output directory
lives somewhere else.

## Install

From a fresh clone:

```bash
git clone git@github.com:jmcguigan10/recipe-freeway.git
cd recipe-freeway

git clone git@github.com:jmcguigan10/packman-muse.git packman-muse

cd packman-muse
bash scripts/bootstrap-pixi.sh
./scripts/pixi-local install
./scripts/pixi-local run -e batch build-stack
cd ..
```

Use `packman-muse/scripts/pixi-local`, not a global Pixi, for commands that need
ROOT, g4PSI, MUSE, or the cooker. The wrapper pins the runtime to the local
`packman-muse` stack.

The shell pipeline requires Bash 4.2+ because it uses associative arrays. On a
system where `/bin/bash` is too old, either run commands through
`packman-muse/scripts/pixi-local run -e batch bash ...` or put a newer Bash
earlier on `PATH`.

Quick sanity checks after install:

```bash
cd packman-muse
./scripts/pixi-local run -e batch bash -lc 'command -v g4PSI && command -v cooker && command -v hadd'
./scripts/pixi-local run -e batch ruby ../src/freeway/ruby/render_macro.rb --help
```

## Moving to Another Cluster

The pipeline has no cluster-specific code outside configuration, but a new
cluster usually needs these changes:

1. Edit `configs/slurm/slurm.sh`.
   - Set `PARTITION`, and add `ACCOUNT` or `QOS` keys if your cluster requires
     them.
   - `MEM` is passed directly to `sbatch --mem`; use the syntax your cluster
     expects. Isaac should use values like `16G`, while other clusters may
     prefer bare values like `16`.
   - `SLURM_SIM_CONFIG` is used for stage 00 g4PSI.
   - `SLURM_RECIPE_CONFIG` is used for cooker stages 01-14.
2. Put output on cluster storage if needed:

   ```bash
   export DATA_ROOT=/path/to/scratch-or-project/data_process
   ```

3. If `packman-muse` is not nested in this checkout, point to it:

   ```bash
   export STACK_DIR=/path/to/packman-muse
   export MUSE_SRC_DIR="$STACK_DIR/.install/src/muse"
   ```

4. Submit with the normal orchestrator:

   ```bash
   bash src/slurm/run_freeway.sh <pipeline-tag>
   ```

The Slurm wrappers export `REAL_MUSE_REPO_ROOT`, `PIPELINE_TAG`, and
`DATA_RUN_DIR` into jobs so job scripts can find this checkout and the selected
run directory.

For testing the submission layer without a real Slurm scheduler, set
`FREEWAY_SBATCH_BIN` to a fake `sbatch` executable.

## Configuration

Pipeline and training defaults live under `configs/freeway/`, `configs/slurm/`,
and `configs/ml/`:

```text
configs/freeway/physics.sh   run number, particle, momentum, event count, seeds, RadGen, T0
configs/freeway/g4psi.sh     g4PSI macro template and generated macro directory
configs/freeway/recipes.sh   stage graph, recipes, inputs, outputs, trees, cooker calls
configs/slurm/slurm.sh       Slurm resources for simulation and recipe stages
configs/ml/*.yaml            modular ML training defaults
```

ML training loads `configs/ml/default.yaml` by default. That file includes the
modular YAML files in `configs/ml/`; command-line options override loaded YAML
values:

```bash
python3 src/ml/python/training/training_loop.py \
  --config configs/ml/default.yaml \
  --train-csv data_process/<tag>/<tag>_gem_classifier.csv
```

Important `configs/freeway/physics.sh` keys:

```text
RUN_NR          MUSE run number passed into the generated macro
RAD_MODE        g4PSI radiative mode, passed as --rad2, --rad3, etc.
STORE_T0        truthy value passes --T0 and requires tree T0 in g4PSI outputs
PARTICLE        Geant4 beam particle, such as e+ or e-
PARTICLE_TAG    filename-safe particle tag
PART            part index embedded in generated names
BEAM_MOMENTUM   beam momentum in MeV
N_EVENTS        total g4PSI events for stage 00
SEED_1/SEED_2   base random seeds; chunk seeds are offset deterministically
```

`STORE_T0=true` writes the additional g4PSI `T0` tree with thrown-beam metadata.
The code intentionally passes `--T0`; `-T0` is not a valid g4PSI flag.

Important `configs/freeway/recipes.sh` behavior:

- `FREEWAY_STAGE_ORDER` defines stages 00-18.
- `FREEWAY_STAGE_INPUTS` controls dependencies.
- `FREEWAY_STAGE_TREE` is the expected output tree for validation.
- `FREEWAY_STAGE_OUTPUT_EXT` marks helper stages whose primary output is not ROOT.
- `FREEWAY_STAGE_COOKER_CALLS` adds required plugin calls.

The BH momentum call is required for the current simulated positron workflow:

```bash
[bh]="BH:setMomentum:@BEAM_MOMENTUM@"
```

Without it, the BH plugin can fall back to missing slow-control momentum; BHD
PID can stay zero, vertexing can go empty, and cross-section output can be zero.

## Run-Directory Snapshots

Each pipeline tag gets a run directory:

```text
data_process/<pipeline-tag>/
```

When a run directory is created or resolved, the pipeline snapshots the current
freeway configs into:

```text
data_process/<pipeline-tag>/configs/freeway/
```

Existing snapshot files win over current repo defaults; snapshots are not
overwritten. Old flat snapshots under `data_process/<tag>/configs/*.sh` are
still read for compatibility. If you change a freeway config after a run exists,
either edit the snapshot directly or remove the stale snapshot:

```bash
rm data_process/<tag>/configs/freeway/physics.sh
rm -f data_process/<tag>/configs/physics.sh  # old flat snapshot layout only
bash src/slurm/run_freeway.sh <tag>
```

For clean comparisons, prefer a new pipeline tag.

## Pipeline Tags and Outputs

Pipeline tags are names, not paths. They must not contain `/`.

Example:

```bash
mc22308_rad2_e_pos_part0
```

Stage outputs are written under the selected run directory. Cooker stages use
ROOT outputs:

```text
data_process/<tag>/<tag>_<stage-output>.root
```

Helper export stages may use `.csv`, `.json`, or `.parquet` outputs.

Example:

```text
data_process/mc22308_rad2_e_pos_part0/
  mc22308_rad2_e_pos_part0_g4psi.root
  mc22308_rad2_e_pos_part0_hazard_truth.root
  mc22308_rad2_e_pos_part0_mmt.root
  mc22308_rad2_e_pos_part0_bh.root
  mc22308_rad2_e_pos_part0_vertex.root
  mc22308_rad2_e_pos_part0_cross_section.root
  mc22308_rad2_e_pos_part0_cross_section_events.csv
  mc22308_rad2_e_pos_part0_hazard_cutflow.root
  mc22308_rad2_e_pos_part0_training_candidates.parquet
```

Keep the tag consistent with `configs/freeway/physics.sh`; scripts do not derive the tag
from physics config values.

## Freeway Stages

The stage graph is defined in `configs/freeway/recipes.sh`.

| Item | Stage | Output | Tree/Data | Inputs |
| --- | --- | --- | --- | --- |
| 00 | `g4psi` | `g4psi.root` | `T` plus optional `T0` | none |
| 01 | `hazard_truth` | `hazard_truth.root` | `hazard_truth` | `g4psi` |
| 02 | `mc2root` | `mmt.root` | `MMT` | `g4psi` |
| 03 | `bh` | `bh.root` | `BH` | `mc2root` |
| 04 | `sps` | `sps.root` | `SPS` | `mc2root` |
| 05 | `bm` | `bm.root` | `BM` | `mc2root` |
| 06 | `veto` | `veto.root` | `VETO` | `mc2root` |
| 07 | `tcpv` | `tcpv.root` | `TCPV` | `mc2root` |
| 08 | `stt` | `stt.root` | `STT` | `mc2root` |
| 09 | `gem_hits` | `gem_hits.root` | `GEM` | `mc2root` |
| 10 | `gem_tracks` | `gem_tracks.root` | `GEMTracks` | `gem_hits`, `bh` |
| 11 | `tracklets` | `tracked.root` | `Tracked` | `bh`, `stt`, `sps` |
| 12 | `vertex` | `vertex.root` | `Vertex` | `tracklets`, `bh`, `sps`, `gem_tracks`, `veto` |
| 13 | `pathlength` | `pathlength.root` | `PathLength` | `bh`, `gem_tracks`, `tracklets`, `sps`, `vertex` |
| 14 | `pbglass` | `pbglass.root` | `PbGlass` | `mc2root`, `bh`, `bm`, `veto` |
| 15 | `cross_section` | `cross_section.root` | `cs` | `pathlength`, `mc2root`, `bh`, `bm`, `sps`, `pbglass`, `gem_tracks`, `veto`, `tcpv` |
| 16 | `export_cs_events` | `cross_section_events.csv` | accepted survivor rows | `cross_section`, `hazard_truth`, `g4psi` |
| 17 | `hazard_cutflow` | `hazard_cutflow.root` | `hazard_cutflow` | `hazard_truth`, `export_cs_events` |
| 18 | `export_training_table` | `training_candidates.parquet` | CSV/Parquet training tables | `hazard_truth`, `hazard_cutflow`, `export_cs_events` |

### ML Export Tables

`hazard_truth` is the denominator table. It reads `{tag}_g4psi.root` tree `T`
and writes one row per g4PSI target-scatter candidate in `TGT_*` arrays:

```text
candidate_id, run_tag, event_number, event_index, target_index, event_weight,
particle, particle_pid, momentum_mev, theta_deg, theta_bin,
vertex_x_mm, vertex_y_mm, vertex_z_mm, truth_track_id, side,
pass_truth, pass_sps_side_truth_hint
```

`candidate_id` is built as:

```text
run_tag:event_number:target_index:side:particle_pid
```

`event_weight` comes from `EventInfo.weight`, `theta_deg` comes from
`TGT_Theta[target_index]`, and `pass_truth` currently means the truth candidate
PID matches the configured `PARTICLE`.

`hazard_cutflow` is the long-form survival table. It writes one row per
candidate per stage:

```text
truth, sps_side, no_veto, bh_pid, lut5, gem_track, tracklet, vertex,
tof, not_decay_or_rid, calo, doca, final_accept
```

Each row carries candidate identity plus:

```text
stage_order, stage_name, at_risk, passed, terminated, fail_reason,
accepted_final, label_status
```

The exporter assigns exact final labels when `CSAcceptedEvents` rows can be
joined back to unique truth candidates, or when the final accepted count is
zero. Intermediate detector/reconstruction stages are marked `not_evaluated`
for non-accepted candidates until stage-specific object matching is added; the
exporter does not fabricate a detector failure label when the ROOT products do
not identify one unambiguously.

## Running on Slurm

Use the dependency-aware freeway orchestrator for normal cluster work:

```bash
bash src/slurm/run_freeway.sh <pipeline-tag>
```

It creates `data_process/<tag>/`, snapshots configs, checks which stage outputs
already exist, and submits every ready stage with `sbatch`.

Under Slurm, stage 00 g4PSI uses `SLURM_SIM_CONFIG` and runs one worker per
selected task. It splits `N_EVENTS` across those workers, writes per-worker logs
under `data_process/<tag>/g4psi_chunks/`, merges chunk ROOT files into the
normal `*_g4psi.root`, then deletes successful chunk ROOT files. Chunk logs are
kept. Direct non-Slurm runs default to one g4PSI worker unless
`G4PSI_PARALLEL_TASKS` is set explicitly.

Cooker stages use `SLURM_RECIPE_CONFIG` and intentionally run serially inside
each stage job, producing one ROOT output per stage. Independent stages still
fan out as separate Slurm jobs when their dependencies are ready.

Stage logs go to:

```text
data_process/<tag>/slurm/
```

Submitted stages are recorded in:

```text
data_process/<tag>/is_submitted.txt
```

Submit one numbered stage explicitly:

```bash
bash src/slurm/submit_freeway.sh 02 <pipeline-tag>
```

That is useful for targeted reruns, but the orchestrator is safer for normal
dependency handling.

## Rerunning Existing Data

The orchestrator treats an existing non-empty stage ROOT file as complete. To
rerun a stage in place:

1. Remove that stage output.
2. Remove downstream outputs that should be regenerated.
3. Remove stale submitted lines from `data_process/<tag>/is_submitted.txt`.
4. Refresh config snapshots if needed.
5. Rerun `bash src/slurm/run_freeway.sh <tag>`.

If stale submitted lines remain, the orchestrator may report a stage as waiting
for an already submitted job instead of resubmitting it.

## Manual and Local Runs

Individual stage scripts live in `src/freeway/shell/freeway/`. They can be run directly
when required inputs already exist:

```bash
bash src/freeway/shell/freeway/12_run_vertex.sh <pipeline-tag>
```

When running on a system with the `packman-muse` Pixi stack, prefer:

```bash
cd packman-muse
./scripts/pixi-local run -e batch bash ../src/freeway/shell/freeway/12_run_vertex.sh <pipeline-tag>
```

`test_run.sh` is a manual serial smoke runner for small sanity-check runs after
installing the stack. It does not submit Slurm jobs and forces stage 00 g4PSI to
one worker.

```bash
bash test_run.sh <pipeline-tag>

START_STAGE=7 END_STAGE=18 bash test_run.sh <pipeline-tag>
STACK_DIR=/path/to/packman-muse bash test_run.sh <pipeline-tag>
```

`START_STAGE` and `END_STAGE` are zero-based freeway item numbers. Defaults are
`0` and `18`. The script runs through `STACK_DIR/scripts/pixi-local`.
Use the Slurm orchestrator, not `test_run.sh`, for parallel production runs.

## Useful Checks

Check run status:

```bash
cat data_process/<tag>/is_submitted.txt
ls -lh data_process/<tag>/*.{root,csv,json,parquet}
ls -lh data_process/<tag>/slurm/
```

Validate a ROOT file has an expected tree:

```bash
cd packman-muse
./scripts/pixi-local run -e batch python \
  ../src/freeway/python/validate_root_file.py \
  ../data_process/<tag>/<tag>_g4psi.root T
```

Count payloads:

```bash
cd packman-muse
./scripts/pixi-local run -e batch python \
  ../src/freeway/python/count_root_payload.py \
  ../data_process/<tag>/<tag>_cross_section.root \
  cs CSAcceptedEvents events
```

Healthy recovery signs for the current positron workflow include:

```text
BH log contains: BH - setMomentum - 159.279
BH PID histogram title contains: p = 159.28 MeV/c
Vertex.eVertices.vertex is nonzero
PathLength.eScattering.vertex is nonzero
cs.CSAcceptedEvents.events is nonzero
```

If `BH` has BHC electron PID but BHD PID is all zero, the BH momentum command
was probably not applied to the run that produced that `bh.root`.

## Environment Variables

```text
STACK_DIR              override the packman-muse checkout
MUSE_SRC_DIR           override the MUSE source tree
DATA_ROOT              override the root output directory
DATA_RUN_DIR           exported by Slurm jobs; must match the selected tag
PIPELINE_TAG           selected run tag
REAL_MUSE_REPO_ROOT    exported by Slurm jobs so they can find this checkout
MUSE_INIT              optional override for cooker init XML
MUSE_PIPELINE_TMPDIR   temp directory for cooker and ROOT validation files
G4PSI_PARALLEL_TASKS   opt-in override for direct stage-00 g4PSI worker count
G4PSI_ENABLE_SRUN      truthy enables nested srun launcher inside g4PSI jobs
G4PSI_STATUS_INTERVAL  seconds between g4PSI chunk status updates
G4PSI_STATUS_PLAIN     truthy disables TTY cursor status updates
FREEWAY_SBATCH_BIN     override sbatch for testing
```

## CI

Pull requests run lightweight checks that do not download `packman-muse` and do
not require ROOT, MUSE, Geant4, or Slurm:

- merge-conflict marker detection
- Bash syntax checks for standalone scripts/configs
- Python and Ruby syntax checks
- stage graph/config consistency checks
- Slurm orchestrator dry-run with a fake `sbatch`

These checks protect repository structure and orchestration logic. They do not
prove physics correctness or cooker/g4PSI runtime behavior; that still requires
the external `packman-muse` stack and real ROOT outputs.
