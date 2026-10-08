"""Evaluation metrics for imbalanced sentiment/risk classification.

Risk mentions are rare (about 5-8% of the data), so plain accuracy is misleading:
a model that always predicts "none" already scores above 90%. The project tracks
macro-F1, recall on the risk classes, and Cohen's kappa for agreement between
annotators.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _labels(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None):
    """Validate inputs and return the label order (given, or all seen labels sorted)."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if not y_true:
        raise ValueError("cannot evaluate an empty set")
    return list(labels) if labels is not None else sorted(set(y_true) | set(y_pred))


def confusion_matrix(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None
) -> tuple[np.ndarray, list[str]]:
    """Return the confusion matrix (rows = true labels, columns = predictions)."""
    labels = _labels(y_true, y_pred, labels)
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(y_true, y_pred, strict=True):
        if t in index and p in index:
            matrix[index[t], index[p]] += 1
    return matrix, labels


def per_class_scores(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None
) -> dict[str, dict[str, float]]:
    """Precision, recall, F1 and support for every class (0.0 when undefined).

    - precision: of all mentions predicted as this class, how many really are;
    - recall: of all mentions that really are this class, how many were found;
    - F1: harmonic mean of the two; support: number of true mentions of the class.
    """
    matrix, labels = confusion_matrix(y_true, y_pred, labels)
    scores = {}
    for i, label in enumerate(labels):
        tp = matrix[i, i]
        predicted = matrix[:, i].sum()
        actual = matrix[i, :].sum()
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores[label] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "support": int(actual),
        }
    return scores


def macro_f1(
    y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None
) -> float:
    """Unweighted mean of per-class F1, so rare classes count as much as frequent ones."""
    scores = per_class_scores(y_true, y_pred, labels)
    return float(np.mean([s["f1"] for s in scores.values()]))


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Agreement between two annotators, corrected for agreement by chance.

    ``kappa = (p_observed - p_expected) / (1 - p_expected)``, where ``p_observed`` is the
    share of items both annotators labelled the same and ``p_expected`` is the share
    they would agree on by pure chance given how often each uses each label.
    1.0 = perfect agreement, 0.0 = no better than chance. The project requires >= 0.80.
    """
    matrix, _ = confusion_matrix(a, b)
    n = matrix.sum()
    observed = np.trace(matrix) / n
    expected = float((matrix.sum(axis=0) * matrix.sum(axis=1)).sum()) / n**2
    if expected == 1.0:
        return 1.0
    return float((observed - expected) / (1 - expected))


def classification_report(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    positive_labels: Sequence[str] = (),
) -> dict:
    """Summary used by the CLI and the CI quality gate.

    ``positive_labels`` are the classes whose combined recall is reported separately
    (for example all risk categories except "none").
    """
    scores = per_class_scores(y_true, y_pred)
    report = {
        "n": len(y_true),
        "accuracy": float(np.mean([t == p for t, p in zip(y_true, y_pred, strict=True)])),
        "macro_f1": float(np.mean([s["f1"] for s in scores.values()])),
        "per_class": scores,
    }
    if positive_labels:
        positive = set(positive_labels)
        relevant = [(t, p) for t, p in zip(y_true, y_pred, strict=True) if t in positive]
        hits = sum(p in positive for _, p in relevant)
        report["positive_recall"] = hits / len(relevant) if relevant else 0.0
    return report
