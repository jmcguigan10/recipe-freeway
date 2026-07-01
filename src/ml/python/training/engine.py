from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import nn

try:
    from training._compat import ensure_project_paths
except ModuleNotFoundError:
    from ._compat import ensure_project_paths

ensure_project_paths()
from src.ml.python.io.args import TrainingConfig
from src.ml.python.io.logging import print_cuda_banner, print_epoch
from src.ml.python.io.saving import save_checkpoint, write_json, write_metrics_csv

from .calibration import collect_logits_and_targets, fit_platt_calibrator
from .dataloaders import make_dataloaders
from .epoch import train_one_epoch
from .evaluate import evaluate
from .factory import (
    build_loss_fn,
    build_model,
    build_optimizer,
    build_scheduler,
    resolve_device,
    resolve_pos_weight,
)
from .payload import config_payload_for
from .plots import check_plot_dependencies, save_training_plots
from .seed import set_reproducible_seed


def fit(config: TrainingConfig) -> dict[str, Any]:
    set_reproducible_seed(config.seed)
    device = resolve_device(config.device)
    if device.type == "cuda":
        print_cuda_banner(device)
    if config.save_plots:
        check_plot_dependencies()

    train_loader, val_loader, calibration_loader, train_dataset, validation_dataset, calibration_dataset = make_dataloaders(config)
    model = build_model(config, train_dataset).to(device)
    if device.type == "cuda" and torch.cuda.device_count() > 1:
        print(f"Using DataParallel across {torch.cuda.device_count()} CUDA devices")
        model = nn.DataParallel(model)

    pos_weight = resolve_pos_weight(config, train_loader, device)
    if pos_weight is not None and pos_weight.numel() != len(train_dataset.target_columns):
        raise ValueError("pos_weight length must match the number of target columns")
    loss_fn = build_loss_fn(config, train_dataset.target_columns, pos_weight, device)
    label_weight = loss_fn.label_weight
    optimizer = build_optimizer(config, model)
    scheduler = build_scheduler(config, optimizer)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_payload = config_payload_for(
        config,
        train_dataset,
        train_loader.dataset,
        validation_dataset,
        device,
        pos_weight,
        label_weight,
        loss_fn.task_loss_weights(),
    )
    config_payload["calibration_examples"] = len(calibration_dataset)
    write_json(output_dir / "config.json", config_payload)

    metrics_rows: list[dict[str, float | int]] = []
    best_val_loss = float("inf")
    best_metric_name = config.checkpoint_metric
    best_metric_value = _initial_best_value(config.checkpoint_mode)
    best_epoch = 0
    epochs_without_improvement = 0

    for epoch in range(1, config.epochs + 1):
        train_metrics = train_one_epoch(
            model,
            train_loader,
            optimizer,
            loss_fn,
            device,
            label_names=train_dataset.target_columns,
        )
        train_loss = train_metrics["loss"]
        val_metrics = evaluate(
            model,
            val_loader,
            loss_fn,
            device,
            threshold=config.threshold,
            label_names=train_dataset.target_columns,
            pos_weight=pos_weight,
            calibrate_pos_weight_logits=config.calibrate_pos_weight_logits,
            calibration_bins=config.plot_bins,
        )
        row: dict[str, float | int] = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_metrics["loss"],
            "lr": float(optimizer.param_groups[0]["lr"]),
        }
        for key, value in train_metrics.items():
            if key != "loss":
                row[f"train_{key}"] = value
        for key, value in val_metrics.items():
            if key != "loss":
                row[f"val_{key}"] = value
        metrics_rows.append(row)
        print_epoch(row)

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]

        current_metric_value = _metric_value(row, best_metric_name)
        if _is_improvement(
            current_metric_value,
            best_metric_value,
            mode=config.checkpoint_mode,
            min_delta=config.early_stopping_min_delta,
        ):
            best_metric_value = current_metric_value
            best_epoch = epoch
            epochs_without_improvement = 0
            save_checkpoint(
                output_dir / "best.pt",
                model,
                optimizer,
                epoch=epoch,
                best_val_loss=best_val_loss,
                config_payload=config_payload,
                best_metric_name=best_metric_name,
                best_metric_value=best_metric_value,
                best_epoch=best_epoch,
            )
        else:
            epochs_without_improvement += 1

        save_checkpoint(
            output_dir / "latest.pt",
            model,
            optimizer,
            epoch=epoch,
            best_val_loss=best_val_loss,
            config_payload=config_payload,
            best_metric_name=best_metric_name,
            best_metric_value=best_metric_value,
            best_epoch=best_epoch,
        )
        write_metrics_csv(output_dir / "metrics.csv", metrics_rows)

        if scheduler is not None:
            scheduler.step()

        if config.early_stopping_patience > 0 and epochs_without_improvement >= config.early_stopping_patience:
            print(
                "Early stopping: "
                f"{best_metric_name} did not improve for {epochs_without_improvement} epoch(s)."
            )
            break

    calibration_payload = None
    if best_epoch > 0:
        checkpoint = torch.load(output_dir / "best.pt", map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        calibration_logits, calibration_targets = collect_logits_and_targets(
            model,
            calibration_loader,
            device,
            pos_weight=pos_weight,
            calibrate_pos_weight_logits=config.calibrate_pos_weight_logits,
        )
        calibrator = fit_platt_calibrator(
            calibration_logits,
            calibration_targets,
            label_names=train_dataset.target_columns,
        )
        calibration_payload = calibrator.to_payload()
        write_json(output_dir / "calibration.json", calibration_payload)

        if config.save_plots:
            save_training_plots(
                output_dir=output_dir,
                metrics_rows=metrics_rows,
                model=model,
                val_loader=calibration_loader,
                validation_dataset=calibration_dataset,
                device=device,
                label_names=train_dataset.target_columns,
                feature_names=train_dataset.feature_columns,
                pos_weight=pos_weight,
                threshold=config.threshold,
                bins=config.plot_bins,
                calibrate_pos_weight_logits=config.calibrate_pos_weight_logits,
                calibrator=calibrator,
                save_validation_predictions=config.plot_validation_predictions,
                save_full_validation_predictions=config.save_full_validation_predictions,
                prediction_sample_size=config.prediction_sample_size,
                edge_band_mm=config.edge_band_mm,
                near_band_mm=config.near_band_mm,
            )

    return {
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "best_metric_name": best_metric_name,
        "best_metric_value": best_metric_value,
        "calibration": calibration_payload,
        "metrics": metrics_rows,
        "output_dir": str(output_dir),
    }


def _initial_best_value(mode: str) -> float:
    if mode == "min":
        return float("inf")
    if mode == "max":
        return float("-inf")
    raise ValueError(f"Unsupported checkpoint mode: {mode}")


def _metric_value(row: dict[str, float | int], metric_name: str) -> float:
    if metric_name not in row:
        available = ", ".join(sorted(row))
        raise ValueError(f"Checkpoint metric not found: {metric_name}. Available metrics: {available}")
    return float(row[metric_name])


def _is_improvement(
    value: float,
    best_value: float,
    *,
    mode: str,
    min_delta: float,
) -> bool:
    if mode == "min":
        return value < best_value - min_delta
    if mode == "max":
        return value > best_value + min_delta
    raise ValueError(f"Unsupported checkpoint mode: {mode}")
