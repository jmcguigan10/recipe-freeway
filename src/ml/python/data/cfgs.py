from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import torch

from .registry import DEFAULT_FEATURE_COLUMNS, DEFAULT_TARGET_COLUMNS, GemDataConfig


def build_gem_data_config(
    csv_path: str | Path,
    *,
    feature_columns: Sequence[str] | str | None = None,
    target_columns: Sequence[str] | str | None = None,
    dtype: torch.dtype = torch.float32,
    transform: Callable[[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]] | None = None,
    normalize_features: bool = True,
    feature_mean: Sequence[float] | None = None,
    feature_std: Sequence[float] | None = None,
) -> GemDataConfig:
    parsed_feature_columns = parse_columns(
        "feature_columns",
        DEFAULT_FEATURE_COLUMNS if feature_columns is None else feature_columns,
    )
    parsed_target_columns = parse_columns(
        "target_columns",
        DEFAULT_TARGET_COLUMNS if target_columns is None else target_columns,
    )
    parsed_dtype = parse_dtype(dtype)
    parsed_transform = parse_transform(transform)
    parsed_feature_mean = parse_optional_float_sequence("feature_mean", feature_mean)
    parsed_feature_std = parse_optional_float_sequence("feature_std", feature_std)
    validate_feature_stats("feature_mean", parsed_feature_mean, parsed_feature_columns)
    validate_feature_stats("feature_std", parsed_feature_std, parsed_feature_columns)

    return GemDataConfig(
        csv_path=parse_csv_path(csv_path),
        feature_columns=parsed_feature_columns,
        target_columns=parsed_target_columns,
        dtype=parsed_dtype,
        transform=parsed_transform,
        normalize_features=bool(normalize_features),
        feature_mean=parsed_feature_mean,
        feature_std=parsed_feature_std,
    )


def parse_csv_path(csv_path: str | Path) -> Path:
    if csv_path is None:
        raise ValueError("csv_path must not be None")
    path_text = str(csv_path).strip()
    if not path_text:
        raise ValueError("csv_path must not be empty")
    return Path(path_text).expanduser()


def parse_columns(name: str, columns: Sequence[str] | str) -> tuple[str, ...]:
    if isinstance(columns, str):
        parsed = tuple(column.strip() for column in columns.split(",") if column.strip())
    else:
        parsed = tuple(str(column).strip() for column in columns if str(column).strip())
    if not parsed:
        raise ValueError(f"{name} must not be empty")
    return parsed


def parse_dtype(dtype: torch.dtype) -> torch.dtype:
    if not isinstance(dtype, torch.dtype):
        raise ValueError(f"dtype must be a torch.dtype: {dtype!r}")
    return dtype


def parse_transform(
    transform: Callable[[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]] | None,
) -> Callable[[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]] | None:
    if transform is not None and not callable(transform):
        raise ValueError("transform must be callable")
    return transform


def parse_optional_float_sequence(name: str, values: Sequence[float] | str | None) -> tuple[float, ...] | None:
    if values is None:
        return None
    if isinstance(values, str):
        parsed = tuple(float(value.strip()) for value in values.split(",") if value.strip())
    else:
        parsed = tuple(float(value) for value in values)
    if not parsed:
        raise ValueError(f"{name} must not be empty when provided")
    return parsed


def validate_feature_stats(
    name: str,
    values: Sequence[float] | None,
    feature_columns: Sequence[str],
) -> None:
    if values is None:
        return
    if len(values) != len(feature_columns):
        raise ValueError(
            f"{name} length must match feature_columns length: "
            f"{len(values)} != {len(feature_columns)}"
        )
