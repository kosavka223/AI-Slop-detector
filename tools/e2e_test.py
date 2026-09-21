"""E2E тест: отправляет текст и сам подкидывает 3 недостающих результата."""
import asyncio
import json
import random
import uuid

import httpx
from aiokafka import AIOKafkaProducer

KAFKA = "localhost:9092"
GATEWAY = "http://localhost:8000/api/v1/analyze"
DELAY_AFTER_REQUEST = 2  # сек, ждём пока мок успеет обработать


async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(GATEWAY, json={"text": "E2E automated test text."})
        resp.raise_for_status()
        task_id = resp.json()["task_id"]
        print(f"[e2e] task created: {task_id}", flush=True)

    await asyncio.sleep(DELAY_AFTER_REQUEST)  # мок успевает кинуть text-результат

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    try:
        for atype in ("html", "images", "links-meta"):
            msg = {
                "task_id": task_id,
                "analyzer_type": atype,
                "score": round(random.uniform(0.0, 1.0), 3),
                "features": {"mock": True},
            }
            await producer.send_and_wait(f"analysis.{atype}", msg)
            print(f"[e2e] sent {atype}: score={msg['score']}", flush=True)
    finally:
        await producer.stop()

    print(f"\n[e2e] Готово. Вердикт смотри в терминале decision engine и в БД:", flush=True)
    print(f'  docker exec -it slop-postgres psql -U dev -d slop -c '
          f'"SELECT * FROM verdicts WHERE email_id = \'{task_id}\';"', flush=True)


if __name__ == "__main__":
    asyncio.run(main())