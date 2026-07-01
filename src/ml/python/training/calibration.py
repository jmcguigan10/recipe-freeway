from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader

from .metrics import calibrated_probability_logits


@dataclass(frozen=True)
class PlattCalibrator:
    scale: torch.Tensor
    bias: torch.Tensor
    label_names: tuple[str, ...]

    def transform_logits(self, logits: torch.Tensor) -> torch.Tensor:
        scale = self.scale.to(device=logits.device, dtype=logits.dtype).reshape(1, -1)
        bias = self.bias.to(device=logits.device, dtype=logits.dtype).reshape(1, -1)
        return logits * scale + bias

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": "per_label_platt",
            "label_names": list(self.label_names),
            "scale": [float(value) for value in self.scale.detach().cpu()],
            "bias": [float(value) for value in self.bias.detach().cpu()],
        }


@torch.no_grad()
def collect_logits_and_targets(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    *,
    pos_weight: torch.Tensor | None = None,
    calibrate_pos_weight_logits: bool = True,
) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    logits_batches = []
    target_batches = []
    for features, targets in loader:
        features = features.to(device=device, non_blocking=True)
        logits = model(features).detach().cpu()
        if calibrate_pos_weight_logits:
            logits = calibrated_probability_logits(logits, pos_weight.cpu() if pos_weight is not None else None)
        logits_batches.append(logits)
        target_batches.append(targets.detach().cpu().to(dtype=torch.float32))
    if not logits_batches:
        raise ValueError("Cannot collect calibration logits from an empty loader")
    return torch.cat(logits_batches, dim=0), torch.cat(target_batches, dim=0)


def fit_platt_calibrator(
    logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    label_names: tuple[str, ...],
    max_iter: int = 100,
) -> PlattCalibrator:
    logits = logits.detach().to(dtype=torch.float32)
    targets = targets.detach().to(dtype=torch.float32)
    if logits.shape != targets.shape:
        raise ValueError("Calibration logits and targets must have matching shape")
    if logits.ndim != 2:
        raise ValueError("Calibration logits must be rank 2")

    scale = torch.ones(logits.shape[1], dtype=torch.float32, requires_grad=True)
    bias = torch.zeros(logits.shape[1], dtype=torch.float32, requires_grad=True)
    optimizer = torch.optim.LBFGS([scale, bias], lr=0.25, max_iter=max_iter, line_search_fn="strong_wolfe")

    def closure() -> torch.Tensor:
        optimizer.zero_grad(set_to_none=True)
        calibrated = logits * scale.reshape(1, -1) + bias.reshape(1, -1)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(calibrated, targets)
        loss.backward()
        return loss

    optimizer.step(closure)
    with torch.no_grad():
        scale.clamp_(min=0.01, max=100.0)
    return PlattCalibrator(scale=scale.detach(), bias=bias.detach(), label_names=tuple(label_names))
