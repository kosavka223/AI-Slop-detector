"""Ручная проверка парсера: emails.raw -> emails.parsed через живой Kafka.

Запуск (Kafka и parser должны быть подняты: make up-all или docker compose up -d kafka parser):
    python tools/check_parser.py

Шлёт в emails.raw два сообщения:
  1. формат gateway-v1 (только текст);
  2. полный RFC 5322 MIME в base64 (html + anchor-ссылка + inline-картинка).
Читает emails.parsed и печатает разобранный контракт.
"""
import asyncio
import base64
import json
import os

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

RAW_MIME = """From: Pensionnyi Fond <support@phish.example>
To: victim@bank.com
Subject: =?UTF-8?B?0JLRi9C40LPRgNCw0Lk=?=
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="MIX"

--MIX
Content-Type: text/html; charset="UTF-8"

<p>PKO Bank: <a href="http://evil.example.com/login">Sberbank Online</a></p>
--MIX
Content-Type: image/png
Content-Transfer-Encoding: base64
Content-ID: <logo1>

iVBORw0KGgo=
--MIX--"""


async def main():
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA, value_serializer=lambda v: json.dumps(v).encode()
    )
    await producer.start()
    await producer.send_and_wait("emails.raw", {
        "task_id": "parser-check-1", "created_at": "gateway-v1",
        "text": "Urgent! Confirm your account at http://evil-bank.example/login NOW"})
    await producer.send_and_wait("emails.raw", {
        "task_id": "parser-check-2", "raw_email": base64.b64encode(RAW_MIME.encode()).decode()})
    await producer.flush()
    await producer.stop()
    print("[check] produced 2 messages -> emails.raw", flush=True)

    consumer = AIOKafkaConsumer(
        "emails.parsed", bootstrap_servers=KAFKA,
        group_id="parser-check", auto_offset_reset="latest",
    )
    await consumer.start()
    msgs = []
    try:
        while len(msgs) < 2:
            batch = await consumer.getmany(timeout_ms=10000, max_records=2 - len(msgs))
            for records in batch.values():
                msgs.extend(records)
            if not batch and not msgs:
                break
    finally:
        await consumer.stop()

    for m in sorted(msgs, key=lambda x: json.loads(x.value)["task_id"]):
        d = json.loads(m.value)
        print(f"\n[{d['task_id']}] subject={d['subject']!r} from={d['from_addr']!r}")
        print(f"  text_part : {(d['text_part'] or '')[:60]!r}")
        print(f"  links     : {d['links']}")
        print(f"  images    : {[(i['content_type'], i['content_id'], i['size']) for i in d['images']]}")
    print(f"\n[check] received {len(msgs)}/2 — "
          + ("OK" if len(msgs) == 2 else "FAIL: parser не отвечает"))


if __name__ == "__main__":
    asyncio.run(main())
