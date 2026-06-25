from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import torch
from torch import nn


def save_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    *,
    epoch: int,
    best_val_loss: float,
    config_payload: dict[str, Any],
) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch,
            "best_val_loss": best_val_loss,
            "feature_columns": config_payload["feature_columns"],
            "target_columns": config_payload["target_columns"],
            "config": config_payload,
        },
        path,
    )


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_metrics_csv(path: str | Path, rows: list[dict[str, float | int]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with Path(path).open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
