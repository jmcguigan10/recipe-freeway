from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from torch import nn


@dataclass
class NNBlockCfgs:
    input_dim: int
    output_dim: int
    do_bn: bool = True
    dropout: float = 0.0
    activation_factory: Callable[[], nn.Module] = nn.ReLU


@dataclass
class LinearBlockCfgs:
    input_dim: int
    output_dim: int

BlockCfgs = NNBlockCfgs | LinearBlockCfgs
