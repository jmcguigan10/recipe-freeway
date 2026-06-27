from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import Dataset


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


class GemClassifierDataset(Dataset):
    """CSV-backed dataset for GEM classifier multi-label BCE training."""

    def __init__(
        self,
        config: GemDataConfig | str | Path,
        *,
        feature_columns: Sequence[str] | None = None,
        target_columns: Sequence[str] | None = None,
        dtype: torch.dtype = torch.float32,
        transform: Callable[[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]] | None = None,
        normalize_features: bool = True,
        feature_mean: Sequence[float] | None = None,
        feature_std: Sequence[float] | None = None,
    ) -> None:
        if isinstance(config, GemDataConfig):
            self.config = config
        else:
            self.config = GemDataConfig(
                csv_path=config,
                feature_columns=feature_columns or DEFAULT_FEATURE_COLUMNS,
                target_columns=target_columns or DEFAULT_TARGET_COLUMNS,
                dtype=dtype,
                transform=transform,
                normalize_features=normalize_features,
                feature_mean=feature_mean,
                feature_std=feature_std,
            )

        self.csv_path = Path(self.config.csv_path)
        self.feature_columns = tuple(self.config.feature_columns)
        self.target_columns = tuple(self.config.target_columns)
        self.dtype = self.config.dtype
        self.transform = self.config.transform
        self.normalize_features = self.config.normalize_features

        if not self.feature_columns:
            raise ValueError("feature_columns must not be empty")
        if not self.target_columns:
            raise ValueError("target_columns must not be empty")

        frame = pd.read_csv(self.csv_path)
        _require_columns(frame, self.feature_columns, "feature")
        _require_columns(frame, self.target_columns, "target")

        self.frame = frame
        raw_features = torch.as_tensor(
            frame.loc[:, self.feature_columns].to_numpy(dtype="float32", copy=True),
            dtype=self.dtype,
        )
        if self.normalize_features:
            if self.config.feature_mean is None:
                self.feature_mean = raw_features.mean(dim=0)
            else:
                self.feature_mean = torch.as_tensor(self.config.feature_mean, dtype=self.dtype)
            if self.config.feature_std is None:
                self.feature_std = raw_features.std(dim=0, unbiased=False).clamp_min(1e-6)
            else:
                self.feature_std = torch.as_tensor(self.config.feature_std, dtype=self.dtype).clamp_min(1e-6)
            self.features = (raw_features - self.feature_mean) / self.feature_std
        else:
            self.feature_mean = torch.zeros(raw_features.shape[1], dtype=self.dtype)
            self.feature_std = torch.ones(raw_features.shape[1], dtype=self.dtype)
            self.features = raw_features

        self.targets = torch.as_tensor(
            frame.loc[:, self.target_columns].to_numpy(dtype="float32", copy=True),
            dtype=self.dtype,
        )
        self.target_positive_rates = self.targets.mean(dim=0)

    def __len__(self) -> int:
        return self.features.shape[0]

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.features[index]
        targets = self.targets[index]
        if self.transform is not None:
            return self.transform(features, targets)
        return features, targets


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], kind: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing {kind} column(s): {', '.join(missing)}")
