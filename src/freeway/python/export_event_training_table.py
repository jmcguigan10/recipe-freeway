#!/usr/bin/env python
import argparse
import csv
import json
import math
import os
import sys

import ROOT


SIDE_NAMES = {0: "left", 1: "right"}
SIDE_VALUES = {"left": 0, "right": 1, "unknown": -1}

TRUTH_COLUMNS = (
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
    "truth_theta_min_deg",
    "truth_theta_max_deg",
    "truth_theta_mean_deg",
    "signal_theta_min_deg",
    "signal_theta_max_deg",
    "signal_theta_mean_deg",
    "signal_vertex_x_mean_mm",
    "signal_vertex_y_mean_mm",
    "signal_vertex_z_mean_mm",
    "signal_side_mode",
    "signal_side_mode_id",
)

LABEL_COLUMNS = (
    "accepted_event",
    "accepted_cs",
    "n_accepted_cs_events",
    "label_status",
)

DETECTOR_COLUMNS = (
    "bh_n_hits",
    "bh_n_intime_hits",
    "bh_n_bhc_intime_hits",
    "bh_n_bhd_intime_hits",
    "bh_has_bhc",
    "bh_has_bhd",
    "bh_single_bhc",
    "bh_single_bhd",
    "bh_bhc_bar",
    "bh_bhd_bar",
    "bh_tof_ns",
    "bh_signal_pid_hit",
    "bm_n_hits",
    "bm_n_intime_hits",
    "bm_hit",
    "sps_n_hits",
    "sps_n_intime_hits",
    "sps_left_front_intime_hits",
    "sps_left_rear_intime_hits",
    "sps_right_front_intime_hits",
    "sps_right_rear_intime_hits",
    "sps_lut5_left",
    "sps_lut5_right",
    "sps_lut5_any",
    "veto_n_hits",
    "veto_n_intime_hits",
    "veto_hit",
    "tcpv_n_hits",
    "tcpv_n_intime_hits",
    "tcpv_hit",
    "gem_n_tracks",
    "pbglass_scint_is_hit",
    "pbglass_is_high_e_event",
    "pbglass_n_bar_sum",
    "pbglass_energy",
    "path_all_n_vertices",
    "path_signal_n_vertices",
    "path_signal_n_left_vertices",
    "path_signal_n_right_vertices",
    "path_signal_n_intime_tof",
    "path_signal_n_decay",
    "path_signal_n_not_decay",
    "path_signal_n_good_doca",
    "path_signal_n_target_vertex",
    "path_signal_min_doca_mm",
    "path_signal_theta_min_deg",
    "path_signal_theta_max_deg",
    "path_signal_theta_mean_deg",
)

OUTPUT_COLUMNS = TRUTH_COLUMNS + LABEL_COLUMNS + DETECTOR_COLUMNS

LUT5_MAP = {
    0: {0, 1, 2, 3, 4},
    1: {1, 2, 3, 4, 5, 6},
    2: {2, 3, 4, 5, 6, 7},
    3: {4, 5, 6, 7, 8},
    4: {5, 6, 7, 8, 9, 10},
    5: {6, 7, 8, 9, 10, 11},
    6: {8, 9, 10, 11, 12},
    7: {9, 10, 11, 12, 13, 14},
    8: {11, 12, 13, 14, 15},
    9: {12, 13, 14, 15, 16},
    10: {13, 14, 15, 16, 17, 18},
    11: {15, 16, 17, 18, 19},
    12: {16, 17, 18, 19, 20, 21},
    13: {17, 18, 19, 20, 21, 22},
    14: {19, 20, 21, 22, 23},
    15: {20, 21, 22, 23, 24, 25},
    16: {21, 22, 23, 24, 25, 26},
    17: {23, 24, 25, 26, 27},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export one event-level row per saved event for ML acceptance models."
    )
    parser.add_argument("--hazard-truth-root", required=True)
    parser.add_argument("--events-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--output-parquet", required=True)
    parser.add_argument("--output-summary-json", required=True)
    parser.add_argument("--summary-json")
    parser.add_argument("--run-tag")
    parser.add_argument("--target-pid", type=int)
    parser.add_argument("--bh-root")
    parser.add_argument("--bm-root")
    parser.add_argument("--sps-root")
    parser.add_argument("--veto-root")
    parser.add_argument("--tcpv-root")
    parser.add_argument("--gem-tracks-root")
    parser.add_argument("--pbglass-root")
    parser.add_argument("--pathlength-root")
    return parser.parse_args()


