#!/usr/bin/env python
import argparse
import csv
import json
import os
import sys

import ROOT


BASE_COLUMNS = (
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
    "side",
    "vertex_x_mm",
    "vertex_y_mm",
    "vertex_z_mm",
    "truth_track_id",
    "pass_truth",
    "pass_sps_side_truth_hint",
)

EVENT_FEATURE_COLUMNS = (
    "cs_event_weight",
    "cs_particle_pid",
    "cs_side",
    "cs_side_name",
    "cs_theta_deg",
    "cs_theta_bin",
    "cs_vertex_x_mm",
    "cs_vertex_y_mm",
    "cs_vertex_z_mm",
    "bh_bhc_bar",
    "bh_bhd_bar",
    "bh_signal_pid_hit",
    "sps_lut5_hit",
    "pathlength_doca_mm",
    "pathlength_is_intime_tof",
    "pathlength_is_decay",
    "pathlength_is_good_doca",
    "pathlength_is_target_vertex",
    "pbglass_calo_high_hit",
)

TRAINING_COLUMNS = (
    "run_tag",
    "event_index",
    "event_number",
    "event_weight",
    "particle",
    "particle_pid",
    "momentum_mev",
    "n_truth_candidates",
    "n_signal_truth_candidates",
    "n_pass_sps_side_truth_hint",
    "n_truth_left",
    "n_truth_right",
    "n_truth_unknown",
    "n_signal_truth_left",
    "n_signal_truth_right",
    "n_signal_truth_unknown",
    "signal_theta_min_deg",
    "signal_theta_max_deg",
    "signal_theta_mean_deg",
    "accepted_event",
    "n_accepted_cs_events",
    "label_status",
) + EVENT_FEATURE_COLUMNS


