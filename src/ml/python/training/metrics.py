from __future__ import annotations

import torch


def classification_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    threshold: float = 0.5,
    label_names: tuple[str, ...] | None = None,
    eps: float = 1e-8,
) -> dict[str, float]:
    if label_names is not None and len(label_names) != targets.shape[1]:
        raise ValueError("label_names length must match target dimension")

    predictions = (torch.sigmoid(logits) >= threshold).to(dtype=torch.float32)
    targets = targets.to(dtype=torch.float32)

    true_positive = (predictions * targets).sum(dim=0)
    false_positive = (predictions * (1.0 - targets)).sum(dim=0)
    false_negative = ((1.0 - predictions) * targets).sum(dim=0)
    per_label_accuracy = (predictions == targets).to(dtype=torch.float32).mean(dim=0)
    precision = true_positive / (true_positive + false_positive + eps)
    recall = true_positive / (true_positive + false_negative + eps)
    f1 = 2.0 * precision * recall / (precision + recall + eps)

    metrics: dict[str, float] = {
        "macro_accuracy": float(per_label_accuracy.mean()),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "macro_f1": float(f1.mean()),
    }
    for index in range(targets.shape[1]):
        label = label_names[index] if label_names is not None else f"label_{index}"
        metrics[f"{label}_accuracy"] = float(per_label_accuracy[index])
        metrics[f"{label}_precision"] = float(precision[index])
        metrics[f"{label}_recall"] = float(recall[index])
        metrics[f"{label}_f1"] = float(f1[index])
    return metrics
