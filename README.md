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
  src/python/              ROOT validation and payload-count helpers
  src/ruby/                g4PSI macro renderer
  src/shell/               stage runners and shared shell library
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
./scripts/pixi-local run -e batch ruby ../src/ruby/render_macro.rb --help
```

## Moving to Another Cluster

The pipeline has no cluster-specific code outside configuration, but a new
cluster usually needs these changes:

1. Edit `configs/slurm.sh`.
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

Pipeline defaults live in `configs/*.sh`:

```text
configs/physics.sh   run number, particle, momentum, event count, seeds, RadGen, T0
configs/g4psi.sh     g4PSI macro template and generated macro directory
configs/slurm.sh     Slurm resources for simulation and recipe stages
configs/recipes.sh   stage graph, recipes, inputs, outputs, trees, cooker calls
```

Important `configs/physics.sh` keys:

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

Important `configs/recipes.sh` behavior:

- `FREEWAY_STAGE_ORDER` defines stages 00-14.
- `FREEWAY_STAGE_INPUTS` controls dependencies.
- `FREEWAY_STAGE_TREE` is the expected output tree for validation.
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
top-level configs into:

```text
data_process/<pipeline-tag>/configs/
```

Existing snapshot files win over top-level `configs/*.sh`; snapshots are not
overwritten. If you change a top-level config after a run exists, either edit the
snapshot directly or remove the stale snapshot:

```bash
rm data_process/<tag>/configs/physics.sh
rm data_process/<tag>/configs/slurm.sh
bash src/slurm/run_freeway.sh <tag>
```

For clean comparisons, prefer a new pipeline tag.

## Pipeline Tags and Outputs

Pipeline tags are names, not paths. They must not contain `/`.

Example:

```bash
mc22308_rad2_e_pos_part0
```

Outputs are written as:

```text
data_process/<tag>/<tag>_<stage-output>.root
```

Example:

```text
data_process/mc22308_rad2_e_pos_part0/
  mc22308_rad2_e_pos_part0_g4psi.root
  mc22308_rad2_e_pos_part0_mmt.root
  mc22308_rad2_e_pos_part0_bh.root
  mc22308_rad2_e_pos_part0_vertex.root
  mc22308_rad2_e_pos_part0_cross_section.root
```

Keep the tag consistent with `configs/physics.sh`; scripts do not derive the tag
from physics config values.

## Freeway Stages

The stage graph is defined in `configs/recipes.sh`.

| Item | Stage | Output suffix | Tree | Inputs |
| --- | --- | --- | --- | --- |
| 00 | `g4psi` | `g4psi` | `T` plus optional `T0` | none |
| 01 | `mc2root` | `mmt` | `MMT` | `g4psi` |
| 02 | `bh` | `bh` | `BH` | `mc2root` |
| 03 | `sps` | `sps` | `SPS` | `mc2root` |
| 04 | `bm` | `bm` | `BM` | `mc2root` |
| 05 | `veto` | `veto` | `VETO` | `mc2root` |
| 06 | `tcpv` | `tcpv` | `TCPV` | `mc2root` |
| 07 | `stt` | `stt` | `STT` | `mc2root` |
| 08 | `gem_hits` | `gem_hits` | `GEM` | `mc2root` |
| 09 | `gem_tracks` | `gem_tracks` | `GEMTracks` | `gem_hits`, `bh` |
| 10 | `tracklets` | `tracked` | `Tracked` | `bh`, `stt`, `sps` |
| 11 | `vertex` | `vertex` | `Vertex` | `tracklets`, `bh`, `sps`, `gem_tracks`, `veto` |
| 12 | `pathlength` | `pathlength` | `PathLength` | `bh`, `gem_tracks`, `tracklets`, `sps`, `vertex` |
| 13 | `pbglass` | `pbglass` | `PbGlass` | `mc2root`, `bh`, `bm`, `veto` |
| 14 | `cross_section` | `cross_section` | `cs` | `pathlength`, `mc2root`, `bh`, `bm`, `sps`, `pbglass`, `gem_tracks`, `veto`, `tcpv` |

## Running on Slurm

Use the dependency-aware freeway orchestrator for normal cluster work:

```bash
bash src/slurm/run_freeway.sh <pipeline-tag>
```

It creates `data_process/<tag>/`, snapshots configs, checks which stage ROOT
files already exist, and submits every ready stage with `sbatch`.

Stage 00 g4PSI uses `SLURM_SIM_CONFIG`. The stage runs one worker per selected
task, splits `N_EVENTS` across those workers, writes per-worker logs under
`data_process/<tag>/g4psi_chunks/`, merges chunk ROOT files into the normal
`*_g4psi.root`, then deletes successful chunk ROOT files. Chunk logs are kept.

Cooker stages use `SLURM_RECIPE_CONFIG` and currently run one output per stage.
The shared parallel worker helper is in place for future cooker parallelization,
but cooker stages are not parallelized by default.

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

Individual stage scripts live in `src/shell/freeway/`. They can be run directly
when required inputs already exist:

```bash
bash src/shell/freeway/11_run_vertex.sh <pipeline-tag>
```

When running on a system with the `packman-muse` Pixi stack, prefer:

```bash
cd packman-muse
./scripts/pixi-local run -e batch bash ../src/shell/freeway/11_run_vertex.sh <pipeline-tag>
```

`test_run.sh` is a manual sequential smoke runner. It is not the preferred
cluster orchestrator, but it is useful for local debugging or for running a
range of stages by hand.

```bash
bash test_run.sh <pipeline-tag>

START_STAGE=7 END_STAGE=14 bash test_run.sh <pipeline-tag>
STACK_DIR=/path/to/packman-muse bash test_run.sh <pipeline-tag>
```

`START_STAGE` and `END_STAGE` are zero-based freeway item numbers. Defaults are
`0` and `14`. The script runs through `STACK_DIR/scripts/pixi-local`.

## Useful Checks

Check run status:

```bash
cat data_process/<tag>/is_submitted.txt
ls -lh data_process/<tag>/*.root
ls -lh data_process/<tag>/slurm/
```

Validate a ROOT file has an expected tree:

```bash
cd packman-muse
./scripts/pixi-local run -e batch python \
  ../src/python/validate_root_file.py \
  ../data_process/<tag>/<tag>_g4psi.root T
```

Count payloads:

```bash
cd packman-muse
./scripts/pixi-local run -e batch python \
  ../src/python/count_root_payload.py \
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
G4PSI_PARALLEL_TASKS   override stage-00 worker count for local/test runs
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
