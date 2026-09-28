import base64

from services.parser.parser import EmailParser, _MAX_IMAGE_BYTES


def _png_bytes() -> bytes:
    # Минимальная заглушка: парсер не валидирует содержимое картинки.
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_parse_simple_email():
    raw = """From: test@example.com
Subject: Hello
Content-Type: text/plain; charset="UTF-8"

Test body with http://example.com/link"""
    r = EmailParser().parse(raw)
    assert r.subject == "Hello"
    assert "Test body" in r.text_body
    assert {"href": "http://example.com/link", "anchor_text": "", "source": "text"} in r.links


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


def test_html_links_carry_anchor_text():
    raw = """From: phish@example.com
Subject: T
MIME-Version: 1.0
Content-Type: text/html; charset="UTF-8"

<p>Ваш банк: <a href="http://evil.example.com/login">Сбербанк Онлайн</a></p>"""
    r = EmailParser().parse(raw)
    assert r.links == [{
        "href": "http://evil.example.com/login",
        "anchor_text": "Сбербанк Онлайн",
        "source": "html",
    }]


def test_links_dedup_preserve_order():
    raw = """From: a@b.com
Subject: T
MIME-Version: 1.0
Content-Type: text/html; charset="UTF-8"

<a href="http://x.com">A</a><a href="http://x.com">B</a><a href="http://y.com">C</a>"""
    r = EmailParser().parse(raw)
    assert [l["href"] for l in r.links] == ["http://x.com", "http://x.com", "http://y.com"]
    assert r.link_urls == ["http://x.com", "http://y.com"]


def test_broken_html_never_raises():
    raw = """From: a@b.com
Subject: T
Content-Type: text/html

<div><a href="http://x.com">unclosed"""
    r = EmailParser().parse(raw)
    assert r.links[0]["href"] == "http://x.com"


def _multipart_with_image(image_bytes: bytes, content_id: str = "logo1", filename: str = "") -> str:
    b64 = base64.b64encode(image_bytes).decode()
    filename_hdr = f'Content-Disposition: inline; filename="{filename}"\n' if filename else ""
    return f"""From: a@b.com
Subject: T
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="MIX"

--MIX
Content-Type: text/html; charset="UTF-8"

<img src="cid:{content_id}">
--MIX
Content-Type: image/png
Content-Transfer-Encoding: base64
Content-ID: <{content_id}>
{filename_hdr}
{b64}
--MIX--"""


def test_inline_image_extracted():
    payload = _png_bytes()
    r = EmailParser().parse(_multipart_with_image(payload))
    assert len(r.images) == 1
    img = r.images[0]
    assert img["content_type"] == "image/png"
    assert img["content_id"] == "logo1"
    assert img["size"] == len(payload)
    assert base64.b64decode(img["data_base64"]) == payload


def test_image_attachment_goes_to_both_images_and_attachments():
    payload = _png_bytes()
    raw = _multipart_with_image(payload, filename="logo.png")
    r = EmailParser().parse(raw)
    assert len(r.images) == 1
    assert r.attachments[0]["filename"] == "logo.png"
    assert r.attachments[0]["content_type"] == "image/png"


def test_oversize_image_skipped():
    r = EmailParser().parse(_multipart_with_image(b"x" * (_MAX_IMAGE_BYTES + 1)))
    assert r.images == []
    # метаданные вложения сохраняются даже без payload
    assert r.attachments[0]["content_type"] == "image/png"


def test_non_image_attachment_metadata_only():
    raw = """From: a@b.com
Subject: T
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="MIX"

--MIX
Content-Type: text/plain

body
--MIX
Content-Type: application/pdf
Content-Disposition: attachment; filename="doc.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQ=
--MIX--"""
    r = EmailParser().parse(raw)
    assert r.images == []
    assert len(r.attachments) == 1
    assert r.attachments[0]["filename"] == "doc.pdf"
