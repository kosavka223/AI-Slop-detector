from dataclasses import dataclass, field

@dataclass
class TextTrainConfig:
    model_name: str = "distilbert-base-uncased"
    max_length: int = 256
    batch_size: int = 16
    learning_rate: float = 2e-5
    epochs: int = 3
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    val_size: float = 0.1
    test_size: float = 0.1
    seed: int = 42
    output_dir: str = "ML/models/text_detector"
    target_column: str = "ai_assisted"  # <- ключевое: учим на AI, не на spam

@dataclass
class BaselineConfig:
    max_features: int = 20000
    ngram_range: tuple = (1, 2)
    min_df: int = 2
    C: float = 1.0
    max_iter: int = 1000
    target_column: str = "ai_assisted"
    seed: int = 42
    model_path: str = "ML/models/baseline_model.pkl"
    vec_path: str = "ML/models/baseline_vectorizer.pkl"
    metrics_path: str = "ML/models/baseline_metrics.json"
