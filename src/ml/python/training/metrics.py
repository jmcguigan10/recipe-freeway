from __future__ import annotations

import torch
import torch.nn.functional as F


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

    probabilities = torch.sigmoid(logits).to(dtype=torch.float32)
    predictions = (probabilities >= threshold).to(dtype=torch.float32)
    targets = targets.to(dtype=torch.float32)

    true_positive = (predictions * targets).sum(dim=0)
    false_positive = (predictions * (1.0 - targets)).sum(dim=0)
    false_negative = ((1.0 - predictions) * targets).sum(dim=0)
    per_label_accuracy = (predictions == targets).to(dtype=torch.float32).mean(dim=0)
    precision = true_positive / (true_positive + false_positive + eps)
    recall = true_positive / (true_positive + false_negative + eps)
    f1 = 2.0 * precision * recall / (precision + recall + eps)
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none").mean(dim=0)
    target_rate = targets.mean(dim=0)
    predicted_rate = predictions.mean(dim=0)
    probability_mean = probabilities.mean(dim=0)

    auroc_values = []
    average_precision_values = []
    for index in range(targets.shape[1]):
        auroc_values.append(binary_auroc(probabilities[:, index], targets[:, index]))
        average_precision_values.append(binary_average_precision(probabilities[:, index], targets[:, index]))

    auroc = torch.as_tensor(auroc_values, dtype=torch.float32)
    average_precision = torch.as_tensor(average_precision_values, dtype=torch.float32)

    metrics: dict[str, float] = {
        "macro_accuracy": float(per_label_accuracy.mean()),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "macro_f1": float(f1.mean()),
        "macro_bce": float(bce.mean()),
        "macro_auroc": float(torch.nanmean(auroc)),
        "macro_average_precision": float(torch.nanmean(average_precision)),
    }
    for index in range(targets.shape[1]):
        label = label_names[index] if label_names is not None else f"label_{index}"
        metrics[f"{label}_accuracy"] = float(per_label_accuracy[index])
        metrics[f"{label}_precision"] = float(precision[index])
        metrics[f"{label}_recall"] = float(recall[index])
        metrics[f"{label}_f1"] = float(f1[index])
        metrics[f"{label}_bce"] = float(bce[index])
        metrics[f"{label}_positive_rate"] = float(target_rate[index])
        metrics[f"{label}_predicted_positive_rate"] = float(predicted_rate[index])
        metrics[f"{label}_probability_mean"] = float(probability_mean[index])
        metrics[f"{label}_auroc"] = float(auroc[index])
        metrics[f"{label}_average_precision"] = float(average_precision[index])
    return metrics


def binary_auroc(scores: torch.Tensor, targets: torch.Tensor) -> float:
    targets = targets.to(dtype=torch.float32)
    positives = targets.sum()
    negatives = targets.numel() - positives
    if positives <= 0 or negatives <= 0:
        return float("nan")

    order = torch.argsort(scores, stable=True)
    sorted_targets = targets[order]
    ranks = torch.arange(1, targets.numel() + 1, dtype=torch.float32)
    positive_rank_sum = ranks[sorted_targets > 0.5].sum()
    auc = (positive_rank_sum - positives * (positives + 1.0) / 2.0) / (positives * negatives)
    return float(auc)


def binary_average_precision(scores: torch.Tensor, targets: torch.Tensor) -> float:
    targets = targets.to(dtype=torch.float32)
    positives = targets.sum()
    if positives <= 0:
        return float("nan")

    order = torch.argsort(scores, descending=True, stable=True)
    sorted_targets = targets[order]
    true_positive_cumsum = torch.cumsum(sorted_targets, dim=0)
    ranks = torch.arange(1, targets.numel() + 1, dtype=torch.float32)
    precision_at_rank = true_positive_cumsum / ranks
    average_precision = (precision_at_rank * sorted_targets).sum() / positives
    return float(average_precision)
