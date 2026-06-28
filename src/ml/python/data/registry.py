from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import torch


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
    dtype: torch.dtype = torch.float32
    transform: Callable[[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]] | None = None
    normalize_features: bool = True
    feature_mean: Sequence[float] | None = None
    feature_std: Sequence[float] | None = None
