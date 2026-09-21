"""Aggregator: собирает результаты анализаторов, шлёт aggregated."""
import asyncio
import json
import os
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
ANALYSIS_TOPICS = ["analysis.text", "analysis.html", "analysis.images", "analysis.links-meta"]
OUTPUT_TOPIC = "analysis.aggregated"
DLQ_TOPIC = "dead-letter-queue"
EXPECTED_ANALYZERS = 4          # сколько анализаторов ждём
TASK_TIMEOUT_SEC = 30           # если не собрали всё — в DLQ


class TaskBuffer:
    """Копит результаты по task_id и решает, когда задача готова."""

    def __init__(self):
        self.results: dict[str, list] = {}
        self.deadline: dict[str, float] = {}

    def add(self, task_id: str, message: dict) -> list | None:
        """Добавляет результат. Возвращает список результатов, если задача собрана."""
        now = asyncio.get_event_loop().time()
        if task_id not in self.results:
            self.results[task_id] = []
            self.deadline[task_id] = now + TASK_TIMEOUT_SEC
        # идемпотентность: дубликат не добавляем
        if message not in self.results[task_id]:
            self.results[task_id].append(message)
        return self.results[task_id] if self.is_complete(task_id, now) else None

    def is_complete(self, task_id: str, now: float) -> bool:
        types = {r.get("analyzer_type") for r in self.results[task_id]}
        return len(types) >= EXPECTED_ANALYZERS or now >= self.deadline.get(task_id, 0)

    def pop_expired(self) -> list[str]:
        """Возвращает task_id задач, у которых вышло время."""
        now = asyncio.get_event_loop().time()
        expired = [
            tid for tid, dl in self.deadline.items()
            if tid in self.results and now >= dl
        ]
        for tid in expired:
            self.results.pop(tid, None)
            self.deadline.pop(tid, None)
        return expired


async def main():
    consumer = AIOKafkaConsumer(
        *ANALYSIS_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="aggregator",
        # value_deserializer НЕ используем — парсим вручную с защитой от битых JSON
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await producer.start()
    print(f"Aggregator: listening {ANALYSIS_TOPICS} -> {OUTPUT_TOPIC}", flush=True)

    buffer = TaskBuffer()

    async def timeout_watcher():
        """Периодически проверяет задачи, зависшие по таймауту."""
        while True:
            await asyncio.sleep(5)
            for tid in buffer.pop_expired():
                await producer.send_and_wait(DLQ_TOPIC, {
                    "task_id": tid,
                    "reason": "aggregation timeout",
                    "at": datetime.now(timezone.utc).isoformat(),
                })
                print(f"[aggregator] task={tid} -> DLQ (timeout)", flush=True)

    watcher = asyncio.create_task(timeout_watcher())

    try:
        async for msg in consumer:
            # --- ручной парсинг JSON с защитой от битых сообщений ---
            try:
                data = json.loads(msg.value.decode("utf-8"))
            except Exception as e:
                await producer.send_and_wait(DLQ_TOPIC, {
                    "topic": msg.topic,
                    "error": f"deserialization failed: {e}",
                    "raw": msg.value.decode("utf-8", errors="replace"),
                })
                print(f"[aggregator] bad message from {msg.topic} -> DLQ: {e}", flush=True)
                continue

            task_id = data.get("task_id")
            if not task_id:
                continue

            data["analyzer_type"] = data.get("analyzer_type") or msg.topic.split(".")[-1]

            results = buffer.add(task_id, data)
            if results is not None:
                aggregated = {
                    "task_id": task_id,
                    "results": results,
                    "aggregated_at": datetime.now(timezone.utc).isoformat(),
                }
                await producer.send_and_wait(OUTPUT_TOPIC, aggregated)
                print(f"[aggregator] task={task_id} aggregated "
                      f"({len(results)} results) -> {OUTPUT_TOPIC}", flush=True)
                buffer.results.pop(task_id, None)
                buffer.deadline.pop(task_id, None)
    finally:
        watcher.cancel()
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())