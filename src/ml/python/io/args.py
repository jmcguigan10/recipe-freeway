from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from typing import Any

from ..data.registry import DEFAULT_FEATURE_COLUMNS, DEFAULT_TARGET_COLUMNS
from .config import default_ml_config_path, load_training_config_file


@dataclass(frozen=True)
class TrainingConfig:
    train_csv: str
    output_dir: str
    val_csv: str | None = None
    val_fraction: float = 0.2
    calibration_fraction: float = 0.0
    split_strategy: str = "random"
    split_column: str = "event_index"
    epochs: int = 20
    batch_size: int = 1024
    lr: float = 1e-3
    weight_decay: float = 0.0
    hidden_dims: tuple[int, ...] = (64, 64)
    dropout: float = 0.1
    batch_norm: bool = False
    seed: int = 1337
    num_workers: int = 0
    device: str | None = None
    threshold: float = 0.5
    pos_weight: str = "auto"
    pos_weight_max: float | None = None
    scheduler: str = "none"
    min_lr: float = 1e-5
    checkpoint_metric: str = "val_loss"
    checkpoint_mode: str = "min"
    early_stopping_patience: int = 0
    early_stopping_min_delta: float = 0.0
    calibrate_pos_weight_logits: bool = True
    save_plots: bool = True
    plot_validation_predictions: bool = True
    save_full_validation_predictions: bool = False
    prediction_sample_size: int = 250000
    plot_bins: int = 20
    edge_band_mm: float = 5.0
    near_band_mm: float = 20.0
    feature_columns: tuple[str, ...] = DEFAULT_FEATURE_COLUMNS
    target_columns: tuple[str, ...] = DEFAULT_TARGET_COLUMNS
    geometry_config: str | None = None
    normalize_inputs: bool = True
    grouped_heads: bool = False
    head_hidden_dim: int = 128
    loss: str = "grouped-bce"
    focal_gamma: float = 2.0
    primary_loss_weight: float = 0.1
    secondary_loss_weight: float = 1.0
    other_loss_weight: float = 1.0


