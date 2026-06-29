from __future__ import annotations

from collections.abc import Sequence
from typing import Callable

from torch import nn

from .registry import LinearBlockCfgs, NNBlockCfgs
from .wrap import LatWrap, LongWrap


def build_nnblockcfgs(
    input_dim: int,
    output_dim: int,
    do_bn: bool = True,
    dropout: float = 0.0,
    activation_factory: Callable[[], nn.Module] = nn.ReLU,
) -> NNBlockCfgs:
    return NNBlockCfgs(
        input_dim=positive_int("input_dim", input_dim),
        output_dim=positive_int("output_dim", output_dim),
        do_bn=do_bn,
        dropout=dropout_value(dropout),
        activation_factory=activation_factory,
    )


def build_linearblockcfgs(
    input_dim: int,
    output_dim: int,
) -> LinearBlockCfgs:
    return LinearBlockCfgs(
        input_dim=positive_int("input_dim", input_dim),
        output_dim=positive_int("output_dim", output_dim),
    )


def build_nnblockcfg_sequence(
    input_dim: int,
    output_dims: Sequence[int],
    *,
    do_bn: bool,
    dropout: float,
    activation_factory: Callable[[], nn.Module] = nn.ReLU,
) -> list[NNBlockCfgs]:
    parsed_input_dim = positive_int("input_dim", input_dim)
    parsed_output_dims = tuple(positive_int("hidden_dim", dim) for dim in output_dims)
    if not parsed_output_dims:
        raise ValueError("hidden_dims must not be empty")

    parsed_dropout = dropout_value(dropout)
    cfgs: list[NNBlockCfgs] = []
    previous_dim = parsed_input_dim
    for output_dim in parsed_output_dims:
        cfgs.append(
            NNBlockCfgs(
                input_dim=previous_dim,
                output_dim=output_dim,
                do_bn=do_bn,
                dropout=parsed_dropout,
                activation_factory=activation_factory,
            )
        )
        previous_dim = output_dim
    return cfgs


def build_longwrap_classifier(
    input_dim: int = 4,
    output_dim: int = 6,
    hidden_dims: Sequence[int] = (64, 64),
    dropout: float = 0.1,
    batch_norm: bool = False,
    activation_factory: Callable[[], nn.Module] = nn.ReLU,
) -> LongWrap:
    hidden_cfgs = build_nnblockcfg_sequence(
        input_dim,
        hidden_dims,
        do_bn=bool(batch_norm),
        dropout=dropout,
        activation_factory=activation_factory,
    )
    return LongWrap(
        [
            *hidden_cfgs,
            build_linearblockcfgs(hidden_cfgs[-1].output_dim, output_dim),
        ]
    )


def build_latwrap_classifier(
    *,
    input_dim: int,
    output_names: Sequence[str],
    trunk_dims: Sequence[int] = (256, 256, 256),
    head_hidden_dim: int = 128,
    dropout: float = 0.05,
    batch_norm: bool = True,
    activation_factory: Callable[[], nn.Module] = nn.ReLU,
) -> LatWrap:
    parsed_input_dim = positive_int("input_dim", input_dim)
    parsed_output_names = tuple(output_names)
    if not parsed_output_names:
        raise ValueError("output_names must not be empty")

    parsed_trunk_dims = tuple(positive_int("trunk_dim", dim) for dim in trunk_dims)
    if not parsed_trunk_dims:
        raise ValueError("hidden_dims must not be empty")
    parsed_head_hidden_dim = positive_int("head_hidden_dim", head_hidden_dim)
    parsed_dropout = dropout_value(dropout)
    parsed_batch_norm = bool(batch_norm)

    task_indices = grouped_output_indices(parsed_output_names)
    trunk_cfgs = build_nnblockcfg_sequence(
        parsed_input_dim,
        parsed_trunk_dims,
        do_bn=parsed_batch_norm,
        dropout=parsed_dropout,
        activation_factory=activation_factory,
    )
    trunk = LongWrap(trunk_cfgs)

    heads = [
        build_classifier_head(
            parsed_trunk_dims[-1],
            len(indices),
            parsed_head_hidden_dim,
            dropout=parsed_dropout,
            batch_norm=parsed_batch_norm,
            activation_factory=activation_factory,
        )
        for indices in task_indices
    ]

    return LatWrap(trunk, *heads, output_indices=task_indices, output_dim=len(parsed_output_names))


def grouped_output_indices(output_names: Sequence[str]) -> tuple[tuple[int, ...], ...]:
    parsed_output_names = tuple(output_names)
    primary_indices = tuple(
        index
        for index, name in enumerate(parsed_output_names)
        if name.startswith("hit_") and name.endswith("_primary")
    )
    secondary_indices = tuple(
        index for index, name in enumerate(parsed_output_names) if name.startswith("secondary_in_")
    )
    grouped_indices = set(primary_indices) | set(secondary_indices)
    other_indices = tuple(index for index in range(len(parsed_output_names)) if index not in grouped_indices)
    if other_indices:
        raise ValueError(
            "LatWrap grouped architecture only supports hit_*_primary and secondary_in_* labels; "
            + ", ".join(parsed_output_names[index] for index in other_indices)
        )

    task_indices: list[tuple[int, ...]] = []
    if primary_indices:
        task_indices.append(primary_indices)
    if secondary_indices:
        task_indices.append(secondary_indices)
    if not task_indices:
        raise ValueError("LatWrap grouped architecture requires at least one non-empty output group")
    return tuple(task_indices)


def build_classifier_head(
    input_dim: int,
    output_dim: int,
    hidden_dim: int,
    *,
    dropout: float,
    batch_norm: bool,
    activation_factory: Callable[[], nn.Module] = nn.ReLU,
) -> LongWrap:
    hidden_cfgs = build_nnblockcfg_sequence(
        input_dim,
        (hidden_dim,),
        do_bn=bool(batch_norm),
        dropout=dropout,
        activation_factory=activation_factory,
    )
    return LongWrap(
        [
            *hidden_cfgs,
            build_linearblockcfgs(hidden_cfgs[-1].output_dim, output_dim),
        ]
    )


def positive_int(name: str, value: int) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return parsed


def dropout_value(value: float) -> float:
    parsed = float(value)
    if not 0.0 <= parsed < 1.0:
        raise ValueError(f"dropout must be in [0, 1): {value}")
    return parsed
