from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, Subset

from .calibration import PlattCalibrator
from .metrics import calibrated_probability_logits
from .residual_rates import (
    DEFAULT_MIN_RATE_BIN_COUNT,
    DEFAULT_RATE_QUANTILE_BINS,
    RESIDUAL_RATE_BIN_COLUMNS,
    residual_core_rate_tables,
)


TOPK_FRACTIONS = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05)
REGIME_ORDER = ("outside", "edge", "near", "core")


def check_plot_dependencies() -> None:
    missing = []
    for module_name in ("matplotlib", "numpy", "pandas"):
        try:
            __import__(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
    if missing:
        raise RuntimeError(
            "Plotting is enabled but required package(s) are missing: "
            + ", ".join(missing)
            + ". Install the packman-muse batch environment dependencies or pass --no-save-plots."
        )


@torch.no_grad()
def save_training_plots(
    *,
    output_dir: str | Path,
    metrics_rows: list[dict[str, float | int]],
    model: nn.Module,
    val_loader: DataLoader,
    validation_dataset: Dataset,
    device: torch.device,
    label_names: tuple[str, ...],
    feature_names: tuple[str, ...],
    pos_weight: torch.Tensor | None,
    threshold: float,
    bins: int,
    calibrate_pos_weight_logits: bool,
    calibrator: PlattCalibrator | None,
    save_validation_predictions: bool,
    save_full_validation_predictions: bool,
    prediction_sample_size: int,
    edge_band_mm: float,
    near_band_mm: float,
) -> dict[str, Any]:
    check_plot_dependencies()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    output_dir = Path(output_dir)
    plots_dir = output_dir / "plots"
    tables_dir = output_dir / "summary_tables"
    plots_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, str] = {}
    tables: dict[str, str] = {}
    metrics_frame = pd.DataFrame(metrics_rows)
    if not metrics_frame.empty:
        _plot_loss_curves(metrics_frame, plots_dir / "loss_curves.png", plt)
        saved["loss_curves"] = "plots/loss_curves.png"
        _plot_macro_metrics(metrics_frame, plots_dir / "macro_metrics.png", plt)
        saved["macro_metrics"] = "plots/macro_metrics.png"
        for metric, filename in (
            ("auroc", "per_label_auroc.png"),
            ("average_precision", "per_label_average_precision.png"),
            ("brier", "per_label_brier.png"),
            ("expected_calibration_error", "per_label_ece.png"),
        ):
            _plot_per_label_metric(metrics_frame, label_names, metric, plots_dir / filename, plt)
            saved[f"per_label_{metric}"] = f"plots/{filename}"

    prediction_frame = _collect_prediction_frame(
        model=model,
        val_loader=val_loader,
        validation_dataset=validation_dataset,
        device=device,
        label_names=label_names,
        feature_names=feature_names,
        pos_weight=pos_weight,
        calibrate_pos_weight_logits=calibrate_pos_weight_logits,
        calibrator=calibrator,
        edge_band_mm=edge_band_mm,
        near_band_mm=near_band_mm,
    )

    per_label = _per_label_summary(prediction_frame, label_names)
    topk = _topk_lift_table(prediction_frame, label_names)
    regimes = _regime_metrics_table(prediction_frame, label_names)
    calibration_bins = _calibration_bins_table(prediction_frame, label_names, bins)
    residual_core_metrics, residual_rate_bins = residual_core_rate_tables(
        prediction_frame,
        label_names,
        quantile_bins=DEFAULT_RATE_QUANTILE_BINS,
    )
    per_label.to_csv(tables_dir / "per_label_metrics.csv", index=False)
    topk.to_csv(tables_dir / "topk_lift.csv", index=False)
    regimes.to_csv(tables_dir / "regime_metrics.csv", index=False)
    calibration_bins.to_csv(tables_dir / "calibration_bins.csv", index=False)
    if not residual_core_metrics.empty:
        residual_core_metrics.to_csv(tables_dir / "residual_core_metrics.csv", index=False)
    if not residual_rate_bins.empty:
        residual_rate_bins.to_csv(tables_dir / "residual_rate_bins.csv", index=False)
    tables.update(
        {
            "per_label_metrics": "summary_tables/per_label_metrics.csv",
            "topk_lift": "summary_tables/topk_lift.csv",
            "regime_metrics": "summary_tables/regime_metrics.csv",
            "calibration_bins": "summary_tables/calibration_bins.csv",
        }
    )
    if not residual_core_metrics.empty:
        tables["residual_core_metrics"] = "summary_tables/residual_core_metrics.csv"
    if not residual_rate_bins.empty:
        tables["residual_rate_bins"] = "summary_tables/residual_rate_bins.csv"

    if save_full_validation_predictions:
        prediction_frame.to_csv(plots_dir / "validation_predictions_full.csv", index=False, float_format="%.8g")
        saved["validation_predictions_full"] = "plots/validation_predictions_full.csv"
    if save_validation_predictions:
        sampled = _sample_prediction_frame(prediction_frame, label_names, prediction_sample_size, pd)
        sampled.to_csv(plots_dir / "validation_predictions.csv", index=False, float_format="%.8g")
        saved["validation_predictions"] = "plots/validation_predictions.csv"

    _plot_roc_curves(prediction_frame, label_names, per_label, plots_dir / "roc_curves.png", plt, np)
    saved["roc_curves"] = "plots/roc_curves.png"
    _plot_pr_curves(prediction_frame, label_names, per_label, plots_dir / "pr_curves.png", plt, np)
    saved["pr_curves"] = "plots/pr_curves.png"
    _plot_topk_lift(topk, plots_dir / "topk_lift.png", plt)
    saved["topk_lift"] = "plots/topk_lift.png"
    _plot_regime_rates(regimes, plots_dir / "regime_rates.png", plt, np)
    saved["regime_rates"] = "plots/regime_rates.png"
    _plot_edge_margin_zoom(prediction_frame, label_names, plots_dir / "edge_margin_zoom.png", plt, np, bins)
    saved["edge_margin_zoom"] = "plots/edge_margin_zoom.png"
    _plot_calibration_curves(prediction_frame, label_names, plots_dir / "calibration_curves.png", plt, np, bins)
    saved["calibration_curves"] = "plots/calibration_curves.png"
    _plot_calibration_log_probability(calibration_bins, plots_dir / "calibration_log_probability.png", plt)
    saved["calibration_log_probability"] = "plots/calibration_log_probability.png"
    _plot_calibration_by_regime(regimes, plots_dir / "calibration_by_regime.png", plt, np)
    saved["calibration_by_regime"] = "plots/calibration_by_regime.png"
    _plot_predicted_vs_observed_bins(prediction_frame, label_names, plots_dir / "predicted_vs_observed_bins.png", plt, np, bins)
    saved["predicted_vs_observed_bins"] = "plots/predicted_vs_observed_bins.png"
    _plot_score_histograms(prediction_frame, label_names, plots_dir / "score_hist_tail.png", plt, np)
    saved["score_hist_tail"] = "plots/score_hist_tail.png"
    _plot_xy_acceptance_heatmaps(prediction_frame, label_names, plots_dir / "xy_heatmaps_zoomed.png", plt, np)
    saved["xy_heatmaps_zoomed"] = "plots/xy_heatmaps_zoomed.png"

    index = {
        "plots": saved,
        "tables": tables,
        "threshold": threshold,
        "bins": bins,
        "prediction_rows": int(len(prediction_frame)),
        "saved_prediction_sample_size": int(min(len(prediction_frame), prediction_sample_size)),
        "residual_rate_quantile_bins": DEFAULT_RATE_QUANTILE_BINS,
        "residual_rate_min_bin_count": DEFAULT_MIN_RATE_BIN_COUNT,
        "residual_rate_bin_columns": [name for name in RESIDUAL_RATE_BIN_COLUMNS if name in prediction_frame.columns],
        "probability_columns": {
            "prob_raw__<label>": "sigmoid(raw model logit)",
            "prob_weight_corrected__<label>": "sigmoid(logit - log(pos_weight)) when enabled",
            "prob__<label>": "post-hoc calibrated probability when calibration is available",
        },
    }
    (plots_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return index


def _collect_prediction_frame(
    *,
    model: nn.Module,
    val_loader: DataLoader,
    validation_dataset: Dataset,
    device: torch.device,
    label_names: tuple[str, ...],
    feature_names: tuple[str, ...],
    pos_weight: torch.Tensor | None,
    calibrate_pos_weight_logits: bool,
    calibrator: PlattCalibrator | None,
    edge_band_mm: float,
    near_band_mm: float,
):
    import pandas as pd

    model.eval()
    logits_batches = []
    target_batches = []
    for features, targets in val_loader:
        features = features.to(device=device, non_blocking=True)
        logits_batches.append(model(features).detach().cpu())
        target_batches.append(targets.detach().cpu())

    logits = torch.cat(logits_batches, dim=0)
    targets = torch.cat(target_batches, dim=0).to(dtype=torch.float32)
    if calibrate_pos_weight_logits:
        weight_corrected_logits = calibrated_probability_logits(logits, pos_weight.cpu() if pos_weight is not None else None)
    else:
        weight_corrected_logits = logits
    final_logits = calibrator.transform_logits(weight_corrected_logits) if calibrator is not None else weight_corrected_logits
    raw_probabilities = torch.sigmoid(logits)
    weight_corrected_probabilities = torch.sigmoid(weight_corrected_logits)
    probabilities = torch.sigmoid(final_logits)

    data: dict[str, Any] = {}
    for index, label in enumerate(label_names):
        data[f"target__{label}"] = targets[:, index].numpy()
        data[f"logit__{label}"] = logits[:, index].numpy()
        data[f"prob_raw__{label}"] = raw_probabilities[:, index].numpy()
        data[f"prob_weight_corrected__{label}"] = weight_corrected_probabilities[:, index].numpy()
        data[f"prob__{label}"] = probabilities[:, index].numpy()
    prediction_frame = pd.DataFrame(data)
    metadata = _validation_metadata_frame(validation_dataset, feature_names)
    prediction_frame = pd.concat([metadata, prediction_frame], axis=1)
    _add_regime_columns(prediction_frame, label_names, edge_band_mm=edge_band_mm, near_band_mm=near_band_mm)
    return prediction_frame


def _validation_metadata_frame(validation_dataset: Dataset, feature_names: tuple[str, ...]):
    import numpy as np
    import pandas as pd

    base_dataset, indices = _base_dataset_and_indices(validation_dataset)
    row_index = np.asarray(indices, dtype=np.int64)
    frame = pd.DataFrame({"row_index": row_index})
    feature_frame = getattr(base_dataset, "feature_frame", None)
    if feature_frame is None:
        return frame
    geometry_columns = [name for name in feature_names if name in feature_frame.columns and _is_geometry_plot_column(name)]
    if not geometry_columns:
        return frame
    return pd.concat([frame, feature_frame.iloc[row_index][geometry_columns].reset_index(drop=True)], axis=1)


def _base_dataset_and_indices(dataset: Dataset) -> tuple[Dataset, list[int]]:
    if isinstance(dataset, Subset):
        return dataset.dataset, [int(index) for index in dataset.indices]
    return dataset, list(range(len(dataset)))


def _is_geometry_plot_column(name: str) -> bool:
    return (
        "_at_" in name
        or name.endswith("_edge_margin_mm")
        or name.endswith("_edge_margin_norm")
        or name.startswith("r_at_")
        or name.startswith("geom_")
        or name == "path_scale_z"
        or name in RESIDUAL_RATE_BIN_COLUMNS
    )


def _add_regime_columns(frame, label_names: tuple[str, ...], *, edge_band_mm: float, near_band_mm: float) -> None:
    import numpy as np

    for label in label_names:
        detector = _detector_for_label(label)
        if detector is None:
            continue
        margin_col = f"{detector}_edge_margin_mm"
        if margin_col not in frame.columns:
            continue
        margin = frame[margin_col].to_numpy()
        regimes = np.full(len(frame), "core", dtype=object)
        regimes[margin <= near_band_mm] = "near"
        regimes[margin <= edge_band_mm] = "edge"
        regimes[margin <= 0.0] = "outside"
        frame[f"regime__{label}"] = regimes


def _sample_prediction_frame(frame, label_names: tuple[str, ...], sample_size: int, pd):
    if len(frame) <= sample_size:
        return frame
    positive_mask = None
    for label in label_names:
        mask = frame[f"target__{label}"] > 0.5
        positive_mask = mask if positive_mask is None else (positive_mask | mask)
    positives = frame[positive_mask]
    negatives = frame[~positive_mask]
    negative_count = max(0, sample_size - len(positives))
    if negative_count >= len(negatives):
        return frame
    sampled_negatives = negatives.sample(n=negative_count, random_state=1337)
    return pd.concat([positives, sampled_negatives], axis=0).sample(frac=1.0, random_state=1337).reset_index(drop=True)


def _per_label_summary(frame, label_names: tuple[str, ...]):
    import pandas as pd

    rows = []
    for label in label_names:
        target = frame[f"target__{label}"]
        prob = frame[f"prob__{label}"]
        base = float(target.mean())
        brier = float(((prob - target) ** 2).mean())
        rows.append(
            {
                "label": label,
                "count": int(len(frame)),
                "positives": int(target.sum()),
                "base_rate": base,
                "mean_probability": float(prob.mean()),
                "brier": brier,
                "top_0_1pct_lift": _top_fraction_rate(frame, label, 0.001) / base if base > 0 else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _topk_lift_table(frame, label_names: tuple[str, ...]):
    import pandas as pd

    rows = []
    for label in label_names:
        base = float(frame[f"target__{label}"].mean())
        for fraction in TOPK_FRACTIONS:
            rate = _top_fraction_rate(frame, label, fraction)
            rows.append(
                {
                    "label": label,
                    "fraction": fraction,
                    "top_count": max(1, int(round(len(frame) * fraction))),
                    "observed_rate": rate,
                    "base_rate": base,
                    "lift": rate / base if base > 0 else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def _regime_metrics_table(frame, label_names: tuple[str, ...]):
    import pandas as pd

    rows = []
    for label in label_names:
        regime_col = f"regime__{label}"
        if regime_col not in frame.columns:
            continue
        grouped = frame.groupby(regime_col, observed=True)
        for regime, group in grouped:
            rows.append(
                {
                    "label": label,
                    "regime": regime,
                    "count": int(len(group)),
                    "positives": int(group[f"target__{label}"].sum()),
                    "observed_rate": float(group[f"target__{label}"].mean()),
                    "predicted_rate": float(group[f"prob__{label}"].mean()),
                }
            )
    table = pd.DataFrame(rows)
    if not table.empty:
        table["regime"] = pd.Categorical(table["regime"], categories=list(REGIME_ORDER), ordered=True)
        table = table.sort_values(["label", "regime"])
    return table


def _calibration_bins_table(frame, label_names: tuple[str, ...], bins: int):
    import numpy as np
    import pandas as pd

    rows = []
    edges = np.geomspace(1e-6, 1.0, bins + 1)
    edges[0] = 0.0
    for label in label_names:
        prob = frame[f"prob__{label}"].to_numpy()
        target = frame[f"target__{label}"].to_numpy()
        bin_index = np.clip(np.digitize(prob, edges, right=False) - 1, 0, bins - 1)
        for index in range(bins):
            mask = bin_index == index
            if not mask.any():
                continue
            rows.append(
                {
                    "label": label,
                    "bin": index,
                    "lower": float(edges[index]),
                    "upper": float(edges[index + 1]),
                    "count": int(mask.sum()),
                    "mean_probability": float(prob[mask].mean()),
                    "observed_rate": float(target[mask].mean()),
                }
            )
    return pd.DataFrame(rows)


def _top_fraction_rate(frame, label: str, fraction: float) -> float:
    n = max(1, int(round(len(frame) * fraction)))
    return float(frame.nlargest(n, f"prob__{label}")[f"target__{label}"].mean())


def _plot_loss_curves(metrics, path: Path, plt) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(metrics["epoch"], metrics["train_loss"], label="train_loss")
    ax.plot(metrics["epoch"], metrics["val_loss"], label="val_loss")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("Training and validation loss")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_macro_metrics(metrics, path: Path, plt) -> None:
    columns = ["val_macro_auroc", "val_macro_average_precision", "val_macro_f1", "val_macro_brier", "val_macro_expected_calibration_error"]
    fig, ax = plt.subplots(figsize=(9, 5))
    for column in columns:
        if column in metrics.columns:
            ax.plot(metrics["epoch"], metrics[column], label=column.removeprefix("val_macro_"))
    ax.set_xlabel("epoch")
    ax.set_ylabel("metric")
    ax.set_title("Validation macro metrics")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_per_label_metric(metrics, label_names: tuple[str, ...], metric: str, path: Path, plt) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for label in label_names:
        column = f"val_{label}_{metric}"
        if column in metrics.columns:
            ax.plot(metrics["epoch"], metrics[column], label=label)
    ax.set_xlabel("epoch")
    ax.set_ylabel(metric)
    ax.set_title(f"Validation per-label {metric}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_roc_curves(frame, label_names, per_label, path, plt, np):
    fig, ax = plt.subplots(figsize=(6, 6))
    for label in label_names:
        fpr, tpr = _roc_points(frame[f"prob__{label}"].to_numpy(), frame[f"target__{label}"].to_numpy(), np)
        if len(fpr):
            fpr, tpr = _thin_points(fpr, tpr, np)
            ax.plot(fpr, tpr, label=label)
    ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title("ROC curves")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_pr_curves(frame, label_names, per_label, path, plt, np):
    fig, ax = plt.subplots(figsize=(6, 6))
    for label in label_names:
        recall, precision = _pr_points(frame[f"prob__{label}"].to_numpy(), frame[f"target__{label}"].to_numpy(), np)
        if len(recall):
            recall, precision = _thin_points(recall, precision, np)
            base = float(frame[f"target__{label}"].mean())
            ax.plot(recall, precision, label=f"{label} base={base:.3g}")
            ax.axhline(base, color="gray", linewidth=0.6, alpha=0.35)
    ax.set_xlabel("recall")
    ax.set_ylabel("precision")
    ax.set_title("Precision-recall curves")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_topk_lift(topk, path, plt):
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, group in topk.groupby("label"):
        ax.plot(group["fraction"] * 100.0, group["lift"], marker="o", label=label)
    ax.set_xscale("log")
    ax.set_xlabel("top scored fraction [%]")
    ax.set_ylabel("observed/base lift")
    ax.set_title("Top-k enrichment")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_regime_rates(regimes, path, plt, np):
    if regimes.empty:
        _blank_plot(path, plt, "No regime columns available")
        return
    labels = list(regimes["label"].drop_duplicates())
    fig, axes = plt.subplots(len(labels), 1, figsize=(9, max(3, 2.8 * len(labels))), squeeze=False)
    for ax, label in zip(axes[:, 0], labels):
        group = regimes[regimes["label"] == label]
        x = np.arange(len(group))
        ax.plot(x, group["observed_rate"], marker="o", label="observed")
        ax.plot(x, group["predicted_rate"], marker="o", label="predicted")
        ax.set_xticks(x, [str(value) for value in group["regime"]])
        ax.set_title(label)
        ax.set_ylabel("rate")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_edge_margin_zoom(frame, label_names, path, plt, np, bins):
    fig, axes = plt.subplots(len(label_names), 1, figsize=(9, max(3, 2.8 * len(label_names))), squeeze=False)
    for ax, label in zip(axes[:, 0], label_names):
        detector = _detector_for_label(label)
        if detector is None or f"{detector}_edge_margin_mm" not in frame.columns:
            continue
        margin = frame[f"{detector}_edge_margin_mm"].to_numpy()
        keep = (margin >= -20.0) & (margin <= 50.0)
        x, observed, _ = _binned_xy(margin[keep], frame.loc[keep, f"target__{label}"].to_numpy(), np, bins)
        _, predicted, counts = _binned_xy(margin[keep], frame.loc[keep, f"prob__{label}"].to_numpy(), np, bins)
        ax.plot(x, observed, marker="o", label="observed")
        ax.plot(x, predicted, marker="o", label="predicted")
        ax.axvline(0.0, color="black", linestyle="--", linewidth=1)
        ax.set_title(f"{label} edge-margin zoom")
        ax.set_xlabel("edge margin [mm]")
        ax.set_ylabel("miss rate")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        ax2 = ax.twinx()
        ax2.bar(x, counts, width=_median_bin_width(x, np), color="gray", alpha=0.15)
        ax2.set_yscale("log")
        ax2.set_ylabel("count")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_calibration_curves(frame, label_names, path, plt, np, bins):
    fig, ax = plt.subplots(figsize=(6, 6))
    for label in label_names:
        mean_pred, observed, _ = _quantile_bin_stats(frame[f"prob__{label}"].to_numpy(), frame[f"target__{label}"].to_numpy(), np, bins)
        ax.plot(mean_pred, observed, marker="o", markersize=3, label=label)
    ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("observed positive rate")
    ax.set_title("Quantile calibration curves")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_calibration_log_probability(calibration_bins, path, plt):
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, group in calibration_bins.groupby("label"):
        ax.plot(group["mean_probability"], group["observed_rate"], marker="o", label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("observed positive rate")
    ax.set_title("Log-probability calibration")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_calibration_by_regime(regimes, path, plt, np):
    _plot_regime_rates(regimes, path, plt, np)


def _plot_predicted_vs_observed_bins(frame, label_names, path, plt, np, bins):
    fig, axes = plt.subplots(len(label_names), 1, figsize=(8, max(3, 2.8 * len(label_names))), squeeze=False)
    for ax, label in zip(axes[:, 0], label_names):
        mean_pred, observed, counts = _quantile_bin_stats(frame[f"prob__{label}"].to_numpy(), frame[f"target__{label}"].to_numpy(), np, bins)
        x = np.arange(len(mean_pred))
        ax.plot(x, observed, marker="o", label="observed")
        ax.plot(x, mean_pred, marker="o", label="predicted")
        ax.set_title(f"{label} probability bins")
        ax.set_xlabel("score quantile bin")
        ax.set_ylabel("rate")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        ax2 = ax.twinx()
        ax2.bar(x, counts, color="gray", alpha=0.15)
        ax2.set_ylabel("count")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_score_histograms(frame, label_names, path, plt, np):
    fig, axes = plt.subplots(len(label_names), 1, figsize=(8, max(3, 2.6 * len(label_names))), squeeze=False)
    for ax, label in zip(axes[:, 0], label_names):
        scores = frame[f"prob__{label}"].to_numpy()
        targets = frame[f"target__{label}"].to_numpy() > 0.5
        ax.hist(scores[~targets], bins=np.geomspace(1e-6, 1.0, 80), alpha=0.55, label="negative", density=True)
        if targets.any():
            ax.hist(scores[targets], bins=np.geomspace(1e-6, 1.0, 80), alpha=0.65, label="positive", density=True)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(label)
        ax.set_xlabel("calibrated probability")
        ax.set_ylabel("density")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_xy_acceptance_heatmaps(frame, label_names, path, plt, np):
    labels = []
    for label in label_names:
        detector = _detector_for_label(label)
        if detector and f"x_at_{detector}_mm" in frame.columns and f"y_at_{detector}_mm" in frame.columns:
            labels.append((label, detector))
    if not labels:
        _blank_plot(path, plt, "No x/y detector projection columns available")
        return
    fig, axes = plt.subplots(len(labels), 2, figsize=(10, max(4, 3.2 * len(labels))), squeeze=False)
    for row, (label, detector) in enumerate(labels):
        x = frame[f"x_at_{detector}_mm"].to_numpy()
        y = frame[f"y_at_{detector}_mm"].to_numpy()
        target = frame[f"target__{label}"].to_numpy()
        probability = frame[f"prob__{label}"].to_numpy()
        margin = frame[f"{detector}_edge_margin_mm"].to_numpy()
        keep = margin <= 50.0
        observed, extent = _weighted_heatmap(x[keep], y[keep], target[keep], np)
        predicted, _ = _weighted_heatmap(x[keep], y[keep], probability[keep], np)
        for ax, image, title in ((axes[row, 0], observed, f"{label} observed"), (axes[row, 1], predicted, f"{label} predicted")):
            im = ax.imshow(image.T, origin="lower", extent=extent, aspect="auto")
            ax.set_title(title)
            ax.set_xlabel("x [mm]")
            ax.set_ylabel("y [mm]")
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _roc_points(scores, targets, np):
    targets = (targets > 0.5).astype(np.float64)
    positives = targets.sum()
    negatives = targets.size - positives
    if positives <= 0 or negatives <= 0:
        return np.array([]), np.array([])
    order = np.argsort(-scores, kind="mergesort")
    sorted_targets = targets[order]
    true_positive = np.cumsum(sorted_targets)
    false_positive = np.cumsum(1.0 - sorted_targets)
    tpr = np.concatenate([[0.0], true_positive / positives])
    fpr = np.concatenate([[0.0], false_positive / negatives])
    return fpr, tpr


def _pr_points(scores, targets, np):
    targets = (targets > 0.5).astype(np.float64)
    positives = targets.sum()
    if positives <= 0:
        return np.array([]), np.array([])
    order = np.argsort(-scores, kind="mergesort")
    sorted_targets = targets[order]
    true_positive = np.cumsum(sorted_targets)
    ranks = np.arange(1, sorted_targets.size + 1)
    precision = true_positive / ranks
    recall = true_positive / positives
    return np.concatenate([[0.0], recall]), np.concatenate([[1.0], precision])


def _thin_points(x, y, np, max_points: int = 2000):
    if len(x) <= max_points:
        return x, y
    indices = np.linspace(0, len(x) - 1, max_points).astype(int)
    return x[indices], y[indices]


def _quantile_bin_stats(scores, targets, np, bins: int):
    order = np.argsort(scores, kind="mergesort")
    chunks = np.array_split(order, min(bins, len(order)))
    mean_pred = []
    observed = []
    counts = []
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        mean_pred.append(float(np.mean(scores[chunk])))
        observed.append(float(np.mean(targets[chunk])))
        counts.append(int(len(chunk)))
    return np.asarray(mean_pred), np.asarray(observed), np.asarray(counts)


def _binned_xy(x, y, np, bins: int):
    if len(x) == 0:
        return np.asarray([]), np.asarray([]), np.asarray([])
    order = np.argsort(x, kind="mergesort")
    chunks = np.array_split(order, min(bins, len(order)))
    x_mean = []
    y_mean = []
    counts = []
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        x_mean.append(float(np.mean(x[chunk])))
        y_mean.append(float(np.mean(y[chunk])))
        counts.append(int(len(chunk)))
    return np.asarray(x_mean), np.asarray(y_mean), np.asarray(counts)


def _weighted_heatmap(x, y, values, np, bins: int = 60):
    counts, x_edges, y_edges = np.histogram2d(x, y, bins=bins)
    sums, _, _ = np.histogram2d(x, y, bins=(x_edges, y_edges), weights=values)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = sums / counts
    mean[counts <= 0] = np.nan
    extent = [x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]]
    return mean, extent


def _detector_for_label(label: str) -> str | None:
    for detector in ("bhc", "bhd", "gem0"):
        if detector in label:
            return detector
    return None


def _median_bin_width(x, np) -> float:
    if len(x) < 2:
        return 1.0
    diffs = np.diff(np.sort(x))
    positive = diffs[diffs > 0]
    if len(positive) == 0:
        return 1.0
    return float(np.median(positive))


def _blank_plot(path: Path, plt, message: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.text(0.5, 0.5, message, ha="center", va="center")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
