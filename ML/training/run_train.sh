#!/usr/bin/env bash
set -e
export PYTHONPATH=.

echo "[1/3] Baseline (TF-IDF + LogReg)"
python -m ML.training.train_baseline

echo "[2/3] Transformer (DistilBERT)"
python -m ML.training.train_text_model

echo "[3/3] Evaluate transformer"
python -m ML.training.evaluate
