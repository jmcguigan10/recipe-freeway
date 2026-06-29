from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import torch
import torch.nn.functional as F
from torch import nn

LOSS_KINDS = ("grouped-bce", "focal-bce")
TASK_GROUPS = ("primary", "secondary", "other")


def build_bce_with_logits_loss(
    pos_weight: torch.Tensor | Iterable[float] | None = None,
    *,
    device: torch.device | str | None = None,
    reduction: str = "mean",
) -> nn.BCEWithLogitsLoss:
    if pos_weight is not None:
        pos_weight = torch.as_tensor(pos_weight, dtype=torch.float32, device=device)
    return nn.BCEWithLogitsLoss(pos_weight=pos_weight, reduction=reduction)


class MultiTaskBCEWithLogitsLoss(nn.Module):
    """Grouped BCE loss for primary, secondary, and fallback label tasks."""

    def __init__(
        self,
        *,
        target_columns: Sequence[str],
        pos_weight: torch.Tensor | Iterable[float] | None = None,
        task_weights: Mapping[str, float] | None = None,
        loss_kind: str = "grouped-bce",
        focal_gamma: float = 2.0,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        self.target_columns = tuple(target_columns)
        if not self.target_columns:
            raise ValueError("target_columns must not be empty")

        if loss_kind not in LOSS_KINDS:
            raise ValueError(f"Unsupported loss kind: {loss_kind}")
        self.loss_kind = loss_kind
        self.focal_gamma = _non_negative_float("focal_gamma", focal_gamma)

        weights = dict.fromkeys(TASK_GROUPS, 1.0)
        if task_weights is not None:
            unknown_groups = sorted(set(task_weights) - set(TASK_GROUPS))
            if unknown_groups:
                raise ValueError(f"Unsupported task weight group(s): {', '.join(unknown_groups)}")
            weights.update(task_weights)
        self.task_weights = {
            group: _non_negative_float(f"{group}_loss_weight", value)
            for group, value in weights.items()
        }

        self.group_indices = label_group_indices(self.target_columns)
        active_weight_sum = sum(
            self.task_weights[group]
            for group, indices in self.group_indices.items()
            if indices and self.task_weights[group] > 0.0
        )
        if active_weight_sum <= 0.0:
            raise ValueError("At least one non-empty task group must have a positive loss weight")

        if pos_weight is None:
            parsed_pos_weight = None
        else:
            parsed_pos_weight = torch.as_tensor(pos_weight, dtype=torch.float32, device=device)
            if parsed_pos_weight.numel() != len(self.target_columns):
                raise ValueError("pos_weight length must match the number of target columns")
        self.register_buffer("pos_weight", parsed_pos_weight)
        self.register_buffer(
            "label_weight",
            torch.as_tensor(
                [self.task_weights[label_group_for(label)] for label in self.target_columns],
                dtype=torch.float32,
                device=device,
            ),
        )

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.component_losses(logits, targets)["loss"]

    def component_losses(self, logits: torch.Tensor, targets: torch.Tensor) -> dict[str, torch.Tensor]:
        if logits.shape != targets.shape:
            raise ValueError(f"logits and targets must have the same shape: {logits.shape} != {targets.shape}")
        if logits.ndim != 2:
            raise ValueError(f"logits and targets must be rank-2 tensors: {logits.shape}")
        if logits.shape[1] != len(self.target_columns):
            raise ValueError("logit dimension must match the number of target columns")

        elementwise_loss = F.binary_cross_entropy_with_logits(
            logits,
            targets,
            pos_weight=self.pos_weight,
            reduction="none",
        )
        if self.loss_kind == "focal-bce":
            probabilities = torch.sigmoid(logits)
            p_t = probabilities * targets + (1.0 - probabilities) * (1.0 - targets)
            elementwise_loss = elementwise_loss * (1.0 - p_t).pow(self.focal_gamma)

        losses: dict[str, torch.Tensor] = {}
        weighted_total = logits.new_tensor(0.0)
        active_weight_sum = logits.new_tensor(0.0)
        for group, indices in self.group_indices.items():
            if not indices:
                continue
            group_loss = elementwise_loss[:, indices].mean()
            losses[f"{group}_loss"] = group_loss
            weight = self.task_weights[group]
            if weight > 0.0:
                weighted_total = weighted_total + group_loss * weight
                active_weight_sum = active_weight_sum + weight

        losses["loss"] = weighted_total / active_weight_sum
        return losses

    def task_loss_weights(self) -> dict[str, float]:
        return dict(self.task_weights)


def label_group_for(label: str) -> str:
    if label.startswith("hit_") and label.endswith("_primary"):
        return "primary"
    if label.startswith("secondary_in_"):
        return "secondary"
    return "other"


def label_group_indices(target_columns: Sequence[str]) -> dict[str, tuple[int, ...]]:
    return {
        group: tuple(
            index
            for index, label in enumerate(target_columns)
            if label_group_for(label) == group
        )
        for group in TASK_GROUPS
    }


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


def _non_negative_float(name: str, value: float) -> float:
    parsed = float(value)
    if parsed < 0.0:
        raise ValueError(f"{name} must be non-negative: {value}")
    return parsed
