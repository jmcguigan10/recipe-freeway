from __future__ import annotations

import torch
from torch import nn
from torch.utils.data import DataLoader

try:
    from training.metrics import classification_metrics
except ModuleNotFoundError:
    from .metrics import classification_metrics


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
    *,
    threshold: float = 0.5,
    label_names: tuple[str, ...] | None = None,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    total_examples = 0
    logits_batches = []
    target_batches = []

    for features, targets in loader:
        features = features.to(device=device, non_blocking=True)
        targets = targets.to(device=device, non_blocking=True)
        logits = model(features)
        loss = loss_fn(logits, targets)

        batch_size = features.shape[0]
        total_loss += float(loss.detach().cpu()) * batch_size
        total_examples += batch_size
        logits_batches.append(logits.detach().cpu())
        target_batches.append(targets.detach().cpu())

    if not logits_batches:
        raise ValueError("Cannot evaluate an empty validation loader")

    logits = torch.cat(logits_batches, dim=0)
    targets = torch.cat(target_batches, dim=0)
    metrics = classification_metrics(logits, targets, threshold=threshold, label_names=label_names)
    metrics["loss"] = total_loss / max(total_examples, 1)
    return metrics
