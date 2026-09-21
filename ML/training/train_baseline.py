"""Baseline AI-slop classifier. Reads .eml (raw/) + synthetic CSV."""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import mlflow
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split

sys.path.append(str(Path(__file__).resolve().parents[2]))
from services.parser.parser import EmailParser
from ML.preprocess import TextPreprocessor

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
SYNTH = Path(__file__).resolve().parents[1] / "data" / "processed" / "synthetic_full.csv"
PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = Path(__file__).resolve().parents[1] / "models"
for d in (PROCESSED, MODELS):
    d.mkdir(exist_ok=True)

# --- target column: 1 = AI-generated, 0 = human ---
TARGET = "ai_assisted"

# --- hyperparameters ---
SEED = 42
TEST_SIZE = 0.2
MAX_FEATURES = 20000
NGRAM_RANGE = (1, 2)
MIN_DF = 2
C = 1.0
MAX_ITER = 1000


def load_eml() -> pd.DataFrame:
    """Walk raw/, parse every .eml, infer label from folder name."""
    parser = EmailParser()
    rows = []
    for path in RAW.rglob("*"):
        if not path.is_file():
            continue
        parent = path.parent.name.lower()
        if "spam" in parent:
            label, ai = 1, 0
        elif "ham" in parent:
            label, ai = 0, 0
        else:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            parsed = parser.parse(raw)
        except Exception:
            continue
        text = parsed.text_body or parser.strip_html(parsed.html_body)
        if text.strip():
            rows.append({"text": text, "label": label, "source": "human", "ai_assisted": ai})
    return pd.DataFrame(rows)


def load_synth() -> pd.DataFrame:
    """Load the generated synthetic dataset."""
    if not SYNTH.exists():
        print(f"[warn] {SYNTH} not found — run generate_synthetic.py first")
        return pd.DataFrame()
    return pd.read_csv(SYNTH)


def train(df: pd.DataFrame):
    pre = TextPreprocessor(language="english")
    df["clean"] = df["text"].astype(str).apply(pre.clean_text)
    df = df[df["clean"].str.len() > 0].reset_index(drop=True)

    df.to_parquet(PROCESSED / "combined_clean.parquet", index=False)

    if TARGET not in df.columns:
        sys.exit(f"Target column '{TARGET}' not found in data.")
    if df[TARGET].nunique() < 2:
        sys.exit(f"Target '{TARGET}' has only one class — need both AI and human samples.")

    X_tr, X_te, y_tr, y_te = train_test_split(
        df["clean"], df[TARGET],
        test_size=TEST_SIZE, random_state=SEED, stratify=df[TARGET],
    )

    vec = TfidfVectorizer(
        max_features=MAX_FEATURES,
        ngram_range=NGRAM_RANGE,
        min_df=MIN_DF,
    )
    X_tr_v = vec.fit_transform(X_tr)
    X_te_v = vec.transform(X_te)

    model = LogisticRegression(
        C=C, max_iter=MAX_ITER, class_weight="balanced",
    )

    mlflow.set_experiment("ai-slop-baseline")
    with mlflow.start_run():
        mlflow.log_params({
            "target": TARGET,
            "max_features": MAX_FEATURES,
            "ngram_range": str(NGRAM_RANGE),
            "min_df": MIN_DF,
            "C": C,
            "seed": SEED,
            "test_size": TEST_SIZE,
        })

        model.fit(X_tr_v, y_tr)

        y_pred = model.predict(X_te_v)
        y_proba = model.predict_proba(X_te_v)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_te, y_pred)),
            "roc_auc": float(roc_auc_score(y_te, y_proba)),
        }
        mlflow.log_metrics(metrics)

        report = classification_report(y_te, y_pred, zero_division=0)
        print("\n=== Baseline report ===")
        print(report)
        mlflow.log_text(report, "classification_report.txt")

    # save metrics json
    with open(MODELS / "baseline_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # save test split for later re-evaluation
    pd.DataFrame({"text": X_te, "label": y_te}).to_parquet(
        PROCESSED / "baseline_test.parquet", index=False
    )

    return model, vec


def save(model, vec) -> None:
    with open(MODELS / "baseline_model.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODELS / "baseline_vectorizer.pkl", "wb") as f:
        pickle.dump(vec, f)
    print(f"\nSaved → {MODELS}")


if __name__ == "__main__":
    parts = [load_eml(), load_synth()]
    df = pd.concat([p for p in parts if not p.empty], ignore_index=True)

    if df.empty:
        sys.exit("No data. Check ML/data/raw/ and ML/data/processed/.")

    print(f"Total: {len(df)} emails | spam={df['label'].sum()} | ham={(df['label'] == 0).sum()}")
    print(f"         ai_assisted={df['ai_assisted'].sum()} | human={(df['ai_assisted'] == 0).sum()}")

    model, vec = train(df)
    save(model, vec)
