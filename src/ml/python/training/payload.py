from __future__ import annotations

from dataclasses import asdict
from typing import Any

import torch
from torch.utils.data import Dataset

from src.ml.python.io.args import TrainingConfig

try:
    from ..data import GemClassifierDataset
except ImportError:
    from data import GemClassifierDataset


def config_payload_for(
    config: TrainingConfig,
    train_dataset: GemClassifierDataset,
    training_dataset: Dataset,
    validation_dataset: Dataset,
    device: torch.device,
    pos_weight: torch.Tensor | None,
    label_weight: torch.Tensor | None,
    task_loss_weights: dict[str, float],
) -> dict[str, Any]:
    payload = asdict(config)
    payload.update(
        {
            "feature_columns": list(train_dataset.feature_columns),
            "geometry": train_dataset.geometry,
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
            "task_loss_weights": task_loss_weights,
        }
    )
    payload["hidden_dims"] = list(config.hidden_dims)
    return payload
