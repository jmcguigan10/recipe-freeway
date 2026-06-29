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
from .seed import set_reproducible_seed


def fit(config: TrainingConfig) -> dict[str, Any]:
    set_reproducible_seed(config.seed)
    device = resolve_device(config.device)
    if device.type == "cuda":
        print_cuda_banner(device)

    train_loader, val_loader, train_dataset, validation_dataset = make_dataloaders(config)
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
    write_json(output_dir / "config.json", config_payload)

    metrics_rows: list[dict[str, float | int]] = []
    best_val_loss = float("inf")
    best_epoch = 0

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
        )
        row: dict[str, float | int] = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_metrics["loss"],
        }
        for key, value in train_metrics.items():
            if key != "loss":
                row[f"train_{key}"] = value
        for key, value in val_metrics.items():
            if key != "loss":
                row[f"val_{key}"] = value
        metrics_rows.append(row)
        print_epoch(row)

        if scheduler is not None:
            scheduler.step()

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            best_epoch = epoch
            save_checkpoint(
                output_dir / "best.pt",
                model,
                optimizer,
                epoch=epoch,
                best_val_loss=best_val_loss,
                config_payload=config_payload,
            )

        save_checkpoint(
            output_dir / "latest.pt",
            model,
            optimizer,
            epoch=epoch,
            best_val_loss=best_val_loss,
            config_payload=config_payload,
        )
        write_metrics_csv(output_dir / "metrics.csv", metrics_rows)

    return {
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "metrics": metrics_rows,
        "output_dir": str(output_dir),
    }
