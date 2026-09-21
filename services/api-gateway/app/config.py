import os

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TOPIC_RAW = "emails.raw"
TOPIC_VERDICTS = "verdicts.final"