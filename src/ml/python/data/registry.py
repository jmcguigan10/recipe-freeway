from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from .derived import DEFAULT_EDGE_BAND_MM, DEFAULT_NEAR_BAND_MM


DEFAULT_FEATURE_COLUMNS = ("x0_mm", "y0_mm", "xprime", "yprime")
DEFAULT_TARGET_COLUMNS = (
    "hit_bhc_primary",
    "hit_bhd_primary",
    "hit_gem0_primary",
    "secondary_in_bhc",
    "secondary_in_bhd",
    "secondary_in_gem0",
)


@dataclass(frozen=True)
class GemDataConfig:
    csv_path: str | Path
    feature_columns: Sequence[str] = DEFAULT_FEATURE_COLUMNS
    target_columns: Sequence[str] = DEFAULT_TARGET_COLUMNS
    geometry_config: str | Path | Mapping[str, Any] | None = None
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM
    near_band_mm: float = DEFAULT_NEAR_BAND_MM
    dtype: torch.dtype = torch.float32
    transform: Callable[[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]] | None = None
    normalize_features: bool = True
    feature_mean: Sequence[float] | None = None
    feature_std: Sequence[float] | None = None