EMPTY_EVENT_FEATURES = {
    "cs_event_weight": None,
    "cs_particle_pid": None,
    "cs_side": None,
    "cs_side_name": None,
    "cs_theta_deg": None,
    "cs_theta_bin": None,
    "cs_vertex_x_mm": None,
    "cs_vertex_y_mm": None,
    "cs_vertex_z_mm": None,
    "bh_bhc_bar": None,
    "bh_bhd_bar": None,
    "bh_signal_pid_hit": None,
    "sps_lut5_hit": None,
    "pathlength_doca_mm": None,
    "pathlength_is_intime_tof": None,
    "pathlength_is_decay": None,
    "pathlength_is_good_doca": None,
    "pathlength_is_target_vertex": None,
    "pbglass_calo_high_hit": None,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export event-level ML training tables.")
    parser.add_argument("--hazard-truth-root", required=True)
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-parquet", required=True)
    parser.add_argument("--output-summary-json", required=True)
    parser.add_argument("--reported-output-csv")
    parser.add_argument("--reported-output-parquet")
    parser.add_argument("--reported-output-summary-json")
    parser.add_argument("--hazard-truth-parquet", required=True)
    return parser.parse_args()


def scalar(row, name):
    value = getattr(row, name)
    try:
        if isinstance(value, str):
            return value
    except Exception:
        pass
    try:
        numeric = float(value)
    except Exception:
        return str(value)
    try:
        integer = int(value)
        if numeric == integer:
            return integer
    except Exception:
        pass
    return numeric


def read_tree_rows(path, tree_name, columns):
    root_file = ROOT.TFile.Open(path, "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open ROOT file: {path}")
    tree = root_file.Get(tree_name)
    if not tree or not tree.InheritsFrom("TTree"):
        root_file.Close()
        raise RuntimeError(f"Missing {tree_name} tree: {path}")

    rows = []
    for row in tree:
        rows.append({column: scalar(row, column) for column in columns})
    root_file.Close()
    return rows


def nullable_int(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def nullable_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def event_key(row):
    event_index = nullable_int(row.get("event_index"))
    event_number = nullable_int(row.get("event_number"))
    if event_index is None or event_number is None:
        return None
    return (event_index, event_number)


def group_truth_by_event(truth_rows):
    grouped = {}
    for row in truth_rows:
        key = event_key(row)
        if key is None:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def read_events_by_event(path):
    rows_by_key = {}
    with open(path, newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            key = event_key(row)
            if key is not None:
                rows_by_key.setdefault(key, []).append(row)
    return rows_by_key


def truth_side(row):
    side = str(row.get("side", "unknown")).strip().lower()
    return side if side in ("left", "right") else "unknown"


def side_from_csv(row):
    side_name = (row.get("side_name") or "").strip().lower()
    if side_name:
        return side_name
    side = (row.get("side") or "").strip()
    return {"0": "left", "1": "right"}.get(side, side.lower() or "unknown")


def event_features(event):
    if not event:
        return dict(EMPTY_EVENT_FEATURES)
    return {
        "cs_event_weight": nullable_float(event.get("event_weight")),
        "cs_particle_pid": nullable_int(event.get("particle_pid")),
        "cs_side": nullable_int(event.get("side")),
        "cs_side_name": side_from_csv(event),
        "cs_theta_deg": nullable_float(event.get("theta_deg")),
        "cs_theta_bin": nullable_int(event.get("theta_bin")),
        "cs_vertex_x_mm": nullable_float(event.get("vertex_x_mm")),
        "cs_vertex_y_mm": nullable_float(event.get("vertex_y_mm")),
        "cs_vertex_z_mm": nullable_float(event.get("vertex_z_mm")),
        "bh_bhc_bar": nullable_int(event.get("bhc_bar")),
        "bh_bhd_bar": nullable_int(event.get("bhd_bar")),
        "bh_signal_pid_hit": nullable_int(event.get("signal_pid_hit")),
        "sps_lut5_hit": nullable_int(event.get("lut5_hit")),
        "pathlength_doca_mm": nullable_float(event.get("doca_mm")),
        "pathlength_is_intime_tof": nullable_int(event.get("is_intime_tof")),
        "pathlength_is_decay": nullable_int(event.get("is_decay")),
        "pathlength_is_good_doca": nullable_int(event.get("is_good_doca")),
        "pathlength_is_target_vertex": nullable_int(event.get("is_target_vertex")),
        "pbglass_calo_high_hit": nullable_int(event.get("calo_high_hit")),
    }


def mean(values):
    return sum(values) / len(values) if values else None


def summarize_truth_event(rows):
    first = rows[0]
    signal_rows = [row for row in rows if int(row.get("pass_truth", 0)) == 1]
    signal_theta = [float(row["theta_deg"]) for row in signal_rows]
    side_counts = {"left": 0, "right": 0, "unknown": 0}
    signal_side_counts = {"left": 0, "right": 0, "unknown": 0}

    for row in rows:
        side_counts[truth_side(row)] += 1
    for row in signal_rows:
        signal_side_counts[truth_side(row)] += 1

    return {
        "run_tag": first["run_tag"],
        "event_index": int(first["event_index"]),
        "event_number": int(first["event_number"]),
        "event_weight": first["event_weight"],
        "particle": first["particle"],
        "particle_pid": first["particle_pid"],
        "momentum_mev": first["momentum_mev"],
        "n_truth_candidates": len(rows),
        "n_signal_truth_candidates": len(signal_rows),
        "n_pass_sps_side_truth_hint": sum(int(row.get("pass_sps_side_truth_hint", 0)) == 1 for row in rows),
        "n_truth_left": side_counts["left"],
        "n_truth_right": side_counts["right"],
        "n_truth_unknown": side_counts["unknown"],
        "n_signal_truth_left": signal_side_counts["left"],
        "n_signal_truth_right": signal_side_counts["right"],
        "n_signal_truth_unknown": signal_side_counts["unknown"],
        "signal_theta_min_deg": min(signal_theta) if signal_theta else None,
        "signal_theta_max_deg": max(signal_theta) if signal_theta else None,
        "signal_theta_mean_deg": mean(signal_theta),
    }


def label_status_for(summary, events_by_key):
    final_count = summary.get("counts", {}).get("final_accepted_count") or 0
    if float(final_count) == 0.0:
        return "exact_negative_zero_final_count"
    if events_by_key:
        return "event_level_cs_events"
    raise RuntimeError(
        "cannot build event-level labels without accepted CS event rows when final count is nonzero"
    )


def build_training_rows(truth_rows, events_by_key, label_status):
    grouped_truth = group_truth_by_event(truth_rows)
    training_rows = []
    for key in sorted(grouped_truth):
        accepted_events = events_by_key.get(key, [])
        output = summarize_truth_event(grouped_truth[key])
        output["accepted_event"] = int(bool(accepted_events)) if label_status != "aggregate_only_no_event_match" else -1
        output["n_accepted_cs_events"] = len(accepted_events)
        output["label_status"] = label_status
        output.update(event_features(accepted_events[0] if accepted_events else None))
        training_rows.append(output)
    return training_rows


def write_csv(path, rows, columns):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path, rows):
    import pandas as pd

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def main() -> int:
    args = parse_args()
    reported_output_csv = args.reported_output_csv or args.output_csv
    reported_output_parquet = args.reported_output_parquet or args.output_parquet
    reported_output_summary_json = (
        args.reported_output_summary_json or args.output_summary_json
    )

    with open(args.summary_json) as json_file:
        summary = json.load(json_file)

    truth_rows = read_tree_rows(args.hazard_truth_root, "hazard_truth", BASE_COLUMNS)
    events_by_key = read_events_by_event(args.events_csv)
    label_status = label_status_for(summary, events_by_key)
    training_rows = build_training_rows(truth_rows, events_by_key, label_status)

    write_csv(args.output_csv, training_rows, TRAINING_COLUMNS)
    write_parquet(args.output_parquet, training_rows)
    write_parquet(args.hazard_truth_parquet, truth_rows)

    accepted_event_rows = sum(row["accepted_event"] == 1 for row in training_rows)
    accepted_cs_rows = sum(row["n_accepted_cs_events"] for row in training_rows)
    output_summary = dict(summary)
    output_summary["training_table"] = {
        "unit": "event",
        "event_rows": len(training_rows),
        "accepted_event_rows": accepted_event_rows,
        "accepted_cs_event_rows": accepted_cs_rows,
        "label_status": label_status,
        "training_csv": reported_output_csv,
        "training_parquet": reported_output_parquet,
        "hazard_truth_parquet": args.hazard_truth_parquet,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output_summary_json)), exist_ok=True)
    with open(args.output_summary_json, "w") as json_file:
        json.dump(output_summary, json_file, indent=2, sort_keys=True)
        json_file.write("\n")

    print(f"Wrote {len(training_rows)} event-level training rows")
    print(f"Accepted event rows: {accepted_event_rows}")
    print(f"Accepted CS rows:    {accepted_cs_rows}")
    print(f"Training CSV:        {reported_output_csv}")
    print(f"Training Parquet:    {reported_output_parquet}")
    print(f"Summary JSON:        {reported_output_summary_json}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
