from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader


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
    component_loss_sums: dict[str, float] = {}

    for features, targets in loader:
        features = features.to(device=device, non_blocking=True)
        targets = targets.to(device=device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        logits = model(features)
        loss_components = component_losses(loss_fn, logits, targets)
        loss = loss_components["loss"]
        loss.backward()
        optimizer.step()

        batch_size = features.shape[0]
        total_loss += float(loss.detach().cpu()) * batch_size
        total_examples += batch_size
        accumulate_component_losses(component_loss_sums, loss_components, batch_size)
        batch_bce = F.binary_cross_entropy_with_logits(logits.detach(), targets, reduction="none").mean(dim=0)
        per_label_bce_sum += batch_bce.detach().cpu().to(dtype=torch.float64) * batch_size

    metrics = {"loss": total_loss / max(total_examples, 1)}
    for key, value in component_loss_sums.items():
        metrics[key] = value / max(total_examples, 1)
    per_label_bce = per_label_bce_sum / max(total_examples, 1)
    for index, label in enumerate(label_names):
        metrics[f"{label}_bce"] = float(per_label_bce[index])
    return metrics


def component_losses(
    loss_fn: nn.Module,
    logits: torch.Tensor,
    targets: torch.Tensor,
) -> dict[str, torch.Tensor]:
    if hasattr(loss_fn, "component_losses"):
        return loss_fn.component_losses(logits, targets)
    return {"loss": loss_fn(logits, targets)}


def accumulate_component_losses(
    loss_sums: dict[str, float],
    loss_components: dict[str, torch.Tensor],
    batch_size: int,
) -> None:
    for key, value in loss_components.items():
        if key != "loss":
            loss_sums[key] = loss_sums.get(key, 0.0) + float(value.detach().cpu()) * batch_size
