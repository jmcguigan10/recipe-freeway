from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
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
    from models.multi_label_bce import GroupedMultiTaskBCEModel, MultiLabelBCEModel
    from training.dataloaders import make_dataloaders
    from training.evaluate import evaluate
    from training.loss import estimate_pos_weight
    from training.seed import set_reproducible_seed
except ModuleNotFoundError:
    from ..data.gem_data import GemClassifierDataset
    from ..models.multi_label_bce import GroupedMultiTaskBCEModel, MultiLabelBCEModel
    from .dataloaders import make_dataloaders
    from .evaluate import evaluate
    from .loss import estimate_pos_weight
    from .seed import set_reproducible_seed


class WeightedBCEWithLogitsLoss(nn.Module):
    def __init__(
        self,
        *,
        pos_weight: torch.Tensor | None,
        label_weight: torch.Tensor | None,
    ) -> None:
        super().__init__()
        self.register_buffer("pos_weight", pos_weight if pos_weight is not None else None)
        self.register_buffer("label_weight", label_weight if label_weight is not None else None)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss = F.binary_cross_entropy_with_logits(
            logits,
            targets,
            pos_weight=self.pos_weight,
            reduction="none",
        )
        if self.label_weight is not None:
            loss = loss * self.label_weight
        return loss.mean()


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: torch.device,
    *,
    label_names: tuple[str, ...],
) -> dict[str, float]:
    model.train()
    total_loss = 0.0
    total_examples = 0
    per_label_bce_sum = torch.zeros(len(label_names), dtype=torch.float64)

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
        batch_bce = F.binary_cross_entropy_with_logits(logits.detach(), targets, reduction="none").mean(dim=0)
        per_label_bce_sum += batch_bce.detach().cpu().to(dtype=torch.float64) * batch_size

    metrics = {"loss": total_loss / max(total_examples, 1)}
    per_label_bce = per_label_bce_sum / max(total_examples, 1)
    for index, label in enumerate(label_names):
        metrics[f"{label}_bce"] = float(per_label_bce[index])
    return metrics


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
    label_weight = label_weight_for(config, train_dataset.target_columns, device)
    loss_fn = WeightedBCEWithLogitsLoss(pos_weight=pos_weight, label_weight=label_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
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


def build_model(config: TrainingConfig, train_dataset: GemClassifierDataset) -> nn.Module:
    if config.grouped_heads:
        return GroupedMultiTaskBCEModel(
            input_dim=len(train_dataset.feature_columns),
            output_names=train_dataset.target_columns,
            trunk_dims=config.hidden_dims,
            head_hidden_dim=config.head_hidden_dim,
            dropout=config.dropout,
            batch_norm=config.batch_norm,
        )
    return MultiLabelBCEModel(
        input_dim=len(train_dataset.feature_columns),
        output_dim=len(train_dataset.target_columns),
        hidden_dims=config.hidden_dims,
        dropout=config.dropout,
        batch_norm=config.batch_norm,
    )


def build_scheduler(
    config: TrainingConfig,
    optimizer: torch.optim.Optimizer,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    scheduler_name = config.scheduler.strip().lower()
    if scheduler_name in ("", "none", "false", "0", "off"):
        return None
    if scheduler_name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=config.epochs,
            eta_min=config.min_lr,
        )
    raise ValueError(f"Unsupported scheduler: {config.scheduler}")


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


def label_weight_for(
    config: TrainingConfig,
    target_columns: tuple[str, ...],
    device: torch.device,
) -> torch.Tensor:
    values = []
    for label in target_columns:
        if label.startswith("hit_") and label.endswith("_primary"):
            values.append(config.primary_loss_weight)
        elif label.startswith("secondary_in_"):
            values.append(config.secondary_loss_weight)
        else:
            values.append(1.0)
    return torch.as_tensor(values, dtype=torch.float32, device=device)


def config_payload_for(
    config: TrainingConfig,
    train_dataset: GemClassifierDataset,
    training_dataset: Dataset,
    validation_dataset: Dataset,
    device: torch.device,
    pos_weight: torch.Tensor | None,
    label_weight: torch.Tensor | None,
) -> dict[str, Any]:
    payload = asdict(config)
    payload.update(
        {
            "feature_columns": list(train_dataset.feature_columns),
            "feature_mean": [float(value) for value in train_dataset.feature_mean],
            "feature_std": [float(value) for value in train_dataset.feature_std],
            "normalize_inputs": train_dataset.normalize_features,
            "target_columns": list(train_dataset.target_columns),
            "target_positive_rates": {
                label: float(rate)
                for label, rate in zip(train_dataset.target_columns, train_dataset.target_positive_rates)
            },
            "input_dim": len(train_dataset.feature_columns),
            "output_dim": len(train_dataset.target_columns),
            "device": str(device),
            "source_train_examples": len(train_dataset),
            "train_examples": len(training_dataset),
            "validation_examples": len(validation_dataset),
            "pos_weight_values": None if pos_weight is None else [float(value) for value in pos_weight.detach().cpu()],
            "label_weight_values": None if label_weight is None else [float(value) for value in label_weight.detach().cpu()],
        }
    )
    payload["hidden_dims"] = list(config.hidden_dims)
    return payload