def parse_args(argv: list[str] | None = None) -> TrainingConfig:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", default=str(default_ml_config_path()))
    config_args, _ = config_parser.parse_known_args(argv)

    try:
        config_defaults = load_training_config_file(config_args.config)
    except (RuntimeError, ValueError) as exc:
        config_parser.error(str(exc))

    known_fields = {field.name for field in fields(TrainingConfig)}
    unknown_keys = sorted(set(config_defaults) - known_fields)
    if unknown_keys:
        config_parser.error(f"Unsupported ML config key(s): {', '.join(unknown_keys)}")

    parser = argparse.ArgumentParser(description="Train the GEM multi-label BCE classifier.")
    parser.add_argument("--config", default=config_args.config)
    parser.add_argument("--train-csv", default=config_default(config_defaults, "train_csv", None))
    parser.add_argument("--output-dir", default=config_default(config_defaults, "output_dir", "artifacts/gem_classifier"))
    parser.add_argument("--val-csv", default=config_default(config_defaults, "val_csv", None))
    parser.add_argument("--val-fraction", type=float, default=config_default(config_defaults, "val_fraction", 0.2))
    parser.add_argument("--calibration-fraction", type=float, default=config_default(config_defaults, "calibration_fraction", 0.0))
    parser.add_argument("--split-strategy", choices=("random", "event-hash"), default=config_default(config_defaults, "split_strategy", "random"))
    parser.add_argument("--split-column", default=config_default(config_defaults, "split_column", "event_index"))
    parser.add_argument("--epochs", type=int, default=config_default(config_defaults, "epochs", 20))
    parser.add_argument("--batch-size", type=int, default=config_default(config_defaults, "batch_size", 1024))
    parser.add_argument("--lr", type=float, default=config_default(config_defaults, "lr", 1e-3))
    parser.add_argument("--weight-decay", type=float, default=config_default(config_defaults, "weight_decay", 0.0))
    parser.add_argument("--hidden-dims", default=config_default(config_defaults, "hidden_dims", "64,64"))
    parser.add_argument("--dropout", type=float, default=config_default(config_defaults, "dropout", 0.1))
    parser.add_argument("--batch-norm", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "batch_norm", False))
    parser.add_argument("--seed", type=int, default=config_default(config_defaults, "seed", 1337))
    parser.add_argument("--num-workers", type=int, default=config_default(config_defaults, "num_workers", 0))
    parser.add_argument("--device", default=config_default(config_defaults, "device", None))
    parser.add_argument("--threshold", type=float, default=config_default(config_defaults, "threshold", 0.5))
    parser.add_argument("--scheduler", choices=("none", "cosine"), default=config_default(config_defaults, "scheduler", "none"))
    parser.add_argument("--min-lr", type=float, default=config_default(config_defaults, "min_lr", 1e-5))
    parser.add_argument("--checkpoint-metric", default=config_default(config_defaults, "checkpoint_metric", "val_loss"))
    parser.add_argument("--checkpoint-mode", choices=("min", "max"), default=config_default(config_defaults, "checkpoint_mode", "min"))
    parser.add_argument("--early-stopping-patience", type=int, default=config_default(config_defaults, "early_stopping_patience", 0))
    parser.add_argument("--early-stopping-min-delta", type=float, default=config_default(config_defaults, "early_stopping_min_delta", 0.0))
    parser.add_argument("--calibrate-pos-weight-logits", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "calibrate_pos_weight_logits", True))
    parser.add_argument("--save-plots", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "save_plots", True))
    parser.add_argument("--plot-validation-predictions", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "plot_validation_predictions", True))
    parser.add_argument("--save-full-validation-predictions", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "save_full_validation_predictions", False))
    parser.add_argument("--prediction-sample-size", type=int, default=config_default(config_defaults, "prediction_sample_size", 250000))
    parser.add_argument("--plot-bins", type=int, default=config_default(config_defaults, "plot_bins", 20))
    parser.add_argument("--edge-band-mm", type=float, default=config_default(config_defaults, "edge_band_mm", 5.0))
    parser.add_argument("--near-band-mm", type=float, default=config_default(config_defaults, "near_band_mm", 20.0))
    parser.add_argument("--feature-columns", default=config_default(config_defaults, "feature_columns", DEFAULT_FEATURE_COLUMNS))
    parser.add_argument("--target-columns", default=config_default(config_defaults, "target_columns", DEFAULT_TARGET_COLUMNS))
    parser.add_argument("--geometry-config", default=config_default(config_defaults, "geometry_config", None))
    parser.add_argument("--normalize-inputs", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "normalize_inputs", True))
    parser.add_argument("--grouped-heads", action=argparse.BooleanOptionalAction, default=config_default(config_defaults, "grouped_heads", False))
    parser.add_argument("--head-hidden-dim", type=int, default=config_default(config_defaults, "head_hidden_dim", 128))
    parser.add_argument("--loss", choices=("grouped-bce", "focal-bce"), default=config_default(config_defaults, "loss", "grouped-bce"))
    parser.add_argument("--focal-gamma", type=float, default=config_default(config_defaults, "focal_gamma", 2.0))
    parser.add_argument("--primary-loss-weight", type=float, default=config_default(config_defaults, "primary_loss_weight", 0.1))
    parser.add_argument("--secondary-loss-weight", type=float, default=config_default(config_defaults, "secondary_loss_weight", 1.0))
    parser.add_argument("--other-loss-weight", type=float, default=config_default(config_defaults, "other_loss_weight", 1.0))
    parser.add_argument("--pos-weight", default=config_default(config_defaults, "pos_weight", "auto"), help="Use 'auto', 'none', or comma-separated per-label weights.")
    parser.add_argument("--pos-weight-max", type=float, default=config_default(config_defaults, "pos_weight_max", None))
    args = parser.parse_args(argv)
    if not args.train_csv:
        parser.error("--train-csv is required unless train_csv is set in the ML YAML config")
    if not 0.0 < args.val_fraction < 1.0:
        parser.error("--val-fraction must be in (0, 1)")
    if not 0.0 <= args.calibration_fraction < 1.0:
        parser.error("--calibration-fraction must be in [0, 1)")
    if args.val_fraction + args.calibration_fraction >= 1.0:
        parser.error("--val-fraction + --calibration-fraction must be < 1")
    if args.focal_gamma < 0.0:
        parser.error("--focal-gamma must be non-negative")
    if args.early_stopping_patience < 0:
        parser.error("--early-stopping-patience must be non-negative")
    if args.early_stopping_min_delta < 0.0:
        parser.error("--early-stopping-min-delta must be non-negative")
    if args.plot_bins <= 0:
        parser.error("--plot-bins must be positive")
    if args.prediction_sample_size <= 0:
        parser.error("--prediction-sample-size must be positive")
    if args.edge_band_mm <= 0.0 or args.near_band_mm <= args.edge_band_mm:
        parser.error("Require 0 < --edge-band-mm < --near-band-mm")
    if args.pos_weight_max is not None and args.pos_weight_max <= 0.0:
        parser.error("--pos-weight-max must be positive when set")
    for name in ("primary_loss_weight", "secondary_loss_weight", "other_loss_weight"):
        if getattr(args, name) < 0.0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")

    return TrainingConfig(
        train_csv=args.train_csv,
        output_dir=args.output_dir,
        val_csv=args.val_csv,
        val_fraction=args.val_fraction,
        calibration_fraction=args.calibration_fraction,
        split_strategy=args.split_strategy,
        split_column=args.split_column,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        hidden_dims=parse_hidden_dims(args.hidden_dims),
        dropout=args.dropout,
        batch_norm=args.batch_norm,
        seed=args.seed,
        num_workers=args.num_workers,
        device=args.device,
        threshold=args.threshold,
        pos_weight=args.pos_weight,
        pos_weight_max=args.pos_weight_max,
        scheduler=args.scheduler,
        min_lr=args.min_lr,
        checkpoint_metric=args.checkpoint_metric,
        checkpoint_mode=args.checkpoint_mode,
        early_stopping_patience=args.early_stopping_patience,
        early_stopping_min_delta=args.early_stopping_min_delta,
        calibrate_pos_weight_logits=bool(args.calibrate_pos_weight_logits),
        save_plots=bool(args.save_plots),
        plot_validation_predictions=bool(args.plot_validation_predictions),
        save_full_validation_predictions=bool(args.save_full_validation_predictions),
        prediction_sample_size=args.prediction_sample_size,
        plot_bins=args.plot_bins,
        edge_band_mm=args.edge_band_mm,
        near_band_mm=args.near_band_mm,
        feature_columns=parse_columns(args.feature_columns, "--feature-columns"),
        target_columns=parse_columns(args.target_columns, "--target-columns"),
        geometry_config=parse_optional_text(args.geometry_config),
        normalize_inputs=bool(args.normalize_inputs),
        grouped_heads=args.grouped_heads,
        head_hidden_dim=args.head_hidden_dim,
        loss=args.loss,
        focal_gamma=args.focal_gamma,
        primary_loss_weight=args.primary_loss_weight,
        secondary_loss_weight=args.secondary_loss_weight,
        other_loss_weight=args.other_loss_weight,
    )


def config_default(config: dict[str, Any], name: str, default: Any) -> Any:
    value = config.get(name, default)
    return default if value is None else value


def parse_hidden_dims(raw: str | list[int] | tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(raw, str):
        values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    else:
        values = tuple(int(value) for value in raw)
    if not values:
        raise ValueError("--hidden-dims must contain at least one integer")
    if any(value <= 0 for value in values):
        raise ValueError(f"--hidden-dims values must be positive: {raw}")
    return values


def parse_optional_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if value.lower() in ("", "none", "false", "0", "off", "null"):
        return None
    return value


def parse_columns(raw: str | list[str] | tuple[str, ...], name: str) -> tuple[str, ...]:
    if isinstance(raw, str):
        values = tuple(part.strip() for part in raw.split(",") if part.strip())
    else:
        values = tuple(str(part).strip() for part in raw if str(part).strip())
    if not values:
        raise ValueError(f"{name} must contain at least one column")
    return values
