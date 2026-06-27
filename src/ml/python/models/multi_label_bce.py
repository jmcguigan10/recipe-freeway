from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn


class MultiLabelBCEModel(nn.Module):
    """Configurable MLP for multi-label BCE training."""

    def __init__(
        self,
        input_dim: int = 4,
        output_dim: int = 6,
        hidden_dims: Sequence[int] = (64, 64),
        dropout: float = 0.1,
        batch_norm: bool = False,
    ) -> None:
        super().__init__()

        self.input_dim = _positive_int("input_dim", input_dim)
        self.output_dim = _positive_int("output_dim", output_dim)
        self.hidden_dims = tuple(_positive_int("hidden_dim", dim) for dim in hidden_dims)
        self.dropout = _dropout_value(dropout)
        self.batch_norm = bool(batch_norm)
        self.network = nn.Sequential(
            *hidden_layers(
                self.input_dim,
                self.hidden_dims,
                dropout=self.dropout,
                batch_norm=self.batch_norm,
            ),
            nn.Linear(self.hidden_dims[-1], self.output_dim),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


class GroupedMultiTaskBCEModel(nn.Module):
    """Shared trunk with grouped primary and secondary classifier heads."""

    def __init__(
        self,
        *,
        input_dim: int,
        output_names: Sequence[str],
        trunk_dims: Sequence[int] = (256, 256, 256),
        head_hidden_dim: int = 128,
        dropout: float = 0.05,
        batch_norm: bool = True,
    ) -> None:
        super().__init__()
        self.input_dim = _positive_int("input_dim", input_dim)
        self.output_names = tuple(output_names)
        if not self.output_names:
            raise ValueError("output_names must not be empty")
        self.output_dim = len(self.output_names)
        self.trunk_dims = tuple(_positive_int("trunk_dim", dim) for dim in trunk_dims)
        self.head_hidden_dim = _positive_int("head_hidden_dim", head_hidden_dim)
        self.dropout = _dropout_value(dropout)
        self.batch_norm = bool(batch_norm)

        self.primary_indices = tuple(
            index for index, name in enumerate(self.output_names) if name.startswith("hit_") and name.endswith("_primary")
        )
        self.secondary_indices = tuple(
            index for index, name in enumerate(self.output_names) if name.startswith("secondary_in_")
        )
        other_indices = tuple(
            index for index in range(self.output_dim)
            if index not in self.primary_indices and index not in self.secondary_indices
        )
        if other_indices:
            raise ValueError(
                "GroupedMultiTaskBCEModel only supports hit_*_primary and secondary_in_* labels; "
                + ", ".join(self.output_names[index] for index in other_indices)
            )

        self.trunk = nn.Sequential(
            *hidden_layers(
                self.input_dim,
                self.trunk_dims,
                dropout=self.dropout,
                batch_norm=self.batch_norm,
            )
        )
        trunk_output_dim = self.trunk_dims[-1]
        self.primary_head = make_head(
            trunk_output_dim,
            len(self.primary_indices),
            self.head_hidden_dim,
            dropout=self.dropout,
            batch_norm=self.batch_norm,
        ) if self.primary_indices else None
        self.secondary_head = make_head(
            trunk_output_dim,
            len(self.secondary_indices),
            self.head_hidden_dim,
            dropout=self.dropout,
            batch_norm=self.batch_norm,
        ) if self.secondary_indices else None

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        shared = self.trunk(inputs)
        outputs = inputs.new_empty((inputs.shape[0], self.output_dim))
        if self.primary_head is not None:
            outputs[:, self.primary_indices] = self.primary_head(shared)
        if self.secondary_head is not None:
            outputs[:, self.secondary_indices] = self.secondary_head(shared)
        return outputs


def hidden_layers(
    input_dim: int,
    hidden_dims: Sequence[int],
    *,
    dropout: float,
    batch_norm: bool,
) -> list[nn.Module]:
    if not hidden_dims:
        raise ValueError("hidden_dims must not be empty")
    layers: list[nn.Module] = []
    previous_dim = input_dim
    for hidden_dim in hidden_dims:
        layers.append(nn.Linear(previous_dim, hidden_dim))
        if batch_norm:
            layers.append(nn.BatchNorm1d(hidden_dim))
        layers.append(nn.ReLU())
        if dropout > 0.0:
            layers.append(nn.Dropout(dropout))
        previous_dim = hidden_dim
    return layers


def make_head(
    input_dim: int,
    output_dim: int,
    hidden_dim: int,
    *,
    dropout: float,
    batch_norm: bool,
) -> nn.Sequential:
    layers: list[nn.Module] = [nn.Linear(input_dim, hidden_dim)]
    if batch_norm:
        layers.append(nn.BatchNorm1d(hidden_dim))
    layers.append(nn.ReLU())
    if dropout > 0.0:
        layers.append(nn.Dropout(dropout))
    layers.append(nn.Linear(hidden_dim, output_dim))
    return nn.Sequential(*layers)


def _positive_int(name: str, value: int) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return parsed


def _dropout_value(value: float) -> float:
    parsed = float(value)
    if not 0.0 <= parsed < 1.0:
        raise ValueError(f"dropout must be in [0, 1): {value}")
    return parsed
