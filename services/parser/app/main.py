"""Parser service: emails.raw -> emails.parsed (MIME -> structured contract).

Контракт сообщения emails.parsed фиксирует shared/models/analysis.py::ParsedEmail —
его валидирует эта страница перед публикацией. Контракт принадлежит Data/Network
Engineer; изменения только через PR.

Принимает два формата emails.raw:
  {"task_id", "raw_email": base64(RFC 5322)}  — полный MIME (когда gateway научится)
  {"task_id", "text": "..."}                  — текущий формат gateway v1 (text/plain)
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # noqa: E402

from services.parser.parser import EmailParser  # noqa: E402
from shared.models.analysis import ParsedEmail as ParsedEmailContract  # noqa: E402

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
RAW_TOPIC = "emails.raw"
PARSED_TOPIC = "emails.parsed"

_parser = EmailParser()


def _decode_raw(raw) -> str:
    """raw_email: base64-строка с байтами письма (или сам RFC 5322 текст)."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    try:
        return base64.b64decode(raw, validate=True).decode("utf-8", errors="ignore")
    except Exception:
        return raw  # не base64 — считаем готовым текстом письма


def build_parsed_message(data: dict) -> dict | None:
    """emails.raw payload -> сообщение контракта emails.parsed.

    Чистая функция: тестируется без Kafka. Возвращает None для сообщений
    без task_id. Падает с исключением при дрейфе схемы — контракт валидируется
    здесь, а не у потребителей.
    """
    task_id = data.get("task_id")
    if not task_id:
        return None

    if data.get("raw_email"):
        parsed = _parser.parse(_decode_raw(data["raw_email"]))
    else:
        # Gateway v1 шлёт только {"task_id", "text"} — трактуем как text/plain body.
        parsed = _parser.parse(data.get("text") or "")

    message = {
        "task_id": task_id,
        "email_id": data.get("email_id") or task_id,
        "subject": parsed.subject,
        "from_addr": parsed.from_addr,
        "to_addr": parsed.to_addr,
        "date": parsed.date,
        "message_id": parsed.message_id,
        "text_part": parsed.text_body or None,
        "html_part": parsed.html_body or None,
        "images": parsed.images,
        "links": parsed.links,
        "attachments": parsed.attachments,
        "raw_headers": parsed.raw_headers,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
    }
    ParsedEmailContract.model_validate(message)
    return message


async def main() -> None:
    consumer = AIOKafkaConsumer(RAW_TOPIC, bootstrap_servers=KAFKA, group_id="parser")
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA, value_serializer=lambda v: json.dumps(v).encode()
    )
    await consumer.start()
    await producer.start()
    print(f"Parser: {RAW_TOPIC} -> {PARSED_TOPIC}", flush=True)
    try:
        async for msg in consumer:
            try:
                data = json.loads(msg.value.decode())
                message = build_parsed_message(data)
                if message is None:
                    print("[parser] skipped message without task_id", flush=True)
                    continue
                await producer.send_and_wait(PARSED_TOPIC, message)
            except Exception as exc:
                print(f"[parser] skipped malformed message: {exc}", flush=True)
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