def load_root_dictionaries() -> None:
    for lib in (
        "libmusetree",
        "libBH",
        "libBM",
        "libSPS",
        "libVETO",
        "libTCPV",
        "libGEM_cmin",
        "libPbGlass",
        "libPathLength",
        "libVertexRecon",
    ):
        try:
            ROOT.gSystem.Load(lib)
        except Exception:
            pass


def open_root(path):
    root_file = ROOT.TFile.Open(path, "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open ROOT file: {path}")
    return root_file


def get_tree(path, tree_name):
    root_file = open_root(path)
    tree = root_file.Get(tree_name)
    if not tree or not tree.InheritsFrom("TTree"):
        root_file.Close()
        raise RuntimeError(f"Missing {tree_name} tree: {path}")
    return root_file, tree


def finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def nullable_float(value):
    try:
        result = float(value)
    except Exception:
        return None
    return result if math.isfinite(result) else None


def nullable_int(value):
    try:
        result = int(float(value))
    except Exception:
        return None
    return result


def mean(values):
    values = [float(value) for value in values if finite(value)]
    return sum(values) / len(values) if values else None


def min_or_none(values):
    values = [float(value) for value in values if finite(value)]
    return min(values) if values else None


def max_or_none(values):
    values = [float(value) for value in values if finite(value)]
    return max(values) if values else None


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


def event_key_from_values(event_index, event_number):
    event_index = nullable_int(event_index)
    event_number = nullable_int(event_number)
    if event_index is None or event_number is None:
        return None
    return (event_index, event_number)


def event_key_from_tree(tree, event_index):
    event_number = event_index
    try:
        event_number = int(tree.EventInfo.eventNumber)
    except Exception:
        pass
    return event_key_from_values(event_index, event_number)


def side_name(side):
    side = str(side or "unknown").strip().lower()
    return side if side in SIDE_VALUES else "unknown"


def mode_side(rows):
    counts = {"left": 0, "right": 0, "unknown": 0}
    for row in rows:
        counts[side_name(row.get("side"))] += 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0][0] if ordered and ordered[0][1] > 0 else "unknown"


def blank_detector_features():
    return {column: None for column in DETECTOR_COLUMNS}


def truth_side_counts(rows):
    counts = {"left": 0, "right": 0, "unknown": 0}
    for row in rows:
        counts[side_name(row.get("side"))] += 1
    return counts


def summarize_truth_rows(rows, target_pid):
    first = rows[0]
    if target_pid is None:
        signal_rows = [row for row in rows if nullable_int(row.get("pass_truth")) == 1]
    else:
        signal_rows = [row for row in rows if nullable_int(row.get("particle_pid")) == target_pid]
    truth_counts = truth_side_counts(rows)
    signal_counts = truth_side_counts(signal_rows)
    truth_theta = [row.get("theta_deg") for row in rows]
    signal_theta = [row.get("theta_deg") for row in signal_rows]
    signal_side = mode_side(signal_rows)

    return {
        "run_tag": first.get("run_tag"),
        "event_index": nullable_int(first.get("event_index")),
        "event_number": nullable_int(first.get("event_number")),
        "event_weight": nullable_float(first.get("event_weight")),
        "particle": first.get("particle"),
        "particle_pid": target_pid if target_pid is not None else nullable_int(first.get("particle_pid")),
        "momentum_mev": nullable_float(first.get("momentum_mev")),
        "n_truth_candidates": len(rows),
        "n_signal_truth_candidates": len(signal_rows),
        "n_pass_sps_side_truth_hint": sum(nullable_int(row.get("pass_sps_side_truth_hint")) == 1 for row in rows),
        "n_truth_left": truth_counts["left"],
        "n_truth_right": truth_counts["right"],
        "n_truth_unknown": truth_counts["unknown"],
        "n_signal_truth_left": signal_counts["left"],
        "n_signal_truth_right": signal_counts["right"],
        "n_signal_truth_unknown": signal_counts["unknown"],
        "truth_theta_min_deg": min_or_none(truth_theta),
        "truth_theta_max_deg": max_or_none(truth_theta),
        "truth_theta_mean_deg": mean(truth_theta),
        "signal_theta_min_deg": min_or_none(signal_theta),
        "signal_theta_max_deg": max_or_none(signal_theta),
        "signal_theta_mean_deg": mean(signal_theta),
        "signal_vertex_x_mean_mm": mean(row.get("vertex_x_mm") for row in signal_rows),
        "signal_vertex_y_mean_mm": mean(row.get("vertex_y_mm") for row in signal_rows),
        "signal_vertex_z_mean_mm": mean(row.get("vertex_z_mm") for row in signal_rows),
        "signal_side_mode": signal_side,
        "signal_side_mode_id": SIDE_VALUES[signal_side],
    }


