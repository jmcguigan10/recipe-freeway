from __future__ import annotations

import torch
from torch import nn

from .registry import NNBlockCfgs


class NNBlock(nn.Module):
    def __init__(self, n_layer: int, cfg: NNBlockCfgs) -> None:
        super().__init__()
        self.n_layer = n_layer
        self.linear = nn.Linear(cfg.input_dim, cfg.output_dim)
        if cfg.do_bn:
            self.batchnorm = nn.BatchNorm1d(cfg.output_dim)
        else:
            self.batchnorm = nn.Identity()
        self.activation = cfg.activation_factory()
        self.dropout = nn.Dropout(cfg.dropout) if cfg.dropout > 0.0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.linear(x)
        x = self._batchnorm(x)
        x = self.activation(x)
        return self.dropout(x)

    def _batchnorm(self, x: torch.Tensor) -> torch.Tensor:
        if isinstance(self.batchnorm, nn.Identity):
            return x

        shape = x.shape
        x = x.reshape(-1, shape[-1])
        x = self.batchnorm(x)
        return x.reshape(*shape[:-1], shape[-1])
