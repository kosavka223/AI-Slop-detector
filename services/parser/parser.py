"""Email parser for AI-Slop-detector. Multi-encoding, stdlib-only."""

from __future__ import annotations

import base64
import email
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from email import policy
from html.parser import HTMLParser
from typing import Any

# Compile once at import time — regex compilation is expensive.
_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Fallback encodings ordered by real-world frequency in email traffic.
_ENCODINGS = ("utf-8", "windows-1251", "koi8-r", "iso-8859-1", "cp1252", "gb2312")

# Kafka broker default message.max.bytes is ~1 MB. Capping image payloads keeps
# a single emails.parsed message (text + html + base64 images) under that limit:
# _MAX_IMAGES * ceil(_MAX_IMAGE_BYTES * 4/3) stays well below 1 MB.
_MAX_IMAGES = 3
_MAX_IMAGE_BYTES = 200_000


class _LinkExtractor(HTMLParser):
    """Collects (href, anchor_text) pairs from <a> tags, tolerating broken markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._chunks: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._depth += 1
            if self._depth == 1:  # outermost <a> wins on accidental nesting
                self._href = dict((k.lower(), v or "") for k, v in attrs).get("href", "")
                self._chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._depth:
            self._depth -= 1
            if self._depth == 0 and self._href is not None:
                text = _WS_RE.sub(" ", "".join(self._chunks)).strip()
                self.links.append((self._href, text))
                self._href = None

    def close(self) -> None:
        super().close()
        # Unclosed <a> at EOF (broken markup) — flush the pending link.
        if self._href is not None:
            text = _WS_RE.sub(" ", "".join(self._chunks)).strip()
            self.links.append((self._href, text))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._depth and self._href is not None:
            self._chunks.append(data)


@dataclass(slots=True)
class ParsedEmail:
    """Typed, JSON-serializable representation of a parsed message.

    Mirrors the emails.parsed contract in shared/models/analysis.py.
    """

    subject: str = ""
    from_addr: str = ""
    to_addr: str = ""
    date: str = ""
    message_id: str = ""
    text_body: str = ""
    html_body: str = ""
    # {"href": str, "anchor_text": str, "source": "html" | "text"}
    links: list[dict] = field(default_factory=list)
    # image/* payloads for image-analyzer (Kafka-size capped, see _MAX_IMAGE_BYTES)
    images: list[dict] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    raw_headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def link_urls(self) -> list[str]:
        """Ordered unique hrefs (convenience for callers that only need URLs)."""
        return list(dict.fromkeys(l["href"] for l in self.links))


class EmailParser:
    """Stateless, thread-safe email parser."""

    __slots__ = ()  # Prevent accidental attribute assignment.

    def parse(self, raw: str | bytes) -> ParsedEmail:
        """Parse a raw RFC 5322 message. Never raises on malformed input."""
        # bytes go through message_from_bytes: pre-decoding to str with
        # errors="ignore" would destroy non-UTF-8 bodies (cp1251 etc.) before
        # the charset fallback in _decode_payload ever sees the raw bytes.
        if isinstance(raw, bytes):
            msg = email.message_from_bytes(raw, policy=policy.default)
        else:
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

                if ctype.startswith("image/"):
                    if not self._add_image(part, result):
                        # payload dropped (size cap) — keep at least the metadata
                        self._add_attachment(part, result)
                    elif "attachment" in disp or part.get_filename():
                        self._add_attachment(part, result)
                elif "attachment" in disp or part.get_filename():
                    self._add_attachment(part, result)
                elif ctype == "text/plain":
                    result.text_body += self._decode_payload(part)
                elif ctype == "text/html":
                    html = self._decode_payload(part)
                    result.html_body += html
                    result.links.extend(self._extract_html_links(html))
        else:
            ctype = msg.get_content_type()
            if ctype == "text/html":
                result.html_body = self._decode_payload(msg)
                result.links.extend(self._extract_html_links(result.html_body))
            else:
                result.text_body = self._decode_payload(msg)

        # Spammers often embed bare URLs in text/plain — catch those too.
        if result.text_body:
            result.links.extend(
                {"href": url, "anchor_text": "", "source": "text"}
                for url in _URL_RE.findall(result.text_body)
            )

        # Dedupe exact (href, anchor_text, source) triples, preserve first-seen order.
        result.links = list(
            {(l["href"], l["anchor_text"], l["source"]): l for l in result.links}.values()
        )

        return result

    @staticmethod
    def strip_html(html: str) -> str:
        """Reduce HTML to plain text (used by text-analyzer)."""
        if not html:
            return ""
        return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()

    @staticmethod
    def _extract_html_links(html: str) -> list[dict]:
        """<a href> pairs with anchor text — anchor/href mismatch is a phishing signal."""
        extractor = _LinkExtractor()
        try:
            extractor.feed(html)
            extractor.close()
        except Exception:
            pass  # never crash on broken markup
        return [
            {"href": href, "anchor_text": text, "source": "html"}
            for href, text in extractor.links
            if href
        ]

    def _decode_payload(self, part) -> str:
        """Decode a MIME part; tries declared charset, then fallbacks."""
        cte = (part.get("Content-Transfer-Encoding") or "").lower()
        raw = part.get_payload()
        # str payload without transport encoding: get_payload(decode=True)
        # pushes non-ASCII through raw-unicode-escape and turns it into
        # literal \uXXXX garbage — use the str directly when it is clean.
        if isinstance(raw, str) and cte not in ("base64", "quoted-printable"):
            try:
                raw.encode("utf-8")  # raises on surrogate escapes — bytes path below
                return self._normalize(raw)
            except UnicodeEncodeError:
                pass

        payload = part.get_payload(decode=True)
        if not payload:
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
    def _add_image(part, result: ParsedEmail) -> bool:
        """Keep image payloads (inline CID or attached) for image-analyzer.

        Returns False when the payload was dropped (size cap / part limit).
        """
        payload = part.get_payload(decode=True)
        if not payload or len(payload) > _MAX_IMAGE_BYTES or len(result.images) >= _MAX_IMAGES:
            return False
        result.images.append({
            "content_type": part.get_content_type(),
            "filename": part.get_filename() or "",
            "content_id": (part.get("Content-ID") or "").strip().strip("<>"),
            "size": len(payload),
            "data_base64": base64.b64encode(payload).decode("ascii"),
        })
        return True

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
    # Smoke test: MIME headers, Cyrillic body, anchor links, inline image.
    import json

    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode()
    sample = f"""From: =?UTF-8?B?0KHQv9Cw0LzQtdGA?= <spam@example.com>
Subject: =?UTF-8?B?0JLRi9C40LPRgNCw0Lk=?=
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="MIX"

--MIX
Content-Type: multipart/alternative; boundary="ALT"

--ALT
Content-Type: text/plain; charset="UTF-8"

Зайди на http://fake-bank.com
--ALT
Content-Type: text/html; charset="UTF-8"

<p><a href="http://fake-bank.com/login">Сбербанк Онлайн</a></p>
<img src="cid:logo1">
--ALT--

--MIX
Content-Type: image/png
Content-Transfer-Encoding: base64
Content-ID: <logo1>

{png}
--MIX--"""

    parsed = EmailParser().parse(sample)
    print(json.dumps(parsed.to_dict(), indent=2, ensure_ascii=False)[:1500])
