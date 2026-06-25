#!/usr/bin/env python
import argparse
import csv
import math
import os
import sys
from array import array

import ROOT


STRING_COLUMNS = ("candidate_id", "run_tag", "particle", "side")
INT_COLUMNS = (
    "event_number",
    "event_index",
    "target_index",
    "particle_pid",
    "truth_track_id",
    "pass_truth",
    "pass_sps_side_truth_hint",
    "theta_bin",
)
DOUBLE_COLUMNS = (
    "event_weight",
    "theta_deg",
    "vertex_x_mm",
    "vertex_y_mm",
    "vertex_z_mm",
    "momentum_mev",
)
OUTPUT_COLUMNS = (
    "candidate_id",
    "run_tag",
    "event_number",
    "event_index",
    "target_index",
    "event_weight",
    "particle",
    "particle_pid",
    "momentum_mev",
    "theta_deg",
    "theta_bin",
    "vertex_x_mm",
    "vertex_y_mm",
    "vertex_z_mm",
    "truth_track_id",
    "side",
    "pass_truth",
    "pass_sps_side_truth_hint",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the g4PSI target-scatter denominator table."
    )
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--particle", required=True)
    parser.add_argument("--particle-pid", required=True, type=int)
    parser.add_argument("--momentum-mev", required=True, type=float)
    return parser.parse_args()


def tree_branch(tree, name):
    if not tree.GetBranch(name):
        return None
    try:
        return getattr(tree, name)
    except Exception:
        return None

def tree_formula_value(tree, expression, cache):
    if expression not in cache:
        try:
            cache[expression] = ROOT.TTreeFormula(expression, expression, tree)
        except Exception:
            cache[expression] = None
    formula = cache[expression]
    if formula is None:
        return None
    try:
        value = formula.EvalInstance()
    except Exception:
        return None
    try:
        value_float = float(value)
    except Exception:
        return None
    if not math.isfinite(value_float):
        return None
    return value_float


def sized_container_length(value):
    if value is None:
        return None
    try:
        return int(value.size())
    except Exception:
        pass
    try:
        return len(value)
    except Exception:
        return None


def vector_size(value) -> int:
    if value is None:
        return 0
    container_size = sized_container_length(value)
    if container_size is not None:
        return container_size
    return 1


def vector_value(value, index: int, default):
    if value is None:
        return default
    try:
        if index >= vector_size(value):
            return default
        return value[index]
    except Exception:
        if index == 0:
            try:
                return value
            except Exception:
                return default
        return default


def int_value(value, default: int = -1) -> int:
    try:
        return int(value)
    except Exception:
        return default


def float_value(value, default: float = math.nan) -> float:
    try:
        return float(value)
    except Exception:
        return default


def event_number(tree, event_index: int) -> int:
    event_info = tree_branch(tree, "EventInfo")
    if event_info is not None:
        try:
            return int(event_info.eventNumber)
        except Exception:
            pass

    event_id = tree_branch(tree, "EventID")
    if event_id is not None:
        return int_value(event_id, event_index)

    return event_index


def event_weight(tree, formula_cache=None) -> float:
    event_info = tree_branch(tree, "EventInfo")
    if event_info is not None:
        try:
            return float(event_info.weight)
        except Exception:
            pass
    if formula_cache is None:
        formula_cache = {}
    for expression in ("EventInfo.weight", "EventInfo.event_weight", "event_weight", "EventInfo.wgt", "wgt", "weight"):
        value = tree_formula_value(tree, expression, formula_cache)
        if value is not None:
            return value
    return 1.0


def hit_present(tree, branch_name: str) -> bool:
    value = tree_branch(tree, branch_name)
    if value is None:
        return False
    container_size = sized_container_length(value)
    if container_size is not None:
        return container_size > 0
    try:
        return bool(value)
    except Exception:
        return False


def sps_side_hint(tree) -> str:
    left = hit_present(tree, "SPSLF_Hit") and hit_present(tree, "SPSLR_Hit")
    right = hit_present(tree, "SPSRF_Hit") and hit_present(tree, "SPSRR_Hit")

    if left and not right:
        return "left"
    if right and not left:
        return "right"
    return "unknown"


