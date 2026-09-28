"""Тесты контракта emails.parsed: build_parsed_message без Kafka."""
import base64

from services.parser.app.main import _decode_raw, build_parsed_message

RAW_MIME = """From: Sender <s@example.com>
To: victim@bank.com
Subject: =?UTF-8?B?0J/RgNC40LLQtdGC?=

Visit http://example.com"""


def test_gateway_text_message():
    msg = build_parsed_message({"task_id": "t1", "text": "Hello world, visit http://example.com"})
    assert msg["task_id"] == "t1"
    assert msg["email_id"] == "t1"  # email_id defaults to task_id
    assert "Hello world" in msg["text_part"]
    assert msg["links"][0]["href"] == "http://example.com"
    assert msg["links"][0]["source"] == "text"
    assert msg["images"] == []
    assert msg["html_part"] is None


def test_raw_email_base64_full_contract():
    encoded = base64.b64encode(RAW_MIME.encode()).decode()
    msg = build_parsed_message({"task_id": "t2", "email_id": "e2", "raw_email": encoded})
    assert msg["email_id"] == "e2"
    assert msg["subject"] == "Привет"
    assert msg["from_addr"] == "Sender <s@example.com>"
    assert msg["text_part"].strip() == "Visit http://example.com"
    # policy.default декодирует заголовки — raw_headers содержат уже раскрытые значения
    assert msg["raw_headers"]["Subject"] == "Привет"
    assert msg["parsed_at"]


def test_raw_email_as_plain_text_fallback():
    msg = build_parsed_message({"task_id": "t3", "raw_email": RAW_MIME})
    assert msg["subject"] == "Привет"  # не base64 — распарсен как текст письма


def test_no_task_id_returns_none():
    assert build_parsed_message({"text": "hi"}) is None
    assert build_parsed_message({}) is None


def test_empty_text_still_produces_contract_message():
    msg = build_parsed_message({"task_id": "t4", "text": ""})
    assert msg["task_id"] == "t4"
    assert msg["text_part"] is None  # анализаторы получат сообщение и вернут ~0


def test_decode_raw_variants():
    assert _decode_raw(base64.b64encode(b"hello").decode()) == "hello"
    assert _decode_raw(b"raw bytes") == "raw bytes"
    assert _decode_raw("not base64!!") == "not base64!!"
