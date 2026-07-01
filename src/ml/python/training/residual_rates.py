from __future__ import annotations

from math import isnan

RESIDUAL_RATE_BIN_COLUMNS = ("beam_p_mev", "xprime", "yprime", "path_scale_z")
DEFAULT_RATE_QUANTILE_BINS = 4
DEFAULT_RATE_SMOOTHING = 0.5
DEFAULT_MIN_RATE_BIN_COUNT = 5


def residual_core_rate_tables(
    frame,
    label_names: tuple[str, ...],
    *,
    quantile_bins: int = DEFAULT_RATE_QUANTILE_BINS,
    smoothing: float = DEFAULT_RATE_SMOOTHING,
    min_bin_count: int = DEFAULT_MIN_RATE_BIN_COUNT,
):
    import numpy as np
    import pandas as pd

    if quantile_bins <= 0:
        raise ValueError(f"quantile_bins must be positive: {quantile_bins}")
    if smoothing < 0.0:
        raise ValueError(f"smoothing must be non-negative: {smoothing}")
    if min_bin_count <= 0:
        raise ValueError(f"min_bin_count must be positive: {min_bin_count}")

    metric_rows = []
    rate_rows = []
    for label in label_names:
        if not label.startswith("residual_miss_"):
            continue
        detector = _detector_for_label(label)
        if detector is None:
            continue
        core = _core_frame_for_label(frame, label, detector)
        if core.empty:
            metric_rows.append(_empty_metric_row(label, detector))
            continue

        target = core[f"target__{label}"].to_numpy(dtype=float)
        model_score = core[f"prob__{label}"].to_numpy(dtype=float)
        rate_table, baseline_score = _fit_rate_table(
            core,
            label,
            detector,
            quantile_bins=quantile_bins,
            smoothing=smoothing,
            min_bin_count=min_bin_count,
            pd=pd,
            np=np,
        )
        rate_rows.extend(rate_table)
        metric_rows.append(
            {
                "label": label,
                "detector": detector,
                "regime": "core",
                "count": int(target.size),
                "positives": int(target.sum()),
                "base_rate": float(target.mean()) if target.size else float("nan"),
                "model_mean_probability": float(model_score.mean()) if target.size else float("nan"),
                "model_average_precision": average_precision(model_score, target, np=np),
                "model_brier": brier_score(model_score, target, np=np),
                "model_expected_calibration_error": expected_calibration_error(model_score, target, np=np),
                "model_top_0_1pct_lift": top_fraction_lift(model_score, target, 0.001, np=np),
                "rate_baseline_mean_probability": float(baseline_score.mean()) if target.size else float("nan"),
                "rate_baseline_average_precision": average_precision(baseline_score, target, np=np),
                "rate_baseline_brier": brier_score(baseline_score, target, np=np),
                "rate_baseline_expected_calibration_error": expected_calibration_error(baseline_score, target, np=np),
                "rate_baseline_top_0_1pct_lift": top_fraction_lift(baseline_score, target, 0.001, np=np),
            }
        )

    return pd.DataFrame(metric_rows), pd.DataFrame(rate_rows)


def _core_frame_for_label(frame, label: str, detector: str):
    regime_col = f"regime__{label}"
    if regime_col in frame.columns:
        return frame[frame[regime_col] == "core"].copy()

    core_col = f"geom_core_{detector}"
    if core_col in frame.columns:
        return frame[frame[core_col] > 0.5].copy()

    return frame.iloc[0:0].copy()


