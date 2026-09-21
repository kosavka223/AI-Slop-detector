from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import classification_report, roc_auc_score

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ML.training.metrics import save_metrics


def main(model_dir: str, test_path: str) -> None:
    df = pd.read_parquet(test_path)
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    preds, probs = [], []
    with torch.no_grad():
        for text in df["text"]:
            enc = tok(text, truncation=True, max_length=256, return_tensors="pt").to(device)
            logits = model(**enc).logits
            p = torch.softmax(logits, dim=-1)[0].cpu()
            probs.append(p[1].item())
            preds.append(int(p[1] > 0.5))

    y = df["label"].tolist()
    print(classification_report(y, preds, zero_division=0))
    save_metrics(
        {"roc_auc": roc_auc_score(y, probs)},
        Path(model_dir) / "eval_metrics.json",
    )


if __name__ == "__main__":
    main("ML/models/text_detector", "ML/data/processed/baseline_test.parquet")
