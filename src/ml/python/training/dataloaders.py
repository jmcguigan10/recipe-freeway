from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, Subset, random_split

try:
    from training._compat import ensure_project_paths
except ModuleNotFoundError:
    from ._compat import ensure_project_paths

ensure_project_paths()
from src.ml.python.io.args import TrainingConfig

try:
    from ..data import GemClassifierDataset, build_gem_data_config
except ImportError:
    from data import GemClassifierDataset, build_gem_data_config

from .seed import seed_worker_factory


def make_dataloaders(config: TrainingConfig) -> tuple[DataLoader, DataLoader, DataLoader, GemClassifierDataset, Dataset, Dataset]:
    train_dataset = GemClassifierDataset(
        build_gem_data_config(
            config.train_csv,
            feature_columns=config.feature_columns,
            target_columns=config.target_columns,
            geometry_config=config.geometry_config,
            edge_band_mm=config.edge_band_mm,
            near_band_mm=config.near_band_mm,
            normalize_features=config.normalize_inputs,
        )
    )
    generator = torch.Generator().manual_seed(config.seed)

    if config.val_csv:
        training_subset: Dataset = train_dataset
        validation_subset: Dataset = GemClassifierDataset(
            build_gem_data_config(
                config.val_csv,
                feature_columns=config.feature_columns,
                target_columns=config.target_columns,
                geometry_config=config.geometry_config,
                edge_band_mm=config.edge_band_mm,
                near_band_mm=config.near_band_mm,
                normalize_features=config.normalize_inputs,
                feature_mean=train_dataset.feature_mean.tolist(),
                feature_std=train_dataset.feature_std.tolist(),
            )
        )
        calibration_subset: Dataset = validation_subset
    else:
        training_subset, validation_subset, calibration_subset = split_dataset(train_dataset, config, generator)

    train_loader = make_loader(training_subset, config, shuffle=True, generator=generator)
    val_loader = make_loader(validation_subset, config, shuffle=False, generator=generator)
    calibration_loader = make_loader(calibration_subset, config, shuffle=False, generator=generator)
    return train_loader, val_loader, calibration_loader, train_dataset, validation_subset, calibration_subset


def make_loader(dataset: Dataset, config: TrainingConfig, *, shuffle: bool, generator: torch.Generator) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=config.batch_size,
        shuffle=shuffle,
        num_workers=config.num_workers,
        generator=generator,
        worker_init_fn=seed_worker_factory(config.seed),
    )


def split_dataset(
    dataset: GemClassifierDataset,
    config: TrainingConfig,
    generator: torch.Generator,
) -> tuple[Dataset, Dataset, Dataset]:
    if config.split_strategy == "event-hash":
        return event_hash_split(dataset, config)
    return random_fraction_split(dataset, config, generator)


def random_fraction_split(
    dataset: GemClassifierDataset, config: TrainingConfig, generator: torch.Generator) -> tuple[Dataset, Dataset, Dataset]:
    validation_size = max(1, int(round(len(dataset) * config.val_fraction)))
    calibration_size = int(round(len(dataset) * config.calibration_fraction))
    if config.calibration_fraction > 0.0:
        calibration_size = max(1, calibration_size)
    training_size = len(dataset) - validation_size - calibration_size
    if training_size <= 0:
        raise ValueError("Validation/calibration split would leave no training examples")
    if calibration_size == 0:
        training_subset, validation_subset = random_split(dataset, [training_size, validation_size], generator=generator)
        calibration_subset = validation_subset
        return training_subset, validation_subset, calibration_subset
    training_subset, validation_subset, calibration_subset = random_split(
        dataset,
        [training_size, validation_size, calibration_size],
        generator=generator,
    )
    return training_subset, validation_subset, calibration_subset


def event_hash_split(dataset: GemClassifierDataset, config: TrainingConfig) -> tuple[Dataset, Dataset, Dataset]:
    if config.split_column not in dataset.frame.columns:
        raise ValueError(f"split column not found for event-hash split: {config.split_column}")
    values = dataset.frame[config.split_column].to_numpy(dtype=np.uint64, copy=False)
    hashed = values * np.uint64(11400714819323198485) + np.uint64(config.seed)
    bucket = (hashed % np.uint64(1000000)).astype(np.float64) / 1000000.0
    train_fraction = 1.0 - config.val_fraction - config.calibration_fraction
    validation_end = train_fraction + config.val_fraction
    train_indices = np.flatnonzero(bucket < train_fraction).astype(np.int64).tolist()
    validation_indices = np.flatnonzero((bucket >= train_fraction) & (bucket < validation_end)).astype(np.int64).tolist()
    if config.calibration_fraction > 0.0:
        calibration_indices = np.flatnonzero(bucket >= validation_end).astype(np.int64).tolist()
    else:
        calibration_indices = validation_indices
    if not train_indices or not validation_indices or not calibration_indices:
        raise ValueError("event-hash split produced an empty train/validation/calibration subset")
    return Subset(dataset, train_indices), Subset(dataset, validation_indices), Subset(dataset, calibration_indices)
