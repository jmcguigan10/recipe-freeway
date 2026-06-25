from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn


class MultiLabelBCEModel(nn.Module):
    """Configurable MLP for multi-label BCE training.

    The module returns raw logits. Pair it with ``nn.BCEWithLogitsLoss`` during
    training rather than applying a sigmoid in ``forward``.
    """

    def __init__(
        self,
        input_dim: int = 4,
        output_dim: int = 6,
        hidden_dims: Sequence[int] = (64, 64),
        dropout: float = 0.1,
    ) -> None:
        super().__init__()

        self.input_dim = _positive_int("input_dim", input_dim)
        self.output_dim = _positive_int("output_dim", output_dim)
        self.hidden_dims = tuple(_positive_int("hidden_dim", dim) for dim in hidden_dims)
        if not 0.0 <= dropout < 1.0:
            raise ValueError(f"dropout must be in [0, 1): {dropout}")
        self.dropout = float(dropout)

        layers: list[nn.Module] = []
        previous_dim = self.input_dim
        for hidden_dim in self.hidden_dims:
            layers.append(nn.Linear(previous_dim, hidden_dim))
            layers.append(nn.ReLU())
            if self.dropout > 0.0:
                layers.append(nn.Dropout(self.dropout))
            previous_dim = hidden_dim

        layers.append(nn.Linear(previous_dim, self.output_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)


def _positive_int(name: str, value: int) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return parsed
