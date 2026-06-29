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
    scheduler: str = "none"
    min_lr: float = 1e-5
    feature_columns: tuple[str, ...] = DEFAULT_FEATURE_COLUMNS
    target_columns: tuple[str, ...] = DEFAULT_TARGET_COLUMNS
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
    parser.add_argument("--epochs", type=int, default=config_default(config_defaults, "epochs", 20))
    parser.add_argument("--batch-size", type=int, default=config_default(config_defaults, "batch_size", 1024))
    parser.add_argument("--lr", type=float, default=config_default(config_defaults, "lr", 1e-3))
    parser.add_argument("--weight-decay", type=float, default=config_default(config_defaults, "weight_decay", 0.0))
    parser.add_argument("--hidden-dims", default=config_default(config_defaults, "hidden_dims", "64,64"))
    parser.add_argument("--dropout", type=float, default=config_default(config_defaults, "dropout", 0.1))
    parser.add_argument(
        "--batch-norm",
        action=argparse.BooleanOptionalAction,
        default=config_default(config_defaults, "batch_norm", False),
    )
    parser.add_argument("--seed", type=int, default=config_default(config_defaults, "seed", 1337))
    parser.add_argument("--num-workers", type=int, default=config_default(config_defaults, "num_workers", 0))
    parser.add_argument("--device", default=config_default(config_defaults, "device", None))
    parser.add_argument("--threshold", type=float, default=config_default(config_defaults, "threshold", 0.5))
    parser.add_argument("--scheduler", choices=("none", "cosine"), default=config_default(config_defaults, "scheduler", "none"))
    parser.add_argument("--min-lr", type=float, default=config_default(config_defaults, "min_lr", 1e-5))
    parser.add_argument("--feature-columns", default=config_default(config_defaults, "feature_columns", DEFAULT_FEATURE_COLUMNS))
    parser.add_argument("--target-columns", default=config_default(config_defaults, "target_columns", DEFAULT_TARGET_COLUMNS))
    parser.add_argument(
        "--normalize-inputs",
        action=argparse.BooleanOptionalAction,
        default=config_default(config_defaults, "normalize_inputs", True),
    )
    parser.add_argument(
        "--grouped-heads",
        action=argparse.BooleanOptionalAction,
        default=config_default(config_defaults, "grouped_heads", False),
    )
    parser.add_argument("--head-hidden-dim", type=int, default=config_default(config_defaults, "head_hidden_dim", 128))
    parser.add_argument("--loss", choices=("grouped-bce", "focal-bce"), default=config_default(config_defaults, "loss", "grouped-bce"))
    parser.add_argument("--focal-gamma", type=float, default=config_default(config_defaults, "focal_gamma", 2.0))
    parser.add_argument("--primary-loss-weight", type=float, default=config_default(config_defaults, "primary_loss_weight", 0.1))
    parser.add_argument("--secondary-loss-weight", type=float, default=config_default(config_defaults, "secondary_loss_weight", 1.0))
    parser.add_argument("--other-loss-weight", type=float, default=config_default(config_defaults, "other_loss_weight", 1.0))
    parser.add_argument(
        "--pos-weight",
        default=config_default(config_defaults, "pos_weight", "auto"),
        help="Use 'auto', 'none', or comma-separated per-label weights.",
    )
    args = parser.parse_args(argv)
    if not args.train_csv:
        parser.error("--train-csv is required unless train_csv is set in the ML YAML config")
    if args.focal_gamma < 0.0:
        parser.error("--focal-gamma must be non-negative")
    for name in ("primary_loss_weight", "secondary_loss_weight", "other_loss_weight"):
        if getattr(args, name) < 0.0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")

    return TrainingConfig(
        train_csv=args.train_csv,
        output_dir=args.output_dir,
        val_csv=args.val_csv,
        val_fraction=args.val_fraction,
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
        scheduler=args.scheduler,
        min_lr=args.min_lr,
        feature_columns=parse_columns(args.feature_columns, "--feature-columns"),
        target_columns=parse_columns(args.target_columns, "--target-columns"),
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


def parse_columns(raw: str | list[str] | tuple[str, ...], name: str) -> tuple[str, ...]:
    if isinstance(raw, str):
        values = tuple(part.strip() for part in raw.split(",") if part.strip())
    else:
        values = tuple(str(part).strip() for part in raw if str(part).strip())
    if not values:
        raise ValueError(f"{name} must contain at least one column")
    return values
