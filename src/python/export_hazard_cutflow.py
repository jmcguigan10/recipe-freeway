#!/usr/bin/env python
import argparse
import csv
import json
import os
import sys
from array import array

import ROOT


HAZARD_STAGES = (
    "truth",
    "sps_side",
    "no_veto",
    "bh_pid",
    "lut5",
    "gem_track",
    "tracklet",
    "vertex",
    "tof",
    "not_decay_or_rid",
    "calo",
    "doca",
    "final_accept",
)

STRING_COLUMNS = (
    "candidate_id",
    "run_tag",
    "stage_name",
    "fail_reason",
    "side",
    "particle",
    "label_status",
)
INT_COLUMNS = (
    "event_number",
    "event_index",
    "target_index",
    "stage_order",
    "at_risk",
    "passed",
    "terminated",
    "theta_bin",
    "particle_pid",
    "accepted_final",
)
DOUBLE_COLUMNS = ("event_weight", "theta_deg", "momentum_mev")
OUTPUT_COLUMNS = (
    "candidate_id",
    "run_tag",
    "event_number",
    "event_index",
    "target_index",
    "stage_order",
    "stage_name",
    "at_risk",
    "passed",
    "terminated",
    "fail_reason",
    "event_weight",
    "theta_deg",
    "theta_bin",
    "side",
    "particle",
    "particle_pid",
    "momentum_mev",
    "accepted_final",
    "label_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export long-form hazard cutflow.")
    parser.add_argument("--hazard-truth-root", required=True)
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--reported-output-root")
    parser.add_argument("--reported-output-csv")
    return parser.parse_args()


def create_output_tree():
    tree = ROOT.TTree("hazard_cutflow", "hazard_cutflow")
    string_buffers = {name: ROOT.std.string() for name in STRING_COLUMNS}
    int_buffers = {name: array("i", [0]) for name in INT_COLUMNS}
    double_buffers = {name: array("d", [0.0]) for name in DOUBLE_COLUMNS}

    for name, buffer in string_buffers.items():
        tree.Branch(name, buffer)
    for name, buffer in int_buffers.items():
        tree.Branch(name, buffer, f"{name}/I")
    for name, buffer in double_buffers.items():
        tree.Branch(name, buffer, f"{name}/D")

    return tree, string_buffers, int_buffers, double_buffers


def fill_tree(tree, string_buffers, int_buffers, double_buffers, row):
    for name, buffer in string_buffers.items():
        buffer.assign(str(row[name]))
    for name, buffer in int_buffers.items():
        buffer[0] = int(row[name])
    for name, buffer in double_buffers.items():
        buffer[0] = float(row[name])
    tree.Fill()


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


def read_hazard_truth(path):
    root_file = ROOT.TFile.Open(path, "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open hazard truth ROOT: {path}")
    tree = root_file.Get("hazard_truth")
    if not tree or not tree.InheritsFrom("TTree"):
        root_file.Close()
        raise RuntimeError(f"Missing hazard_truth tree: {path}")

    rows = []
    for row in tree:
        rows.append(
            {
                "candidate_id": str(row.candidate_id),
                "run_tag": str(row.run_tag),
                "event_number": scalar(row, "event_number"),
                "event_index": scalar(row, "event_index"),
                "target_index": scalar(row, "target_index"),
                "event_weight": scalar(row, "event_weight"),
                "theta_deg": scalar(row, "theta_deg"),
                "theta_bin": scalar(row, "theta_bin"),
                "side": str(row.side),
                "particle": str(row.particle),
                "particle_pid": scalar(row, "particle_pid"),
                "momentum_mev": scalar(row, "momentum_mev"),
                "pass_truth": scalar(row, "pass_truth"),
                "pass_sps_side_truth_hint": scalar(row, "pass_sps_side_truth_hint"),
            }
        )
    root_file.Close()
    return rows


def side_from_csv(row):
    side_name = (row.get("side_name") or "").strip().lower()
    if side_name:
        return side_name
    side = (row.get("side") or "").strip()
    return {"0": "left", "1": "right"}.get(side, side.lower() or "unknown")


def candidate_key(row):
    try:
        return (int(row["event_number"]), str(row["side"]), int(row["particle_pid"]))
    except Exception:
        return None


def event_key(row):
    try:
        return (int(float(row["event_number"])), side_from_csv(row), int(float(row["particle_pid"])))
    except Exception:
        return None


