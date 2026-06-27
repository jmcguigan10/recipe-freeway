import argparse
import csv
import math
import os
import sys

import ROOT


BEAM_VECTOR_BRANCHES = (
    "beam_id",
    "beam_p",
    "beam_theta",
    "beam_phi",
    "beam_x0",
    "beam_y0",
    "beam_z0",
    "beam_time",
)

REQUIRED_BRANCHES = (
    "beam_particles",
    *BEAM_VECTOR_BRANCHES,
    "BHC_TrackID",
    "BHC_Edep",
    "BHC_L",
    "BHD_TrackID",
    "BHD_Edep",
    "BHD_L",
    "GEM0_TrackID",
    "GEM0_Edep",
)

OUTPUT_COLUMNS = (
    "run_tag",
    "event_index",
    "event_id",
    "event_seed1",
    "event_seed2",
    "generator_event",
    "particle_pdg",
    "beam_particles",
    "beam_p_mev",
    "beam_time_ns",
    "x0_mm",
    "y0_mm",
    "z0_mm",
    "theta_rad",
    "phi_rad",
    "dir_x",
    "dir_y",
    "dir_z",
    "xprime",
    "yprime",
    "bhc_hit_count",
    "bhd_hit_count",
    "gem0_hit_count",
    "hit_bhc_primary",
    "hit_bhd_primary",
    "hit_gem0_primary",
    "secondary_in_bhc",
    "secondary_in_bhd",
    "secondary_in_gem0",
    "bhc_primary_edep_sum_mev",
    "bhd_primary_edep_sum_mev",
    "gem0_primary_edep_sum_mev",
    "bhc_primary_light_sum_mev",
    "bhd_primary_light_sum_mev",
    "bhc_above_threshold",
    "bhd_above_threshold",
    "misses_gem0",
    "reaches_gem0",
    "coarse_state",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export one-row-per-event GEM0 classifier data from g4PSI T."
    )
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--tree", default="T")
    parser.add_argument(
        "--run-tag",
        help="Run tag to write into the CSV. Defaults to the input ROOT basename.",
    )
    parser.add_argument(
        "--start-event",
        type=int,
        default=0,
        help="First global event index to export. Defaults to 0.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        help="Maximum number of events to export from --start-event.",
    )
    return parser.parse_args()


def branch_names(tree):
    return {branch.GetName() for branch in tree.GetListOfBranches()}


def require_branches(tree):
    names = branch_names(tree)
    missing = [name for name in REQUIRED_BRANCHES if name not in names]
    if missing:
        raise RuntimeError(
            "Input tree is missing required branch(es): " + ", ".join(missing)
        )


def vector_values(tree, branch_name):
    value = getattr(tree, branch_name)
    try:
        return [value[index] for index in range(value.size())]
    except AttributeError:
        return [value]


def first_vector_value(tree, branch_name):
    values = vector_values(tree, branch_name)
    if len(values) != 1:
        raise RuntimeError(
            f"Expected exactly one value in {branch_name}; found {len(values)}"
        )
    return values[0]


def scalar_value(tree, branch_name, default=""):
    if not tree.GetBranch(branch_name):
        return default
    return getattr(tree, branch_name)


def int01(value):
    return 1 if value else 0


def detector_rows(tree, detector):
    track_ids = [int(track_id) for track_id in vector_values(tree, f"{detector}_TrackID")]
    edeps = [float(edep) for edep in vector_values(tree, f"{detector}_Edep")]
    lights = None
    if tree.GetBranch(f"{detector}_L"):
        lights = [float(light) for light in vector_values(tree, f"{detector}_L")]

    rows = []
    for index, track_id in enumerate(track_ids):
        rows.append(
            {
                "track_id": track_id,
                "edep": edeps[index] if index < len(edeps) else 0.0,
                "light": lights[index] if lights is not None and index < len(lights) else 0.0,
            }
        )
    return rows


def detector_summary(tree, detector, light_threshold=None):
    rows = detector_rows(tree, detector)
    primary_rows = [row for row in rows if row["track_id"] == 1]

    summary = {
        "hit_count": len(rows),
        "hit_primary": any(row["track_id"] == 1 for row in rows),
        "secondary": any(row["track_id"] != 1 for row in rows),
        "primary_edep_sum": sum(row["edep"] for row in primary_rows),
        "primary_light_sum": sum(row["light"] for row in primary_rows),
    }
    if light_threshold is not None:
        summary["above_threshold"] = any(row["light"] > light_threshold for row in rows)
    return summary


def default_run_tag(input_root):
    basename = os.path.basename(input_root)
    if basename.endswith("_g4psi.root"):
        return basename[: -len("_g4psi.root")]
    if basename.endswith(".root"):
        return basename[: -len(".root")]
    return basename


def coarse_state(hit_bhc, hit_bhd, hit_gem0):
    if hit_gem0:
        return "reaches_gem0"
    if hit_bhd:
        return "misses_gem0_after_bhd"
    if hit_bhc:
        return "misses_gem0_after_bhc"
    return "lost_before_bhc"


