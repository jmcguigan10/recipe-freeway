from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from training._compat import ensure_project_paths
except ModuleNotFoundError:
    from ._compat import ensure_project_paths

ensure_project_paths()

from src.ml.python.io.args import TrainingConfig, parse_args
from src.ml.python.io.saving import save_checkpoint

try:
    from training.dataloaders import make_dataloaders
    from training.engine import fit, train_one_epoch
    from training.evaluate import evaluate
    from training.metrics import classification_metrics
    from training.seed import set_reproducible_seed
except ModuleNotFoundError:
    from .dataloaders import make_dataloaders
    from .engine import fit, train_one_epoch
    from .evaluate import evaluate
    from .metrics import classification_metrics
    from .seed import set_reproducible_seed


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    try:
        result = fit(config)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Training complete: best_epoch={result['best_epoch']} "
        f"best_val_loss={result['best_val_loss']:.6f} "
        f"{result['best_metric_name']}={result['best_metric_value']:.6f} "
        f"output_dir={result['output_dir']}"
    )
    return 0


__all__ = [
    "TrainingConfig",
    "classification_metrics",
    "evaluate",
    "fit",
    "main",
    "make_dataloaders",
    "parse_args",
    "save_checkpoint",
    "set_reproducible_seed",
    "train_one_epoch",
]


if __name__ == "__main__":
    raise SystemExit(main())