def create_output_tree():
    output_tree = ROOT.TTree("hazard_truth", "hazard_truth")
    string_buffers = {name: ROOT.std.string() for name in STRING_COLUMNS}
    int_buffers = {name: array("i", [0]) for name in INT_COLUMNS}
    double_buffers = {name: array("d", [0.0]) for name in DOUBLE_COLUMNS}

    for name, buffer in string_buffers.items():
        output_tree.Branch(name, buffer)
    for name, buffer in int_buffers.items():
        output_tree.Branch(name, buffer, f"{name}/I")
    for name, buffer in double_buffers.items():
        output_tree.Branch(name, buffer, f"{name}/D")

    return output_tree, string_buffers, int_buffers, double_buffers


def fill_output(output_tree, string_buffers, int_buffers, double_buffers, row) -> None:
    for name, buffer in string_buffers.items():
        buffer.assign(str(row[name]))
    for name, buffer in int_buffers.items():
        buffer[0] = int(row[name])
    for name, buffer in double_buffers.items():
        buffer[0] = float(row[name])
    output_tree.Fill()


def candidate_rows(tree, args):
    n_entries = int(tree.GetEntries())
    formula_cache = {}
    for event_index in range(n_entries):
        tree.GetEntry(event_index)

        pids = tree_branch(tree, "TGT_ParticleID")
        theta = tree_branch(tree, "TGT_Theta")
        vertex_x = tree_branch(tree, "TGT_VertexX")
        vertex_y = tree_branch(tree, "TGT_VertexY")
        vertex_z = tree_branch(tree, "TGT_VertexZ")
        track_ids = tree_branch(tree, "TGT_TrackID")

        n_candidates = vector_size(pids)
        evt_number = event_number(tree, event_index)
        evt_weight = event_weight(tree, formula_cache)
        side = sps_side_hint(tree)
        pass_side_hint = int(side != "unknown")

        for target_index in range(n_candidates):
            particle_pid = int_value(vector_value(pids, target_index, 0), 0)
            theta_rad = float_value(vector_value(theta, target_index, math.nan))
            theta_deg = math.degrees(theta_rad) if math.isfinite(theta_rad) else math.nan
            truth_track_id = int_value(vector_value(track_ids, target_index, -1), -1)
            candidate_id = (
                f"{args.run_tag}:{evt_number}:{target_index}:{side}:{particle_pid}"
            )

            yield {
                "candidate_id": candidate_id,
                "run_tag": args.run_tag,
                "event_number": evt_number,
                "event_index": event_index,
                "target_index": target_index,
                "event_weight": evt_weight,
                "particle": args.particle,
                "particle_pid": particle_pid,
                "momentum_mev": args.momentum_mev,
                "theta_deg": theta_deg,
                "theta_bin": -1,
                "vertex_x_mm": float_value(
                    vector_value(vertex_x, target_index, math.nan)
                ),
                "vertex_y_mm": float_value(
                    vector_value(vertex_y, target_index, math.nan)
                ),
                "vertex_z_mm": float_value(
                    vector_value(vertex_z, target_index, math.nan)
                ),
                "truth_track_id": truth_track_id,
                "side": side,
                "pass_truth": int(particle_pid == args.particle_pid),
                "pass_sps_side_truth_hint": pass_side_hint,
            }


def main() -> int:
    args = parse_args()
    ROOT.gROOT.SetBatch(True)

    input_file = ROOT.TFile.Open(args.input_root, "READ")
    if not input_file or input_file.IsZombie():
        print(f"Could not open input ROOT file: {args.input_root}", file=sys.stderr)
        return 1

    input_tree = input_file.Get("T")
    if not input_tree or not input_tree.InheritsFrom("TTree"):
        print(f"Input ROOT file is missing tree 'T': {args.input_root}", file=sys.stderr)
        input_file.Close()
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output_root)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)

    output_file = ROOT.TFile(args.output_root, "RECREATE")
    if not output_file or output_file.IsZombie():
        print(f"Could not create output ROOT file: {args.output_root}", file=sys.stderr)
        input_file.Close()
        return 1

    output_tree, string_buffers, int_buffers, double_buffers = create_output_tree()
    row_count = 0

    with open(args.output_csv, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for row in candidate_rows(input_tree, args):
            fill_output(output_tree, string_buffers, int_buffers, double_buffers, row)
            writer.writerow(row)
            row_count += 1

    output_file.cd()
    output_tree.Write()
    output_file.Close()
    input_file.Close()

    print(f"Wrote {row_count} hazard truth candidates")
    print(f"ROOT output: {args.output_root}")
    print(f"CSV output:  {args.output_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
