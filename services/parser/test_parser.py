from services.parser.parser import EmailParser


def test_parse_simple_email():
    raw = """From: test@example.com
Subject: Hello
Content-Type: text/plain; charset="UTF-8"

Test body with http://example.com/link"""
    r = EmailParser().parse(raw)
    assert r.subject == "Hello"
    assert "Test body" in r.text_body
    assert "http://example.com/link" in r.links


def test_decode_mime_header():
    raw = """From: test@example.com
Subject: =?UTF-8?B?0J/RgNC40LLQtdGC?=
Content-Type: text/plain; charset="UTF-8"

Hi"""
    assert EmailParser().parse(raw).subject == "Привет"


def test_decode_cp1251():
    raw = "From: a@b.com\nSubject: T\nContent-Type: text/plain; charset=windows-1251\n\nПривет мир".encode("cp1251")
    assert "Привет мир" in EmailParser().parse(raw).text_body


def test_empty_email():
    r = EmailParser().parse("")
    assert r.subject == ""
    assert r.text_body == ""
