from __future__ import annotations

import argparse
from dataclasses import dataclass


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
    primary_loss_weight: float = 0.1
    secondary_loss_weight: float = 1.0


def parse_args(argv: list[str] | None = None) -> TrainingConfig:
    parser = argparse.ArgumentParser(description="Train the GEM multi-label BCE classifier.")
    parser.add_argument("--train-csv", required=True)
    parser.add_argument("--output-dir", default="artifacts/gem_classifier")
    parser.add_argument("--val-csv")
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--hidden-dims", default="64,64")
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--batch-norm", action="store_true")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--scheduler", choices=("none", "cosine"), default="none")
    parser.add_argument("--min-lr", type=float, default=1e-5)
    parser.add_argument("--feature-columns", default=",".join(DEFAULT_FEATURE_COLUMNS))
    parser.add_argument("--target-columns", default=",".join(DEFAULT_TARGET_COLUMNS))
    parser.add_argument("--no-normalize-inputs", action="store_true")
    parser.add_argument("--grouped-heads", action="store_true")
    parser.add_argument("--head-hidden-dim", type=int, default=128)
    parser.add_argument("--primary-loss-weight", type=float, default=0.1)
    parser.add_argument("--secondary-loss-weight", type=float, default=1.0)
    parser.add_argument(
        "--pos-weight",
        default="auto",
        help="Use 'auto', 'none', or comma-separated per-label weights.",
    )
    args = parser.parse_args(argv)
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
        normalize_inputs=not args.no_normalize_inputs,
        grouped_heads=args.grouped_heads,
        head_hidden_dim=args.head_hidden_dim,
        primary_loss_weight=args.primary_loss_weight,
        secondary_loss_weight=args.secondary_loss_weight,
    )


def parse_hidden_dims(raw: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("--hidden-dims must contain at least one integer")
    if any(value <= 0 for value in values):
        raise ValueError(f"--hidden-dims values must be positive: {raw}")
    return values


def parse_columns(raw: str, name: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError(f"{name} must contain at least one column")
    return values
