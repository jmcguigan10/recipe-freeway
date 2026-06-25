from __future__ import annotations

from collections.abc import Iterable

import torch
from torch import nn


def build_bce_with_logits_loss(
    pos_weight: torch.Tensor | Iterable[float] | None = None,
    *,
    device: torch.device | str | None = None,
    reduction: str = "mean",
) -> nn.BCEWithLogitsLoss:
    if pos_weight is not None:
        pos_weight = torch.as_tensor(pos_weight, dtype=torch.float32, device=device)
    return nn.BCEWithLogitsLoss(pos_weight=pos_weight, reduction=reduction)


def estimate_pos_weight(
    targets_source,
    *,
    eps: float = 1e-6,
    device: torch.device | str | None = None,
) -> torch.Tensor:
    targets = _targets_tensor(targets_source).to(dtype=torch.float32)
    if targets.numel() == 0:
        raise ValueError("Cannot estimate pos_weight from empty targets")
    if targets.ndim == 1:
        targets = targets.unsqueeze(1)

    positive = targets.sum(dim=0).clamp_min(eps)
    negative = (targets.shape[0] - targets.sum(dim=0)).clamp_min(eps)
    return (negative / positive).to(device=device)


def _targets_tensor(targets_source) -> torch.Tensor:
    if isinstance(targets_source, torch.Tensor):
        return targets_source.detach()

    if hasattr(targets_source, "targets"):
        return torch.as_tensor(targets_source.targets).detach()

    target_batches = []
    for batch in targets_source:
        if not isinstance(batch, (tuple, list)) or len(batch) < 2:
            raise TypeError("Expected batches shaped as (features, targets)")
        targets = torch.as_tensor(batch[1]).detach().cpu()
        if targets.ndim == 1:
            targets = targets.unsqueeze(0)
        target_batches.append(targets)

    if not target_batches:
        raise ValueError("Cannot estimate pos_weight from an empty dataset or loader")
    return torch.cat(target_batches, dim=0)