def read_hazard_truth(path, target_pid):
    root_file, tree = get_tree(path, "hazard_truth")
    columns = (
        "run_tag",
        "event_number",
        "event_index",
        "event_weight",
        "particle",
        "particle_pid",
        "momentum_mev",
        "theta_deg",
        "vertex_x_mm",
        "vertex_y_mm",
        "vertex_z_mm",
        "side",
        "pass_truth",
        "pass_sps_side_truth_hint",
    )
    grouped = {}
    inferred_target_pid = target_pid
    for row in tree:
        item = {column: scalar(row, column) for column in columns}
        if inferred_target_pid is None and nullable_int(item.get("pass_truth")) == 1:
            inferred_target_pid = nullable_int(item.get("particle_pid"))
        key = event_key_from_values(item.get("event_index"), item.get("event_number"))
        if key is not None:
            grouped.setdefault(key, []).append(item)
    root_file.Close()
    if inferred_target_pid is None:
        raise RuntimeError("Could not infer target pid; pass --target-pid")
    rows_by_key = {
        key: summarize_truth_rows(rows, inferred_target_pid)
        for key, rows in grouped.items()
    }
    return rows_by_key, inferred_target_pid


def read_accepted_events(path):
    accepted = {}
    with open(path, newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            key = event_key_from_values(row.get("event_index"), row.get("event_number"))
            if key is not None:
                accepted.setdefault(key, []).append(row)
    return accepted


def vector_size(value):
    if value is None:
        return 0
    try:
        return int(value.size())
    except Exception:
        pass
    try:
        return len(value)
    except Exception:
        return 0


def hit_intime_count(hit):
    try:
        return int(hit.tdc_hits[0].size())
    except Exception:
        pass
    try:
        return int(hit.tdc_hits_in.size())
    except Exception:
        return 0


def first_tdc(hit):
    try:
        if hit.tdc_hits[0].size() > 0:
            return hit.tdc_hits[0][0]
    except Exception:
        pass
    return None


def tdc_pid_matches(tdc, target_pid):
    if tdc is None or target_pid is None:
        return False
    for index in (0, 1):
        try:
            if abs(int(tdc.pid[index])) == abs(int(target_pid)):
                return True
        except Exception:
            pass
    return False


def scint_hits_features(hits, prefix):
    n_hits = vector_size(getattr(hits, "hits", None))
    n_intime = 0
    for i in range(n_hits):
        try:
            n_intime += int(hit_intime_count(hits.hits[i]) > 0)
        except Exception:
            pass
    return {
        f"{prefix}_n_hits": n_hits,
        f"{prefix}_n_intime_hits": n_intime,
        f"{prefix}_hit": int(n_intime > 0),
    }


def bh_features(tree, target_pid):
    hits = tree.BH_Hits
    n_hits = vector_size(hits.hits)
    n_intime = 0
    bhc_hits = []
    bhd_hits = []
    signal_pid_hit = False
    for i in range(n_hits):
        hit = hits.hits[i]
        if hit_intime_count(hit) <= 0:
            continue
        n_intime += 1
        wall = nullable_int(hit.wall_id)
        if wall == 2:
            bhc_hits.append(hit)
        elif wall == 3:
            bhd_hits.append(hit)
            signal_pid_hit = signal_pid_hit or tdc_pid_matches(first_tdc(hit), target_pid)
    bhc_bar = nullable_int(bhc_hits[0].bar_id) if len(bhc_hits) == 1 else None
    bhd_bar = nullable_int(bhd_hits[0].bar_id) if len(bhd_hits) == 1 else None
    bh_tof = None
    if len(bhc_hits) == 1 and len(bhd_hits) == 1:
        bhc_tdc = first_tdc(bhc_hits[0])
        bhd_tdc = first_tdc(bhd_hits[0])
        try:
            bh_tof = float(bhd_tdc.meantime) - float(bhc_tdc.meantime)
        except Exception:
            bh_tof = None
    return {
        "bh_n_hits": n_hits,
        "bh_n_intime_hits": n_intime,
        "bh_n_bhc_intime_hits": len(bhc_hits),
        "bh_n_bhd_intime_hits": len(bhd_hits),
        "bh_has_bhc": int(len(bhc_hits) > 0),
        "bh_has_bhd": int(len(bhd_hits) > 0),
        "bh_single_bhc": int(len(bhc_hits) == 1),
        "bh_single_bhd": int(len(bhd_hits) == 1),
        "bh_bhc_bar": bhc_bar,
        "bh_bhd_bar": bhd_bar,
        "bh_tof_ns": bh_tof,
        "bh_signal_pid_hit": int(signal_pid_hit),
    }


def lut5(front_bars, rear_bars):
    for front in front_bars:
        allowed = LUT5_MAP.get(front, set())
        if any(rear in allowed for rear in rear_bars):
            return 1
    return 0


def sps_features(tree):
    hits = tree.SPS_Hits
    n_hits = vector_size(hits.hits)
    n_intime = 0
    by_wall = {0: [], 1: [], 2: [], 3: []}
    for i in range(n_hits):
        hit = hits.hits[i]
        if hit_intime_count(hit) <= 0:
            continue
        n_intime += 1
        wall = nullable_int(hit.wall_id)
        bar = nullable_int(hit.bar_id)
        if wall in by_wall and bar is not None:
            by_wall[wall].append(bar)
    lut5_left = lut5(by_wall[0], by_wall[2])
    lut5_right = lut5(by_wall[1], by_wall[3])
    return {
        "sps_n_hits": n_hits,
        "sps_n_intime_hits": n_intime,
        "sps_left_front_intime_hits": len(by_wall[0]),
        "sps_left_rear_intime_hits": len(by_wall[2]),
        "sps_right_front_intime_hits": len(by_wall[1]),
        "sps_right_rear_intime_hits": len(by_wall[3]),
        "sps_lut5_left": lut5_left,
        "sps_lut5_right": lut5_right,
        "sps_lut5_any": int(bool(lut5_left or lut5_right)),
    }


def gem_features(tree):
    try:
        return {"gem_n_tracks": int(tree.Tracks.tracks.size())}
    except Exception:
        return {"gem_n_tracks": None}


def pbglass_features(tree):
    try:
        hit = tree.PbGlass_Hit
    except Exception:
        return {}
    return {
        "pbglass_scint_is_hit": int(bool(getattr(hit, "scint_is_hit", False))),
        "pbglass_is_high_e_event": int(bool(getattr(hit, "is_high_e_event", False))),
        "pbglass_n_bar_sum": nullable_int(getattr(hit, "n_bar_sum", None)),
        "pbglass_energy": nullable_float(getattr(hit, "energy", None)),
    }


def vertex_collection_for_pid(tree, target_pid):
    abs_pid = abs(int(target_pid)) if target_pid is not None else 0
    if abs_pid == 11 and hasattr(tree, "eScattering"):
        return tree.eScattering
    if abs_pid == 13 and hasattr(tree, "muScattering"):
        return tree.muScattering
    if abs_pid == 211 and hasattr(tree, "piScattering"):
        return tree.piScattering
    if hasattr(tree, "allScattering"):
        return tree.allScattering
    return None


def pathlength_features(tree, target_pid):
    try:
        all_vertices = tree.allScattering.vertex
        n_all = int(all_vertices.size())
    except Exception:
        n_all = None
    collection = vertex_collection_for_pid(tree, target_pid)
    if collection is None:
        return {"path_all_n_vertices": n_all}
    vertices = collection.vertex
    n_vertices = int(vertices.size())
    theta = []
    doca = []
    n_left = n_right = n_intime = n_decay = n_good_doca = n_target = 0
    for i in range(n_vertices):
        vertex = vertices[i]
        side = nullable_int(getattr(vertex, "side", None))
        n_left += int(side == 0)
        n_right += int(side == 1)
        n_intime += int(bool(getattr(vertex, "is_intime_tof", False)))
        n_decay += int(bool(getattr(vertex, "is_decay", False)))
        is_good_doca = bool(getattr(vertex, "is_good_doca", False))
        try:
            is_good_doca = is_good_doca or float(vertex.doca) < 15.0
        except Exception:
            pass
        n_good_doca += int(is_good_doca)
        n_target += int(bool(getattr(vertex, "is_target_vertex", False)))
        try:
            theta.append(float(vertex.theta) * 180.0 / math.pi)
        except Exception:
            pass
        try:
            doca.append(float(vertex.doca))
        except Exception:
            pass
    return {
        "path_all_n_vertices": n_all,
        "path_signal_n_vertices": n_vertices,
        "path_signal_n_left_vertices": n_left,
        "path_signal_n_right_vertices": n_right,
        "path_signal_n_intime_tof": n_intime,
        "path_signal_n_decay": n_decay,
        "path_signal_n_not_decay": n_vertices - n_decay,
        "path_signal_n_good_doca": n_good_doca,
        "path_signal_n_target_vertex": n_target,
        "path_signal_min_doca_mm": min_or_none(doca),
        "path_signal_theta_min_deg": min_or_none(theta),
        "path_signal_theta_max_deg": max_or_none(theta),
        "path_signal_theta_mean_deg": mean(theta),
    }


def add_tree_features(rows_by_key, path, tree_name, feature_func, target_pid=None):
    if not path:
        return
    root_file, tree = get_tree(path, tree_name)
    entries = int(tree.GetEntries())
    for event_index in range(entries):
        tree.GetEntry(event_index)
        key = event_key_from_tree(tree, event_index)
        if key not in rows_by_key:
            continue
        if target_pid is None:
            rows_by_key[key].update(feature_func(tree))
        else:
            rows_by_key[key].update(feature_func(tree, target_pid))
    root_file.Close()


def attach_labels(rows_by_key, accepted_by_key):
    for key, row in rows_by_key.items():
        accepted_rows = accepted_by_key.get(key, [])
        accepted = int(bool(accepted_rows))
        row["accepted_event"] = accepted
        row["accepted_cs"] = accepted
        row["n_accepted_cs_events"] = len(accepted_rows)
        row["label_status"] = "event_level_cs_events"


def write_csv(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path, rows):
    import pandas as pd

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pd.DataFrame(rows, columns=OUTPUT_COLUMNS).to_parquet(path, index=False)


def read_summary(path):
    if not path:
        return {}
    with open(path) as json_file:
        return json.load(json_file)


def main() -> int:
    args = parse_args()
    ROOT.gROOT.SetBatch(True)
    load_root_dictionaries()

    rows_by_key, target_pid = read_hazard_truth(args.hazard_truth_root, args.target_pid)
    accepted_by_key = read_accepted_events(args.events_csv)
    attach_labels(rows_by_key, accepted_by_key)

    for row in rows_by_key.values():
        for key, value in blank_detector_features().items():
            row.setdefault(key, value)
        if args.run_tag:
            row["run_tag"] = args.run_tag
        row["particle_pid"] = target_pid

    add_tree_features(rows_by_key, args.bh_root, "BH", bh_features, target_pid)
    add_tree_features(rows_by_key, args.bm_root, "BM", lambda tree: scint_hits_features(tree.BM_Hits, "bm"))
    add_tree_features(rows_by_key, args.sps_root, "SPS", sps_features)
    add_tree_features(rows_by_key, args.veto_root, "VETO", lambda tree: scint_hits_features(tree.VETO_Hits, "veto"))
    add_tree_features(rows_by_key, args.tcpv_root, "TCPV", lambda tree: scint_hits_features(tree.TCPV_Hits, "tcpv"))
    add_tree_features(rows_by_key, args.gem_tracks_root, "GEMTracks", gem_features)
    add_tree_features(rows_by_key, args.pbglass_root, "PbGlass", pbglass_features)
    add_tree_features(rows_by_key, args.pathlength_root, "PathLength", pathlength_features, target_pid)

    rows = [rows_by_key[key] for key in sorted(rows_by_key)]
    write_csv(args.output_csv, rows)
    write_parquet(args.output_parquet, rows)

    input_summary = read_summary(args.summary_json)
    output_summary = dict(input_summary)
    output_summary["event_training_table"] = {
        "unit": "event",
        "rows": len(rows),
        "accepted_event_rows": sum(row["accepted_event"] == 1 for row in rows),
        "accepted_cs_event_rows": sum(row["n_accepted_cs_events"] for row in rows),
        "target_pid": target_pid,
        "label_status": "event_level_cs_events",
        "feature_note": "event_weight is for sample_weight; exclude it from model features",
        "training_csv": args.output_csv,
        "training_parquet": args.output_parquet,
        "detector_inputs": {
            "bh_root": args.bh_root,
            "bm_root": args.bm_root,
            "sps_root": args.sps_root,
            "veto_root": args.veto_root,
            "tcpv_root": args.tcpv_root,
            "gem_tracks_root": args.gem_tracks_root,
            "pbglass_root": args.pbglass_root,
            "pathlength_root": args.pathlength_root,
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output_summary_json)), exist_ok=True)
    with open(args.output_summary_json, "w") as json_file:
        json.dump(output_summary, json_file, indent=2, sort_keys=True)
        json_file.write("\n")

    print(f"Wrote {len(rows)} event-level training rows")
    print(f"Accepted event rows: {sum(row['accepted_event'] == 1 for row in rows)}")
    print(f"Accepted CS rows:    {sum(row['n_accepted_cs_events'] for row in rows)}")
    print(f"Target pid:          {target_pid}")
    print(f"Training CSV:        {args.output_csv}")
    print(f"Training Parquet:    {args.output_parquet}")
    print(f"Summary JSON:        {args.output_summary_json}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
