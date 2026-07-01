from __future__ import annotations

import torch
from torch import nn
from torch.utils.data import DataLoader

from src.ml.python.io.args import TrainingConfig

try:
    from ..data import GemClassifierDataset
    from ..models import build_latwrap_classifier, build_longwrap_classifier
    from .loss import MultiTaskBCEWithLogitsLoss, estimate_pos_weight
except ImportError:
    from data import GemClassifierDataset
    from models import build_latwrap_classifier, build_longwrap_classifier
    from training.loss import MultiTaskBCEWithLogitsLoss, estimate_pos_weight


def build_model(config: TrainingConfig, train_dataset: GemClassifierDataset) -> nn.Module:
    if config.grouped_heads:
        return build_latwrap_classifier(
            input_dim=len(train_dataset.feature_columns),
            output_names=train_dataset.target_columns,
            trunk_dims=config.hidden_dims,
            head_hidden_dim=config.head_hidden_dim,
            dropout=config.dropout,
            batch_norm=config.batch_norm,
        )

    return build_longwrap_classifier(
        input_dim=len(train_dataset.feature_columns),
        output_dim=len(train_dataset.target_columns),
        hidden_dims=config.hidden_dims,
        dropout=config.dropout,
        batch_norm=config.batch_norm,
    )


def build_optimizer(
    config: TrainingConfig,
    model: nn.Module,
) -> torch.optim.Optimizer:
    return torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)


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
        weights = estimate_pos_weight(train_loader, device=device)
        if config.pos_weight_max is not None:
            weights = weights.clamp_max(float(config.pos_weight_max))
        return weights
    values = [float(value.strip()) for value in config.pos_weight.split(",") if value.strip()]
    if not values:
        raise ValueError("--pos-weight must be 'auto', 'none', or comma-separated floats")
    return torch.as_tensor(values, dtype=torch.float32, device=device)


def build_loss_fn(
    config: TrainingConfig,
    target_columns: tuple[str, ...],
    pos_weight: torch.Tensor | None,
    device: torch.device,
) -> MultiTaskBCEWithLogitsLoss:
    return MultiTaskBCEWithLogitsLoss(
        target_columns=target_columns,
        pos_weight=pos_weight,
        task_weights={
            "primary": config.primary_loss_weight,
            "secondary": config.secondary_loss_weight,
            "other": config.other_loss_weight,
        },
        loss_kind=config.loss,
        focal_gamma=config.focal_gamma,
        device=device,
    )
