from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import torch

from .derived import DEFAULT_EDGE_BAND_MM, DEFAULT_NEAR_BAND_MM
from .registry import DEFAULT_FEATURE_COLUMNS, DEFAULT_TARGET_COLUMNS, GemDataConfig


def build_gem_data_config(
    csv_path: str | Path,
    *,
    feature_columns: Sequence[str] | str | None = None,
    target_columns: Sequence[str] | str | None = None,
    geometry_config: str | Path | Mapping[str, Any] | None = None,
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM,
    near_band_mm: float = DEFAULT_NEAR_BAND_MM,
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
    parsed_edge_band_mm, parsed_near_band_mm = parse_regime_bands(edge_band_mm, near_band_mm)

    return GemDataConfig(
        csv_path=parse_csv_path(csv_path),
        feature_columns=parsed_feature_columns,
        target_columns=parsed_target_columns,
        geometry_config=parse_geometry_config(geometry_config),
        edge_band_mm=parsed_edge_band_mm,
        near_band_mm=parsed_near_band_mm,
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


def parse_geometry_config(
    geometry_config: str | Path | Mapping[str, Any] | None,
) -> str | Path | Mapping[str, Any] | None:
    if geometry_config is None or isinstance(geometry_config, Mapping):
        return geometry_config
    text = str(geometry_config).strip()
    if text.lower() in ("", "none", "false", "0", "off", "null"):
        return None
    return text


def parse_regime_bands(edge_band_mm: float, near_band_mm: float) -> tuple[float, float]:
    edge = positive_float("edge_band_mm", edge_band_mm)
    near = positive_float("near_band_mm", near_band_mm)
    if near <= edge:
        raise ValueError(f"near_band_mm must be greater than edge_band_mm: {near} <= {edge}")
    return edge, near


def positive_float(name: str, value: float) -> float:
    parsed = float(value)
    if parsed <= 0.0:
        raise ValueError(f"{name} must be positive: {value}")
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