def _fit_rate_table(
    core,
    label: str,
    detector: str,
    *,
    quantile_bins: int,
    smoothing: float,
    min_bin_count: int,
    pd,
    np,
):
    target_col = f"target__{label}"
    working = core.copy()
    bin_columns = []
    for column in RESIDUAL_RATE_BIN_COLUMNS:
        if column not in working.columns:
            continue
        series = working[column]
        if series.nunique(dropna=True) <= 1:
            continue
        bin_column = f"{column}_bin"
        try:
            candidate = pd.qcut(series, q=quantile_bins, labels=False, duplicates="drop")
        except ValueError:
            continue
        if candidate.nunique(dropna=True) <= 1:
            continue
        working[bin_column] = candidate
        candidate_columns = [*bin_columns, bin_column]
        counts = working.groupby(candidate_columns, dropna=False, observed=True).size()
        if not counts.empty and int(counts.min()) >= min_bin_count:
            bin_columns.append(bin_column)
        else:
            working = working.drop(columns=[bin_column])

    if not bin_columns:
        working["phase_space_bin"] = 0
        bin_columns = ["phase_space_bin"]

    group_keys = ["label", "detector", *bin_columns]
    working["label"] = label
    working["detector"] = detector
    grouped = working.groupby(group_keys, dropna=False, observed=True)

    rate_by_key = {}
    rows = []
    for key, group in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        key_map = dict(zip(group_keys, key))
        count = int(len(group))
        positives = int(group[target_col].sum())
        estimate = (positives + smoothing) / (count + 2.0 * smoothing)
        rate_by_key[tuple(key_map[column] for column in bin_columns)] = estimate
        row = {
            "label": label,
            "detector": detector,
            "count": count,
            "positives": positives,
            "observed_rate": positives / max(count, 1),
            "rate_estimate": estimate,
            "smoothing": float(smoothing),
        }
        for column in bin_columns:
            source = column.removesuffix("_bin")
            row[column] = key_map[column]
            if source in group.columns:
                row[f"{source}_min"] = float(group[source].min())
                row[f"{source}_max"] = float(group[source].max())
        rows.append(row)

    baseline = np.asarray(
        [rate_by_key[tuple(row[column] for column in bin_columns)] for _, row in working.iterrows()],
        dtype=float,
    )
    return rows, baseline


def average_precision(scores, targets, *, np) -> float:
    targets = (np.asarray(targets) > 0.5).astype(float)
    positives = float(targets.sum())
    if positives <= 0.0:
        return float("nan")
    order = np.argsort(-np.asarray(scores), kind="mergesort")
    sorted_targets = targets[order]
    true_positive = np.cumsum(sorted_targets)
    ranks = np.arange(1, sorted_targets.size + 1, dtype=float)
    return float((true_positive / ranks * sorted_targets).sum() / positives)


def brier_score(scores, targets, *, np) -> float:
    scores = np.asarray(scores, dtype=float)
    targets = np.asarray(targets, dtype=float)
    if scores.size == 0:
        return float("nan")
    return float(np.mean((scores - targets) ** 2))


def expected_calibration_error(scores, targets, *, np, bins: int = 10) -> float:
    scores = np.asarray(scores, dtype=float)
    targets = np.asarray(targets, dtype=float)
    if scores.size == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for index in range(bins):
        lower = edges[index]
        upper = edges[index + 1]
        if index == bins - 1:
            mask = (scores >= lower) & (scores <= upper)
        else:
            mask = (scores >= lower) & (scores < upper)
        if mask.any():
            total += float(mask.mean() * abs(scores[mask].mean() - targets[mask].mean()))
    return total


def top_fraction_lift(scores, targets, fraction: float, *, np) -> float:
    scores = np.asarray(scores, dtype=float)
    targets = np.asarray(targets, dtype=float)
    if scores.size == 0:
        return float("nan")
    base = float(targets.mean())
    if base <= 0.0 or isnan(base):
        return float("nan")
    n = max(1, int(round(scores.size * fraction)))
    order = np.argsort(-scores, kind="mergesort")[:n]
    return float(targets[order].mean() / base)


def _empty_metric_row(label: str, detector: str) -> dict[str, float | int | str]:
    return {
        "label": label,
        "detector": detector,
        "regime": "core",
        "count": 0,
        "positives": 0,
        "base_rate": float("nan"),
        "model_mean_probability": float("nan"),
        "model_average_precision": float("nan"),
        "model_brier": float("nan"),
        "model_expected_calibration_error": float("nan"),
        "model_top_0_1pct_lift": float("nan"),
        "rate_baseline_mean_probability": float("nan"),
        "rate_baseline_average_precision": float("nan"),
        "rate_baseline_brier": float("nan"),
        "rate_baseline_expected_calibration_error": float("nan"),
        "rate_baseline_top_0_1pct_lift": float("nan"),
    }


def _detector_for_label(label: str) -> str | None:
    for detector in ("bhc", "bhd", "gem0"):
        if detector in label:
            return detector
    return None
