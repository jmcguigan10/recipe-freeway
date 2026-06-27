from __future__ import annotations

import torch
from torch.utils.data import DataLoader, Dataset, random_split

try:
    from training._compat import ensure_project_paths
except ModuleNotFoundError:
    from ._compat import ensure_project_paths

ensure_project_paths()
from src.ml.python.io.args import TrainingConfig

try:
    from data.gem_data import GemClassifierDataset
    from training.seed import seed_worker_factory
except ModuleNotFoundError:
    from ..data.gem_data import GemClassifierDataset
    from .seed import seed_worker_factory


def make_dataloaders(config: TrainingConfig) -> tuple[DataLoader, DataLoader, GemClassifierDataset, Dataset]:
    train_dataset = GemClassifierDataset(
        config.train_csv,
        feature_columns=config.feature_columns,
        target_columns=config.target_columns,
        normalize_features=config.normalize_inputs,
    )
    generator = torch.Generator().manual_seed(config.seed)

    if config.val_csv:
        training_subset: Dataset = train_dataset
        validation_subset: Dataset = GemClassifierDataset(
            config.val_csv,
            feature_columns=config.feature_columns,
            target_columns=config.target_columns,
            normalize_features=config.normalize_inputs,
            feature_mean=train_dataset.feature_mean.tolist(),
            feature_std=train_dataset.feature_std.tolist(),
        )
    else:
        if not 0.0 < config.val_fraction < 1.0:
            raise ValueError(f"val_fraction must be in (0, 1): {config.val_fraction}")
        validation_size = max(1, int(round(len(train_dataset) * config.val_fraction)))
        if validation_size >= len(train_dataset):
            raise ValueError("Validation split would leave no training examples")
        training_size = len(train_dataset) - validation_size
        training_subset, validation_subset = random_split(
            train_dataset,
            [training_size, validation_size],
            generator=generator,
        )

    train_loader = DataLoader(
        training_subset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        generator=generator,
        worker_init_fn=seed_worker_factory(config.seed),
    )
    val_loader = DataLoader(
        validation_subset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        worker_init_fn=seed_worker_factory(config.seed),
    )
    return train_loader, val_loader, train_dataset, validation_subset
