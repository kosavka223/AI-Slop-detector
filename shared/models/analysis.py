from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AnalyzerName(str, Enum):
    TEXT = "text"
    HTML = "html"
    IMAGES = "images"
    LINKS_META = "links-meta"


class EmailImage(BaseModel):
    """Картинка из письма (inline CID или вложение) для image-analyzer."""
    content_type: str = "application/octet-stream"
    filename: Optional[str] = None
    content_id: Optional[str] = None
    size: int = 0
    data_base64: str


class EmailLink(BaseModel):
    """Ссылка из письма: anchor_text нужен link-analyzer'у для детекта подмены."""
    href: str
    anchor_text: str = ""
    source: str = "html"  # "html" | "text"


class ParsedEmail(BaseModel):
    """Parser -> анализаторы (топик emails.parsed).

    Контракт Data/Network Engineer. Валидируется парсером перед публикацией.
    """
    task_id: str
    email_id: str
    subject: str = ""
    from_addr: str = ""
    to_addr: str = ""
    date: str = ""
    message_id: str = ""
    text_part: Optional[str] = None
    html_part: Optional[str] = None
    images: list[EmailImage] = Field(default_factory=list)
    links: list[EmailLink] = Field(default_factory=list)
    attachments: list[dict] = Field(default_factory=list)
    raw_headers: dict = Field(default_factory=dict)
    parsed_at: Optional[datetime] = None


class AnalyzerResult(BaseModel):
    analyzer: AnalyzerName
    email_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str
    details: dict = Field(default_factory=dict)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CampaignContext(BaseModel):
    cluster_id: Optional[str] = None
    variations_detected: int = 0
    pattern: Optional[str] = None


class AggregatedResult(BaseModel):
    """Aggregator -> Decision Engine."""
    email_id: str
    ai_assistance_score: float = Field(..., ge=0.0, le=1.0)
    signals: dict[str, AnalyzerResult]
    campaign: CampaignContext = Field(default_factory=CampaignContext)
    aggregated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FinalVerdict(BaseModel):
    """Decision Engine -> SIEM/SOAR. Контракт из README."""
    email_id: str
    overall_risk: str
    ai_assistance_score: float = Field(..., ge=0.0, le=1.0)
    classification: str
    signals: dict[str, AnalyzerResult]
    campaign_context: CampaignContext
    rules_applied: list[str] = Field(default_factory=list)
    model_version: str = "0.1.0"
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))