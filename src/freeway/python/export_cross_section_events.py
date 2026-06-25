#!/usr/bin/env python
import argparse
import csv
import json
import math
import os
import sys

import ROOT


EVENT_COLUMNS = (
    "event_index",
    "event_number",
    "event_weight",
    "particle_pid",
    "side",
    "side_name",
    "theta_deg",
    "theta_bin",
    "vertex_x_mm",
    "vertex_y_mm",
    "vertex_z_mm",
    "doca_mm",
    "vertex_pid",
    "stt_id",
    "gem_id",
    "bhc_bar",
    "bhd_bar",
    "signal_pid_hit",
    "lut5_hit",
    "calo_high_hit",
    "is_intime_tof",
    "is_decay",
    "is_good_doca",
    "is_target_vertex",
)

CS_HIST_BY_PARTICLE = {
    "e+": "heeff",
    "e-": "heeff",
    "electron": "heeff",
    "positron": "heeff",
    "mu+": "hmueff",
    "mu-": "hmueff",
    "mu_pos": "hmueff",
    "mu_neg": "hmueff",
    "muon+": "hmueff",
    "muon-": "hmueff",
    "pi+": "hpieff",
    "pi-": "hpieff",
    "pion+": "hpieff",
    "pion-": "hpieff",
}

CS_VALUE_BINS = (
    ("bl_flux", 1),
    ("bl_triggers", 2),
    ("bl_confirmed", 3),
    ("bl_reconstructed", 4),
    ("gem_qualified", 5),
    ("bl_trig_live_time", 6),
    ("bl_trig_analyzable", 7),
    ("gem_analyzable", 8),
    ("incident_corrected", 9),
    ("scat_left_triggers", 10),
    ("scat_left_confirmed", 11),
    ("scat_left_reconstructed", 12),
    ("scat_left_live_time", 13),
    ("scat_left_analyzable", 14),
    ("stt_left_analyzable", 15),
    ("scat_right_triggers", 16),
    ("scat_right_confirmed", 17),
    ("scat_right_reconstructed", 18),
    ("scat_right_live_time", 19),
    ("scat_right_analyzable", 20),
    ("stt_right_analyzable", 21),
    ("intime_tof_left", 22),
    ("real_scat_left", 23),
    ("intime_tof_right", 24),
    ("real_scat_right", 25),
    ("rid_cut_fraction", 26),
    ("total_real_scat", 27),
    ("not_calo_left", 28),
    ("not_calo_right", 29),
    ("calo_high_e_rate", 30),
    ("total_survive_calo", 31),
    ("bad_doca_left", 32),
    ("bad_doca_right", 33),
    ("final_scat", 34),
    ("beam_decay_rate", 35),
    ("target_thickness_mm", 36),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export cross-section summaries.")
    parser.add_argument("--cross-section-root", required=True)
    parser.add_argument("--hazard-truth-root", required=True)
    parser.add_argument("--g4psi-root", required=True)
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--reported-events-csv")
    parser.add_argument("--reported-summary-json")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--particle", required=True)
    parser.add_argument("--particle-pid", required=True, type=int)
    return parser.parse_args()


def ratio(numerator, denominator):
    if denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def maybe_int(value):
    if value is None:
        return None
    try:
        numeric = float(value)
    except Exception:
        return value
    if math.isfinite(numeric) and abs(numeric - round(numeric)) < 1e-9:
        return int(round(numeric))
    return numeric


def open_root(path):
    root_file = ROOT.TFile.Open(path, "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open ROOT file: {path}")
    return root_file


def count_hazard_truth(path):
    root_file = open_root(path)
    tree = root_file.Get("hazard_truth")
    if not tree or not tree.InheritsFrom("TTree"):
        root_file.Close()
        raise RuntimeError(f"Missing hazard_truth tree: {path}")

    total = int(tree.GetEntries())
    pass_truth = 0
    pid_counts = {}
    side_counts = {}
    for row in tree:
        pass_truth += int(row.pass_truth == 1)
        pid = str(int(row.particle_pid))
        side = str(row.side)
        pid_counts[pid] = pid_counts.get(pid, 0) + 1
        side_counts[side] = side_counts.get(side, 0) + 1

    root_file.Close()
    return total, pass_truth, pid_counts, side_counts


def read_g4psi_counts(path):
    root_file = open_root(path)
    tree = root_file.Get("T")
    saved_events = int(tree.GetEntries()) if tree and tree.InheritsFrom("TTree") else None

    requested_events = None
    run_control = root_file.Get("RunControl")
    if run_control:
        try:
            if int(run_control.GetNoElements()) > 0:
                requested_events = maybe_int(run_control[0])
        except Exception:
            requested_events = None

    root_file.Close()
    return requested_events, saved_events


def serializable_value(value):
    if isinstance(value, bool):
        return int(value)
    try:
        if isinstance(value, (str, int, float)):
            return value
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        pass
    return str(value)


def side_name(side):
    try:
        side_int = int(side)
    except Exception:
        return "unknown"
    return {0: "left", 1: "right"}.get(side_int, "unknown")


def value_attr(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def bool_int_attr(obj, name, default=False):
    return int(bool(value_attr(obj, name, default)))


def row_from_accepted_event(event_index, event):
    side = maybe_int(value_attr(event, "side", -1))
    return {
        "event_index": event_index,
        "event_number": maybe_int(value_attr(event, "event_number", None)),
        "event_weight": serializable_value(value_attr(event, "event_weight", 1.0)),
        "particle_pid": maybe_int(value_attr(event, "particle_pid", None)),
        "side": side,
        "side_name": side_name(side),
        "theta_deg": serializable_value(value_attr(event, "theta_deg", None)),
        "theta_bin": maybe_int(value_attr(event, "theta_bin", None)),
        "vertex_x_mm": serializable_value(value_attr(event, "vertex_x_mm", None)),
        "vertex_y_mm": serializable_value(value_attr(event, "vertex_y_mm", None)),
        "vertex_z_mm": serializable_value(value_attr(event, "vertex_z_mm", None)),
        "doca_mm": serializable_value(value_attr(event, "doca_mm", None)),
        "vertex_pid": maybe_int(value_attr(event, "vertex_pid", None)),
        "stt_id": maybe_int(value_attr(event, "stt_id", None)),
        "gem_id": maybe_int(value_attr(event, "gem_id", None)),
        "bhc_bar": maybe_int(value_attr(event, "bhc_bar", None)),
        "bhd_bar": maybe_int(value_attr(event, "bhd_bar", None)),
        "signal_pid_hit": bool_int_attr(event, "signal_pid_hit"),
        "lut5_hit": bool_int_attr(event, "lut5_hit"),
        "calo_high_hit": bool_int_attr(event, "calo_high_hit"),
        "is_intime_tof": bool_int_attr(event, "is_intime_tof"),
        "is_decay": bool_int_attr(event, "is_decay", True),
        "is_good_doca": bool_int_attr(event, "is_good_doca"),
        "is_target_vertex": bool_int_attr(event, "is_target_vertex"),
    }


def write_empty_cs_events(output_csv):
    with open(output_csv, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=EVENT_COLUMNS)
        writer.writeheader()


def load_musetree_dictionary():
    muse_prefix = os.environ.get("MUSE_PREFIX")
    candidates = []
    if muse_prefix:
        include_dir = os.path.join(muse_prefix, "include")
        if os.path.isdir(include_dir):
            try:
                ROOT.gInterpreter.AddIncludePath(include_dir)
            except Exception:
                pass
        for lib_name in ("libmusetree.so", "libmusetree.dylib"):
            candidates.append(os.path.join(muse_prefix, "lib", lib_name))
    candidates.append("libmusetree")

    for candidate in candidates:
        if os.path.isabs(candidate) and not os.path.exists(candidate):
            continue
        try:
            if ROOT.gSystem.Load(candidate) >= 0:
                return True
        except Exception:
            continue
    return False


def export_cs_accepted_branch(root_file, output_csv):
    tree = root_file.Get("cs")
    if not tree or not tree.InheritsFrom("TTree"):
        return False, 0, list(EVENT_COLUMNS)

    branch_name = None
    for candidate in ("CSAcceptedEvents", "cs_events"):
        if tree.GetBranch(candidate):
            branch_name = candidate
            break
    if branch_name is None:
        return False, 0, list(EVENT_COLUMNS)

    if not load_musetree_dictionary():
        raise RuntimeError(
            f"Found {branch_name} branch, but could not load libmusetree dictionary"
        )

    rows_written = 0
    with open(output_csv, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        for event_index in range(int(tree.GetEntries())):
            tree.GetEntry(event_index)
            container = value_attr(tree, branch_name)
            accepted_events = value_attr(container, "events", [])
            for accepted_event in accepted_events:
                writer.writerow(row_from_accepted_event(event_index, accepted_event))
                rows_written += 1

    return True, rows_written, list(EVENT_COLUMNS)


def export_top_level_cs_events(root_file, output_csv):
    tree = root_file.Get("cs_events")
    if not tree or not tree.InheritsFrom("TTree"):
        return False, 0, list(EVENT_COLUMNS)

    branch_names = [branch.GetName() for branch in tree.GetListOfBranches()]
    with open(output_csv, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=branch_names)
        writer.writeheader()
        rows_written = 0
        for row in tree:
            writer.writerow(
                {name: serializable_value(getattr(row, name)) for name in branch_names}
            )
            rows_written += 1
    return True, rows_written, branch_names


def export_cs_events(root_file, output_csv):
    branch_present, branch_rows, branch_columns = export_cs_accepted_branch(
        root_file, output_csv
    )
    if branch_present:
        return branch_present, branch_rows, branch_columns

    tree_present, tree_rows, tree_columns = export_top_level_cs_events(
        root_file, output_csv
    )
    if tree_present:
        return tree_present, tree_rows, tree_columns

    write_empty_cs_events(output_csv)
    return False, 0, list(EVENT_COLUMNS)


def read_cs_efficiency(root_file, particle):
    hist_name = CS_HIST_BY_PARTICLE.get(particle)
    hist = root_file.Get(hist_name) if hist_name else None
    values = {}
    if hist and hist.InheritsFrom("TH1"):
        for name, bin_number in CS_VALUE_BINS:
            values[name] = maybe_int(hist.GetBinContent(bin_number))
    return hist_name, values


def main() -> int:
    args = parse_args()
    ROOT.gROOT.SetBatch(True)
    reported_events_csv = args.reported_events_csv or args.events_csv
    reported_summary_json = args.reported_summary_json or args.summary_json

    os.makedirs(os.path.dirname(os.path.abspath(args.events_csv)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.summary_json)), exist_ok=True)

    hazard_total, pass_truth_count, pid_counts, side_counts = count_hazard_truth(
        args.hazard_truth_root
    )
    requested_events, saved_events = read_g4psi_counts(args.g4psi_root)

    cs_file = open_root(args.cross_section_root)
    cs_tree = cs_file.Get("cs")
    cs_tree_entries = (
        int(cs_tree.GetEntries()) if cs_tree and cs_tree.InheritsFrom("TTree") else None
    )
    cs_events_present, cs_events_rows, cs_event_columns = export_cs_events(
        cs_file, args.events_csv
    )
    hist_name, cs_values = read_cs_efficiency(cs_file, args.particle)

    if cs_events_present:
        final_accepted_count = cs_events_rows
        final_count_source = "cs_events"
    else:
        final_accepted_count = maybe_int(cs_values.get("final_scat"))
        final_count_source = hist_name or "missing_cs_efficiency_histogram"

    final_count_number = final_accepted_count or 0
    final_labels_exact = final_count_number == 0 or cs_events_present
    if final_count_number == 0:
        label_status = "exact_negative_zero_final_count"
    elif cs_events_present:
        label_status = "cs_events_available_candidate_join_required"
    else:
        label_status = "aggregate_only_no_candidate_match"

    summary = {
        "run_tag": args.run_tag,
        "particle": args.particle,
        "particle_pid": args.particle_pid,
        "cs_events_present": cs_events_present,
        "cs_events_rows": cs_events_rows,
        "cs_event_columns": cs_event_columns,
        "label_status": label_status,
        "final_labels_exact_per_candidate": final_labels_exact,
        "counts": {
            "requested_events": requested_events,
            "g4psi_saved_events": saved_events,
            "cross_section_tree_entries": cs_tree_entries,
            "hazard_truth_candidates": hazard_total,
            "pass_truth_candidates": pass_truth_count,
            "final_accepted_count": final_accepted_count,
        },
        "ratios": {
            "g4psi_saved_over_requested": ratio(saved_events, requested_events),
            "pass_truth_over_hazard_truth": ratio(pass_truth_count, hazard_total),
            "final_over_pass_truth": ratio(final_count_number, pass_truth_count),
            "final_over_hazard_truth": ratio(final_count_number, hazard_total),
            "final_over_requested_events": ratio(final_count_number, requested_events),
        },
        "pid_counts": pid_counts,
        "side_counts": side_counts,
        "final_accepted_count_source": final_count_source,
        "cs_efficiency_histogram": hist_name,
        "cs_efficiency_values": cs_values,
    }

    with open(args.summary_json, "w") as json_file:
        json.dump(summary, json_file, indent=2, sort_keys=True)
        json_file.write("\n")

    cs_file.Close()
    print(f"Cross-section events CSV: {reported_events_csv}")
    print(f"Cross-section summary:    {reported_summary_json}")
    print(f"Final accepted count:     {final_accepted_count}")
    print(f"Final/pass_truth ratio:   {summary['ratios']['final_over_pass_truth']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
