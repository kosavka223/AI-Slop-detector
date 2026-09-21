from uuid import uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class KafkaMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    email_id: str
    schema_version: str = "1.0"
    producer: str
    payload: dict
    produced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))