def accepted_candidate_ids(truth_rows, events_csv, summary):
    final_count = summary.get("counts", {}).get("final_accepted_count") or 0
    if float(final_count) == 0.0:
        return set(), "exact_negative_zero_final_count"

    with open(events_csv, newline="") as csv_file:
        event_rows = list(csv.DictReader(csv_file))
    if not event_rows:
        return set(), "aggregate_only_no_candidate_match"

    candidates_by_key = {}
    for row in truth_rows:
        key = candidate_key(row)
        if key is not None:
            candidates_by_key.setdefault(key, []).append(row["candidate_id"])

    accepted = set()
    ambiguous = []
    missing = []
    for row in event_rows:
        key = event_key(row)
        matches = candidates_by_key.get(key, []) if key is not None else []
        if len(matches) == 1:
            accepted.add(matches[0])
        elif len(matches) == 0:
            missing.append(str(key))
        else:
            ambiguous.append(str(key))

    if ambiguous or missing:
        details = []
        if ambiguous:
            details.append(f"ambiguous:{len(ambiguous)}")
        if missing:
            details.append(f"missing:{len(missing)}")
        return set(), f"candidate_join_not_exact_{'_'.join(details)}"

    return accepted, "cs_events_exact_candidate_join"


def make_stage_row(base, stage_order, stage_name, at_risk, passed, terminated, fail_reason):
    output = {
        key: base[key]
        for key in (
            "candidate_id",
            "run_tag",
            "event_number",
            "event_index",
            "target_index",
            "event_weight",
            "theta_deg",
            "theta_bin",
            "side",
            "particle",
            "particle_pid",
            "momentum_mev",
            "accepted_final",
            "label_status",
        )
    }
    output.update(
        {
            "stage_order": stage_order,
            "stage_name": stage_name,
            "at_risk": int(at_risk),
            "passed": int(passed),
            "terminated": int(terminated),
            "fail_reason": fail_reason,
        }
    )
    return output


def stage_rows(truth_row, accepted_ids, label_status):
    accepted_final = int(truth_row["candidate_id"] in accepted_ids)
    exact_label = label_status in (
        "exact_negative_zero_final_count",
        "cs_events_exact_candidate_join",
    )
    base = dict(truth_row)
    base["accepted_final"] = accepted_final if exact_label else -1
    base["label_status"] = label_status

    pass_truth = int(truth_row["pass_truth"] == 1)
    pass_side = int(truth_row["pass_sps_side_truth_hint"] == 1)
    current_at_risk = 1

    first = make_stage_row(
        base,
        0,
        "truth",
        1,
        pass_truth,
        int(not pass_truth),
        "" if pass_truth else "truth_pid_mismatch",
    )
    yield first
    current_at_risk = int(pass_truth)

    second = make_stage_row(
        base,
        1,
        "sps_side",
        current_at_risk,
        pass_side if current_at_risk else 0,
        int(current_at_risk and not pass_side),
        ""
        if current_at_risk and pass_side
        else ("not_at_risk" if not current_at_risk else "unknown_or_ambiguous_sps_side"),
    )
    yield second
    current_at_risk = int(current_at_risk and pass_side)

    for stage_order, stage_name in enumerate(HAZARD_STAGES[2:-1], start=2):
        if not current_at_risk:
            passed = 0
            terminated = 0
            reason = "not_at_risk"
        elif accepted_final:
            passed = 1
            terminated = 0
            reason = ""
        else:
            passed = -1
            terminated = 0
            reason = "not_evaluated"
        yield make_stage_row(
            base, stage_order, stage_name, current_at_risk, passed, terminated, reason
        )

    final_order = len(HAZARD_STAGES) - 1
    if not current_at_risk:
        final_passed = 0
        final_terminated = 0
        final_reason = "not_at_risk"
    elif not exact_label:
        final_passed = -1
        final_terminated = 0
        final_reason = "aggregate_only_no_candidate_match"
    elif accepted_final:
        final_passed = 1
        final_terminated = 0
        final_reason = ""
    else:
        final_passed = 0
        final_terminated = 1
        final_reason = "not_final_accepted"
    yield make_stage_row(
        base,
        final_order,
        "final_accept",
        current_at_risk,
        final_passed,
        final_terminated,
        final_reason,
    )


def main() -> int:
    args = parse_args()
    ROOT.gROOT.SetBatch(True)
    reported_output_root = args.reported_output_root or args.output_root
    reported_output_csv = args.reported_output_csv or args.output_csv

    with open(args.summary_json) as json_file:
        summary = json.load(json_file)

    truth_rows = read_hazard_truth(args.hazard_truth_root)
    accepted_ids, label_status = accepted_candidate_ids(
        truth_rows, args.events_csv, summary
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.output_root)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)

    output_file = ROOT.TFile(args.output_root, "RECREATE")
    output_tree, string_buffers, int_buffers, double_buffers = create_output_tree()
    row_count = 0

    with open(args.output_csv, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for truth_row in truth_rows:
            for output_row in stage_rows(truth_row, accepted_ids, label_status):
                fill_tree(output_tree, string_buffers, int_buffers, double_buffers, output_row)
                writer.writerow(output_row)
                row_count += 1

    output_file.cd()
    output_tree.Write()
    output_file.Close()

    print(f"Wrote {row_count} hazard cutflow rows")
    print(f"ROOT output: {reported_output_root}")
    print(f"CSV output:  {reported_output_csv}")
    print(f"Label status: {label_status}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
