from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix, roc_auc_score, classification_report,
)


def compute_metrics(eval_pred) -> dict:
    logits, labels = eval_pred
    probs = _softmax(logits)
    preds = np.argmax(logits, axis=-1)
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", zero_division=0)
    return {
        "accuracy": accuracy_score(labels, preds),
        "precision": p,
        "recall": r,
        "f1": f1,
        "roc_auc": roc_auc_score(labels, probs[:, 1]),
    }


def _softmax(x):
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=-1, keepdims=True)


def save_metrics(metrics: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


def full_report(y_true, y_pred) -> str:
    return classification_report(y_true, y_pred, zero_division=0)
