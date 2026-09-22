"""Text preprocessing utilities shared by ML training and inference."""
from __future__ import annotations

import html as html_lib
import re
import unicodedata

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_WS_RE = re.compile(r"\s+")
_NON_PRINTABLE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class TextPreprocessor:
    """Stateless, thread-safe text cleaner.

    Normalizes raw email bodies into a canonical form suitable for both
    TF-IDF baselines and transformer models. PII (urls, emails) is masked
    so models learn style, not specific addresses.
    """

    __slots__ = ("language",)

    def __init__(self, language: str = "english") -> None:
        self.language = language

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        # 1) HTML entities & tags: &nbsp; -> space, <b> -> gone
        text = html_lib.unescape(text)
        text = _HTML_TAG_RE.sub(" ", text)
        # 2) Unicode normalization (full-width, ligatures, NBSP etc.)
        text = unicodedata.normalize("NFKC", text)
        # 3) Mask PII that adds noise instead of signal
        text = _URL_RE.sub(" url ", text)
        text = _EMAIL_RE.sub(" email ", text)
        # 4) Strip control characters
        text = _NON_PRINTABLE_RE.sub(" ", text)
        # 5) Collapse whitespace, lowercase
        text = _WS_RE.sub(" ", text).strip().lower()
        return text
