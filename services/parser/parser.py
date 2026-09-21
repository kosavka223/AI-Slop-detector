"""Email parser for AI-Slop-detector. Multi-encoding, stdlib-only."""

from __future__ import annotations

import email
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from email import policy
from typing import Any

# Compile once at import time — regex compilation is expensive.
_HREF_RE = re.compile(r'href=["\']?(https?://[^"\'\s>]+)', re.I)
_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Fallback encodings ordered by real-world frequency in email traffic.
_ENCODINGS = ("utf-8", "windows-1251", "koi8-r", "iso-8859-1", "cp1252", "gb2312")


@dataclass(slots=True)
class ParsedEmail:
    """Typed, JSON-serializable representation of a parsed message."""

    subject: str = ""
    from_addr: str = ""
    to_addr: str = ""
    date: str = ""
    message_id: str = ""
    text_body: str = ""
    html_body: str = ""
    links: list[str] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    raw_headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EmailParser:
    """Stateless, thread-safe email parser."""

    __slots__ = ()  # Prevent accidental attribute assignment.

    def parse(self, raw: str | bytes) -> ParsedEmail:
        """Parse a raw RFC 5322 message. Never raises on malformed input."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")

        # policy.default handles RFC 2047 encoded words and defect recovery.
        msg = email.message_from_string(raw, policy=policy.default)
        result = ParsedEmail()

        # Headers — decode explicitly, policy.default doesn't cover all cases.
        result.subject = self._decode_header(msg.get("Subject", ""))
        result.from_addr = self._decode_header(msg.get("From", ""))
        result.to_addr = self._decode_header(msg.get("To", ""))
        result.date = msg.get("Date", "")
        result.message_id = msg.get("Message-ID", "")
        result.raw_headers = {k: str(v) for k, v in msg.items()}

        # Body — skip walk() for single-part messages (common case).
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition", "")).lower()

                if "attachment" in disp or part.get_filename():
                    self._add_attachment(part, result)
                elif ctype == "text/plain":
                    result.text_body += self._decode_payload(part)
                elif ctype == "text/html":
                    html = self._decode_payload(part)
                    result.html_body += html
                    result.links.extend(_HREF_RE.findall(html))
        else:
            ctype = msg.get_content_type()
            if ctype == "text/html":
                result.html_body = self._decode_payload(msg)
                result.links.extend(_HREF_RE.findall(result.html_body))
            else:
                result.text_body = self._decode_payload(msg)

        # Spammers often embed bare URLs in text/plain — catch those too.
        if result.text_body:
            result.links.extend(_URL_RE.findall(result.text_body))

        # dict.fromkeys dedupes in O(n) while preserving order.
        result.links = list(dict.fromkeys(result.links))

        return result

    @staticmethod
    def strip_html(html: str) -> str:
        """Reduce HTML to plain text (used by text-analyzer)."""
        if not html:
            return ""
        return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()

    def _decode_payload(self, part) -> str:
        """Decode a MIME part; tries declared charset, then fallbacks."""
        payload = part.get_payload(decode=True)
        if not payload:
            # Some parts expose a str via get_payload() when decode=True is None.
            raw = part.get_payload()
            return self._normalize(raw) if isinstance(raw, str) else ""

        charset = (part.get_content_charset() or "").lower()
        candidates = ([charset] if charset else []) + list(_ENCODINGS)

        for enc in candidates:
            try:
                # strict mode lets us detect a wrong charset and try the next.
                return self._normalize(payload.decode(enc, errors="strict"))
            except (UnicodeDecodeError, LookupError):
                continue

        # Last resort — lossy but never crashes the pipeline.
        return self._normalize(payload.decode("utf-8", errors="ignore"))

    @staticmethod
    def _decode_header(value: str) -> str:
        """Decode RFC 2047 encoded header (=?UTF-8?B?...?=)."""
        if not value:
            return ""
        try:
            from email.header import decode_header, make_header
            return str(make_header(decode_header(value)))
        except Exception:
            return str(value)

    @staticmethod
    def _normalize(text: str) -> str:
        """NFKC normalize + strip non-printable chars (critical for NLP)."""
        text = unicodedata.normalize("NFKC", text)
        return "".join(c for c in text if c.isprintable() or c in "\n\t\r")

    @staticmethod
    def _add_attachment(part, result: ParsedEmail) -> None:
        """Store attachment metadata only — payload is not retained."""
        payload = part.get_payload(decode=True) or b""
        result.attachments.append({
            "filename": part.get_filename() or "unnamed",
            "content_type": part.get_content_type(),
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })


if __name__ == "__main__":
    # Smoke test: verifies MIME headers + Cyrillic body decoding.
    import json

    sample = """From: =?UTF-8?B?0KHQv9Cw0LzQtdGA?= <spam@example.com>
Subject: =?UTF-8?B?0JLRi9C40LPRgNCw0Lk=?=
Content-Type: text/plain; charset="UTF-8"

Зайди на http://fake-bank.com"""

    print(json.dumps(EmailParser().parse(sample).to_dict(), indent=2, ensure_ascii=False))