def event_row(tree, event_index, run_tag):
    beam_particles = int(scalar_value(tree, "beam_particles"))
    if beam_particles != 1:
        raise RuntimeError(
            f"Expected beam_particles == 1 at event index {event_index}; found {beam_particles}"
        )

    theta = float(first_vector_value(tree, "beam_theta"))
    phi = float(first_vector_value(tree, "beam_phi"))
    dir_x = math.sin(theta) * math.cos(phi)
    dir_y = math.sin(theta) * math.sin(phi)
    dir_z = math.cos(theta)
    xprime = dir_x / dir_z if dir_z else float("nan")
    yprime = dir_y / dir_z if dir_z else float("nan")

    bhc = detector_summary(tree, "BHC", light_threshold=0.0)
    bhd = detector_summary(tree, "BHD", light_threshold=0.15)
    gem0 = detector_summary(tree, "GEM0")

    hit_bhc = bhc["hit_primary"]
    hit_bhd = bhd["hit_primary"]
    hit_gem0 = gem0["hit_primary"]

    return {
        "run_tag": run_tag,
        "event_index": event_index,
        "event_id": scalar_value(tree, "EventID"),
        "event_seed1": scalar_value(tree, "EventSeed1"),
        "event_seed2": scalar_value(tree, "EventSeed2"),
        "generator_event": int01(bool(scalar_value(tree, "GeneratorEvent", False))),
        "particle_pdg": int(first_vector_value(tree, "beam_id")),
        "beam_particles": beam_particles,
        "beam_p_mev": float(first_vector_value(tree, "beam_p")),
        "beam_time_ns": float(first_vector_value(tree, "beam_time")),
        "x0_mm": float(first_vector_value(tree, "beam_x0")),
        "y0_mm": float(first_vector_value(tree, "beam_y0")),
        "z0_mm": float(first_vector_value(tree, "beam_z0")),
        "theta_rad": theta,
        "phi_rad": phi,
        "dir_x": dir_x,
        "dir_y": dir_y,
        "dir_z": dir_z,
        "xprime": xprime,
        "yprime": yprime,
        "bhc_hit_count": bhc["hit_count"],
        "bhd_hit_count": bhd["hit_count"],
        "gem0_hit_count": gem0["hit_count"],
        "hit_bhc_primary": int01(hit_bhc),
        "hit_bhd_primary": int01(hit_bhd),
        "hit_gem0_primary": int01(hit_gem0),
        "secondary_in_bhc": int01(bhc["secondary"]),
        "secondary_in_bhd": int01(bhd["secondary"]),
        "secondary_in_gem0": int01(gem0["secondary"]),
        "bhc_primary_edep_sum_mev": bhc["primary_edep_sum"],
        "bhd_primary_edep_sum_mev": bhd["primary_edep_sum"],
        "gem0_primary_edep_sum_mev": gem0["primary_edep_sum"],
        "bhc_primary_light_sum_mev": bhc["primary_light_sum"],
        "bhd_primary_light_sum_mev": bhd["primary_light_sum"],
        "bhc_above_threshold": int01(bhc["above_threshold"]),
        "bhd_above_threshold": int01(bhd["above_threshold"]),
        "misses_gem0": int01(not hit_gem0),
        "reaches_gem0": int01(hit_gem0),
        "coarse_state": coarse_state(hit_bhc, hit_bhd, hit_gem0),
    }


def event_bounds(tree, start_event, max_events):
    total_entries = int(tree.GetEntries())
    if start_event < 0:
        raise RuntimeError(f"--start-event must be non-negative: {start_event}")
    if max_events is not None and max_events < 0:
        raise RuntimeError(f"--max-events must be non-negative: {max_events}")

    stop_event = total_entries
    if max_events is not None:
        stop_event = min(total_entries, start_event + max_events)
    start_event = min(start_event, total_entries)
    return start_event, stop_event, total_entries


def iter_event_rows(tree, run_tag, start_event, stop_event):
    for event_index in range(start_event, stop_event):
        if tree.GetEntry(event_index) <= 0:
            raise RuntimeError(f"Could not read event index {event_index}")
        yield event_row(tree, event_index, run_tag)


def write_csv(path, rows):
    row_count = 0
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            row_count += 1
    return row_count


def main():
    args = parse_args()
    ROOT.gROOT.SetBatch(True)

    root_file = ROOT.TFile.Open(args.input_root, "READ")
    if not root_file or root_file.IsZombie():
        print(f"Could not open ROOT file: {args.input_root}", file=sys.stderr)
        return 1

    tree = root_file.Get(args.tree)
    if not tree:
        print(
            f"Input ROOT file is missing tree {args.tree!r}: {args.input_root}",
            file=sys.stderr,
        )
        return 1

    try:
        require_branches(tree)
        run_tag = args.run_tag or default_run_tag(args.input_root)
        start_event, stop_event, total_entries = event_bounds(
            tree, args.start_event, args.max_events
        )
        row_count = write_csv(
            args.output_csv,
            iter_event_rows(tree, run_tag, start_event, stop_event),
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Rows written: {row_count}")
    print(f"Event range:  {start_event}:{stop_event} of {total_entries}")
    print(f"CSV output:   {args.output_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
