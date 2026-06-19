# Recipe Freeway

`recipe-freeway` is a lightweight orchestration layer around a local
`packman-muse` build. It generates a g4PSI ROOT file, then runs the MUSE
cooker recipes in dependency order through Slurm.

This repository does not vendor or build MUSE by itself. It expects a nested
checkout named `packman-muse/` inside this repository, and that checkout owns
the Pixi environment, source downloads, MUSE/g4PSI build, and runtime stack.

## Repository Contract

Expected checkout shape:

```text
recipe-freeway/
  configs/                 pipeline defaults
  data_process/            per-run outputs and copied config snapshots
  macros/generated/        generated g4PSI macros
  packman-muse/            required nested checkout
  src/shell/               stage runners and shared shell library
  src/slurm/               Slurm freeway orchestrator
  templates/g4psi/         g4PSI macro template
```

The default nested checkout is:

```bash
git clone git@github.com:jmcguigan10/packman-muse.git packman-muse
```

The top-level shell library defaults to:

```text
STACK_DIR    = ./packman-muse
MUSE_SRC_DIR = ./packman-muse/.install/src/muse
DATA_ROOT    = ./data_process
```

`STACK_DIR`, `MUSE_SRC_DIR`, and `DATA_ROOT` can be overridden in the
environment, but most scripts assume the defaults.

## First Setup

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

Use `packman-muse/scripts/pixi-local`, not a global Pixi, for commands that
need ROOT, g4PSI, MUSE, or the cooker. The wrapper keeps the toolchain local to
`packman-muse`.

The pipeline shell code requires Bash 4.2+ because it uses associative arrays.
On systems with old `/bin/bash`, run through the `packman-muse` Pixi
environment or put a newer Bash earlier on `PATH`.

## Configuration Files

Pipeline defaults live in `configs/*.sh`:

```text
configs/physics.sh   run number, particle, momentum, event count, seeds, RadGen mode
configs/g4psi.sh     g4PSI macro template and generated macro directory
configs/slurm.sh     Slurm resources for simulation and recipe stages
configs/recipes.sh   freeway stage order, recipes, inputs, outputs, trees, cooker calls
```

Important current recipe call configuration:

```bash
declare -gA FREEWAY_STAGE_COOKER_CALLS=(
  [bh]="BH:setMomentum:@BEAM_MOMENTUM@"
  [tracklets]="cryptor:setMomentum:@BEAM_MOMENTUM@"
)
```

The BH momentum call is required for these simulated positron runs. Without it,
the BH plugin can fall back to missing slow-control momentum, BHD PID stays
zero, vertexing goes empty, and cross-section output is zero.

## Run-Directory Config Snapshots

Each pipeline tag gets a run directory:

```text
data_process/<pipeline-tag>/
```

When a run directory is created or resolved, the pipeline snapshots the current
top-level configs into:

```text
data_process/<pipeline-tag>/configs/
```

Existing snapshot files win over top-level `configs/*.sh`. The copy operation
does not overwrite them.

That means changing `configs/recipes.sh` after a run already exists is not
enough for that run. For an existing run, either edit the copied file directly
or delete the stale copied config before rerunning:

```bash
rm data_process/<pipeline-tag>/configs/recipes.sh
bash src/slurm/run_freeway.sh <pipeline-tag>
```

On the next run, the missing snapshot file is recopied from the top-level
`configs/recipes.sh`.

## Pipeline Tags and Outputs

Pipeline tags are names, not paths. They must not contain `/`.

Example:

```bash
mc22308_rad2_e_pos_part_1M_probe_2
```

Outputs are written as:

```text
data_process/<tag>/<tag>_<stage-output>.root
```

For example:

```text
data_process/mc22308_rad2_e_pos_part_1M_probe_2/
  mc22308_rad2_e_pos_part_1M_probe_2_g4psi.root
  mc22308_rad2_e_pos_part_1M_probe_2_bh.root
  mc22308_rad2_e_pos_part_1M_probe_2_vertex.root
  mc22308_rad2_e_pos_part_1M_probe_2_cross_section.root
```

