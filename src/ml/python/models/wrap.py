from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn

from .basic_nn import NNBlock
from .registry import (
    BlockCfgs,
    LinearBlockCfgs,
    NNBlockCfgs,
)


class LongWrap(nn.Module):
    def __init__(self, cfgs: Sequence[BlockCfgs]) -> None:
        super().__init__()
        self.cfgs = tuple(cfgs)
        if not self.cfgs:
            raise ValueError("LongWrap cfgs must not be empty")
        self.input_dim = _positive_dim("input_dim", self.cfgs[0].input_dim)
        self.output_dim = _positive_dim("output_dim", self.cfgs[-1].output_dim)

        self.blocks = nn.ModuleList()
        self.layer_nums: list[int] = []
        previous_output_dim: int | None = None
        for nth_layer, cfg in enumerate(self.cfgs):
            input_dim = _positive_dim("input_dim", cfg.input_dim)
            output_dim = _positive_dim("output_dim", cfg.output_dim)
            if previous_output_dim is not None and input_dim != previous_output_dim:
                raise ValueError(
                    "LongWrap cfg dimensions must connect: "
                    f"layer {nth_layer} input_dim={input_dim} "
                    f"does not match previous output_dim={previous_output_dim}"
                )
            previous_output_dim = output_dim
            self.layer_nums.append(nth_layer)
            block = self._build_block(nth_layer, cfg)
            self.blocks.append(block)

    def _build_block(self, nth_layer: int, cfg: BlockCfgs) -> nn.Module:
        if isinstance(cfg, NNBlockCfgs):
            return NNBlock(nth_layer, cfg)
        if isinstance(cfg, LinearBlockCfgs):
            return nn.Linear(cfg.input_dim, cfg.output_dim)

        raise TypeError(f"Unsupported block cfg: {type(cfg).__name__}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for block in self.blocks:
            x = block(x)
        return x


class LatWrap(nn.Module):
    def __init__(
        self,
        trunk: LongWrap,
        *heads: LongWrap,
        output_indices: Sequence[Sequence[int]] | None = None,
        output_dim: int | None = None,
    ) -> None:
        super().__init__()
        if not isinstance(trunk, LongWrap):
            raise TypeError("LatWrap trunk must be a LongWrap")
        if not heads:
            raise ValueError("LatWrap requires at least one head LongWrap")

        self.trunk = trunk
        self.heads = nn.ModuleList()
        for index, head in enumerate(heads):
            if not isinstance(head, LongWrap):
                raise TypeError("LatWrap heads must be LongWrap instances")
            if head.input_dim != trunk.output_dim:
                raise ValueError(
                    "LatWrap head input_dim must match trunk output_dim: "
                    f"head {index} input_dim={head.input_dim}, trunk output_dim={trunk.output_dim}"
                )
            self.heads.append(head)

        self.output_indices = _parse_output_indices(output_indices, len(self.heads))
        if self.output_indices is None:
            self.output_dim = None
        else:
            self.output_dim = _resolve_output_dim(self.output_indices, output_dim)
            for head, indices in zip(self.heads, self.output_indices):
                if head.output_dim != len(indices):
                    raise ValueError(
                        "LatWrap head output_dim must match output index count: "
                        f"{head.output_dim} != {len(indices)}"
                    )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor | list[torch.Tensor]:
        trunk_output = self.trunk(inputs)
        head_outputs = [head(trunk_output) for head in self.heads]
        if self.output_indices is None:
            return head_outputs

        outputs = inputs.new_empty((inputs.shape[0], self.output_dim))
        for head_output, indices in zip(head_outputs, self.output_indices):
            outputs[:, list(indices)] = head_output
        return outputs


def _positive_dim(name: str, value: int) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return parsed


def _parse_output_indices(
    output_indices: Sequence[Sequence[int]] | None,
    head_count: int,
) -> tuple[tuple[int, ...], ...] | None:
    if output_indices is None:
        return None
    parsed = tuple(tuple(int(index) for index in indices) for indices in output_indices)
    if len(parsed) != head_count:
        raise ValueError("output_indices length must match LatWrap head count")
    if any(not indices for indices in parsed):
        raise ValueError("output_indices entries must not be empty")
    return parsed


def _resolve_output_dim(
    output_indices: tuple[tuple[int, ...], ...],
    output_dim: int | None,
) -> int:
    flat_indices = tuple(index for indices in output_indices for index in indices)
    if any(index < 0 for index in flat_indices):
        raise ValueError("output_indices must be non-negative")
    parsed_output_dim = max(flat_indices) + 1 if output_dim is None else _positive_dim("output_dim", output_dim)
    if len(set(flat_indices)) != len(flat_indices):
        raise ValueError("output_indices must not contain duplicates")
    expected_indices = set(range(parsed_output_dim))
    actual_indices = set(flat_indices)
    if actual_indices != expected_indices:
        raise ValueError("output_indices must cover every output position exactly once")
    return parsed_output_dim
