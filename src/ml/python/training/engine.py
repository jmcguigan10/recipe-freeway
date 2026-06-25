from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

try:
    from training._compat import ensure_project_paths
except ModuleNotFoundError:
    from ._compat import ensure_project_paths

ensure_project_paths()
from src.ml.python.io.args import TrainingConfig
from src.ml.python.io.logging import print_cuda_banner, print_epoch
from src.ml.python.io.saving import save_checkpoint, write_json, write_metrics_csv

try:
    from data.gem_data import GemClassifierDataset
    from models.multi_label_bce import MultiLabelBCEModel
    from training.dataloaders import make_dataloaders
    from training.evaluate import evaluate
    from training.loss import build_bce_with_logits_loss, estimate_pos_weight
    from training.seed import set_reproducible_seed
except ModuleNotFoundError:
    from ..data.gem_data import GemClassifierDataset
    from ..models.multi_label_bce import MultiLabelBCEModel
    from .dataloaders import make_dataloaders
    from .evaluate import evaluate
    from .loss import build_bce_with_logits_loss, estimate_pos_weight
    from .seed import set_reproducible_seed


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    total_examples = 0

    for features, targets in loader:
        features = features.to(device=device, non_blocking=True)
        targets = targets.to(device=device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        logits = model(features)
        loss = loss_fn(logits, targets)
        loss.backward()
        optimizer.step()

        batch_size = features.shape[0]
        total_loss += float(loss.detach().cpu()) * batch_size
        total_examples += batch_size

    return total_loss / max(total_examples, 1)


def fit(config: TrainingConfig) -> dict[str, Any]:
    set_reproducible_seed(config.seed)
    device = resolve_device(config.device)
    if device.type == "cuda":
        print_cuda_banner(device)

    train_loader, val_loader, train_dataset, validation_dataset = make_dataloaders(config)
    model = MultiLabelBCEModel(
        input_dim=len(train_dataset.feature_columns),
        output_dim=len(train_dataset.target_columns),
        hidden_dims=config.hidden_dims,
        dropout=config.dropout,
    ).to(device)

    pos_weight = resolve_pos_weight(config, train_loader, device)
    if pos_weight is not None and pos_weight.numel() != len(train_dataset.target_columns):
        raise ValueError("pos_weight length must match the number of target columns")
    loss_fn = build_bce_with_logits_loss(pos_weight=pos_weight, device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_payload = config_payload_for(config, train_dataset, train_loader.dataset, validation_dataset, device, pos_weight)
    write_json(output_dir / "config.json", config_payload)

    metrics_rows: list[dict[str, float | int]] = []
    best_val_loss = float("inf")
    best_epoch = 0

    for epoch in range(1, config.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, loss_fn, device)
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
        for key, value in val_metrics.items():
            if key != "loss":
                row[f"val_{key}"] = value
        metrics_rows.append(row)
        print_epoch(row)

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


def resolve_device(device_name: str | None) -> torch.device:
    if device_name is None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required by default. Pass --device cpu for a CPU debug run.")
        return torch.device("cuda")

    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested CUDA device is unavailable: {device_name}")
    return device


def resolve_pos_weight(
    config: TrainingConfig,
    train_loader: DataLoader,
    device: torch.device,
) -> torch.Tensor | None:
    raw = config.pos_weight.strip().lower()
    if raw in ("none", "false", "0", "off"):
        return None
    if raw == "auto":
        return estimate_pos_weight(train_loader, device=device)
    values = [float(value.strip()) for value in config.pos_weight.split(",") if value.strip()]
    if not values:
        raise ValueError("--pos-weight must be 'auto', 'none', or comma-separated floats")
    return torch.as_tensor(values, dtype=torch.float32, device=device)


def config_payload_for(
    config: TrainingConfig,
    train_dataset: GemClassifierDataset,
    training_dataset: Dataset,
    validation_dataset: Dataset,
    device: torch.device,
    pos_weight: torch.Tensor | None,
) -> dict[str, Any]:
    payload = asdict(config)
    payload.update(
        {
            "feature_columns": list(train_dataset.feature_columns),
            "target_columns": list(train_dataset.target_columns),
            "input_dim": len(train_dataset.feature_columns),
            "output_dim": len(train_dataset.target_columns),
            "device": str(device),
            "source_train_examples": len(train_dataset),
            "train_examples": len(training_dataset),
            "validation_examples": len(validation_dataset),
            "pos_weight_values": None if pos_weight is None else [float(value) for value in pos_weight.detach().cpu()],
        }
    )
    payload["hidden_dims"] = list(config.hidden_dims)
    return payload
