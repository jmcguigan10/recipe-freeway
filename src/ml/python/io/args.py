from __future__ import annotations

import argparse
from dataclasses import dataclass


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
    seed: int = 1337
    num_workers: int = 0
    device: str | None = None
    threshold: float = 0.5
    pos_weight: str = "auto"


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
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device")
    parser.add_argument("--threshold", type=float, default=0.5)
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
        seed=args.seed,
        num_workers=args.num_workers,
        device=args.device,
        threshold=args.threshold,
        pos_weight=args.pos_weight,
    )


def parse_hidden_dims(raw: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values:
        raise ValueError("--hidden-dims must contain at least one integer")
    if any(value <= 0 for value in values):
        raise ValueError(f"--hidden-dims values must be positive: {raw}")
    return values