Keep the tag consistent with `configs/physics.sh`; the scripts do not derive
the tag from the physics config.

## Freeway Stages

The stage graph is defined in `configs/recipes.sh`.

| Item | Stage | Output suffix | Tree | Inputs |
| --- | --- | --- | --- | --- |
| 00 | `g4psi` | `g4psi` | `T` | none |
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

The normal entrypoint is the dependency-aware freeway orchestrator:

```bash
bash src/slurm/run_freeway.sh <pipeline-tag>
```

It creates `data_process/<tag>/`, snapshots configs, checks which stage ROOT
files already exist, and submits every ready stage with `sbatch`.

Stage logs go to:

```text
data_process/<tag>/slurm/
```

Submitted stages are recorded in:

```text
data_process/<tag>/is_submitted.txt
```

To submit one numbered stage explicitly:

```bash
bash src/slurm/submit_freeway.sh 02 <pipeline-tag>
```

This is useful for targeted reruns, but it does not replace understanding the
stage dependencies.

## Rerunning Existing Data

The orchestrator treats an existing non-empty stage ROOT file as complete. If
you need to rerun a stage in place, remove that output and any downstream
outputs that should be regenerated.

For config changes, also make sure the run-directory snapshot is current:

```bash
rm data_process/<tag>/configs/recipes.sh
```

If using the orchestrator after deleting outputs, remove stale submitted lines
for those stages from `data_process/<tag>/is_submitted.txt`; otherwise the
orchestrator may report the stage as submitted and wait for an output instead
of resubmitting it.

For a clean comparison, prefer a new pipeline tag.

## Useful Checks

Check a run's stage status:

```bash
cat data_process/<tag>/is_submitted.txt
ls -lh data_process/<tag>/*.root
```

Count payloads with PyROOT through the nested stack:

```bash
cd packman-muse
./scripts/pixi-local run -e batch python \
  ../src/python/count_root_payload.py \
  ../data_process/<tag>/<tag>_cross_section.root \
  cs CSAcceptedEvents events
```

For the current positron workflow, healthy recovery signs include:

```text
BH log contains: BH - setMomentum - 159.279
BH PID histogram title contains: p = 159.28 MeV/c
Vertex.eVertices.vertex is nonzero
PathLength.eScattering.vertex is nonzero
cs.CSAcceptedEvents.events is nonzero
```

If `BH` has BHC electron PID but BHD PID is all zero, the BH momentum command
was not applied to the run that produced that `bh.root`.

## Local Stage Execution

Individual stage scripts live in `src/shell/freeway/`. They can be run
directly when the required inputs already exist:

```bash
bash src/shell/freeway/11_run_vertex.sh <pipeline-tag>
```

For normal cluster work, use `src/slurm/run_freeway.sh` so dependencies,
resources, logs, and follow-up submissions are handled consistently.

## Important Environment Variables

```text
STACK_DIR              override the nested packman-muse checkout
MUSE_SRC_DIR           override the MUSE source tree
DATA_ROOT              override the root output directory
DATA_RUN_DIR           exported by Slurm jobs; must match the selected tag
PIPELINE_TAG           selected run tag
REAL_MUSE_REPO_ROOT    exported by Slurm jobs so they can find this checkout
MUSE_INIT              optional override for the cooker init XML
MUSE_PIPELINE_TMPDIR   temp directory for cooker and ROOT validation files
FREEWAY_SBATCH_BIN     override sbatch for testing
```

## Notes

- `packman-muse` is the build/runtime owner. If ROOT, g4PSI, cooker, or MUSE
  libraries are missing, fix the nested `packman-muse` stack first.
- The `mc2root` freeway stage writes the `mmt` output.
- `g4psi` uses `configs/g4psi.sh`, `templates/g4psi/muse.mac.erb`, and
  `src/ruby/render_macro.rb` to generate a macro under `macros/generated/`.
- RadGen mode comes from `configs/physics.sh` as `RAD_MODE`; the runner passes
  it to g4PSI as `--rad2`, `--rad3`, etc.
