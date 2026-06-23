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

TRAINING_COLUMNS = BASE_COLUMNS + (
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
    "accepted_final",
    "label_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export ML training tables.")
    parser.add_argument("--hazard-truth-root", required=True)
    parser.add_argument("--hazard-cutflow-root", required=True)
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-parquet", required=True)
    parser.add_argument("--output-summary-json", required=True)
    parser.add_argument("--reported-output-csv")
    parser.add_argument("--reported-output-parquet")
    parser.add_argument("--reported-output-summary-json")
    parser.add_argument("--hazard-truth-parquet", required=True)
    parser.add_argument("--hazard-cutflow-parquet", required=True)
    return parser.parse_args()


def scalar(row, name):
    value = getattr(row, name)
    try:
        if isinstance(value, str):
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
        return str(value)


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


def side_from_csv(row):
    side_name = (row.get("side_name") or "").strip().lower()
    if side_name:
        return side_name
    side = (row.get("side") or "").strip()
    return {"0": "left", "1": "right"}.get(side, side.lower() or "unknown")


def event_key(row):
    try:
        return (int(float(row["event_number"])), side_from_csv(row), int(float(row["particle_pid"])))
    except Exception:
        return None


def candidate_key(row):
    try:
        return (int(row["event_number"]), str(row["side"]), int(row["particle_pid"]))
    except Exception:
        return None


def read_events_by_key(path):
    rows_by_key = {}
    with open(path, newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            key = event_key(row)
            if key is not None:
                rows_by_key.setdefault(key, []).append(row)
    return rows_by_key


def final_accept_by_candidate(cutflow_rows):
    labels = {}
    statuses = {}
    for row in cutflow_rows:
        if row["stage_name"] != "final_accept":
            continue
        labels[str(row["candidate_id"])] = int(row["accepted_final"])
        statuses[str(row["candidate_id"])] = str(row["label_status"])
    return labels, statuses


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


def event_features(event):
    if not event:
        return {
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
    return {
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
    cutflow_columns = (
        "candidate_id",
        "stage_name",
        "at_risk",
        "passed",
        "terminated",
        "accepted_final",
        "label_status",
    )
    cutflow_rows = read_tree_rows(args.hazard_cutflow_root, "hazard_cutflow", cutflow_columns)
    accepted_final, label_status = final_accept_by_candidate(cutflow_rows)
    events_by_key = read_events_by_key(args.events_csv)

    training_rows = []
    ambiguous_event_matches = 0
    for row in truth_rows:
        key = candidate_key(row)
        events = events_by_key.get(key, []) if key is not None else []
        event = events[0] if len(events) == 1 else None
        if len(events) > 1:
            ambiguous_event_matches += 1

        output = dict(row)
        output.update(event_features(event))
        candidate_id = str(row["candidate_id"])
        output["accepted_final"] = accepted_final.get(candidate_id, -1)
        output["label_status"] = label_status.get(candidate_id, "missing_final_accept")
        training_rows.append(output)

    if ambiguous_event_matches:
        raise RuntimeError(
            f"ambiguous accepted-event matches for {ambiguous_event_matches} candidates"
        )

    write_csv(args.output_csv, training_rows, TRAINING_COLUMNS)
    write_parquet(args.output_parquet, training_rows)
    write_parquet(args.hazard_truth_parquet, truth_rows)
    write_parquet(args.hazard_cutflow_parquet, cutflow_rows)

    output_summary = dict(summary)
    output_summary["training_table"] = {
        "candidate_rows": len(training_rows),
        "cutflow_rows": len(cutflow_rows),
        "training_csv": reported_output_csv,
        "training_parquet": reported_output_parquet,
        "hazard_truth_parquet": args.hazard_truth_parquet,
        "hazard_cutflow_parquet": args.hazard_cutflow_parquet,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output_summary_json)), exist_ok=True)
    with open(args.output_summary_json, "w") as json_file:
        json.dump(output_summary, json_file, indent=2, sort_keys=True)
        json_file.write("\n")

    print(f"Wrote {len(training_rows)} training candidate rows")
    print(f"Training CSV:     {reported_output_csv}")
    print(f"Training Parquet: {reported_output_parquet}")
    print(f"Summary JSON:     {reported_output_summary_json}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
