"""Мок-анализатор: emails.raw -> analysis.text (фейковые скоры)."""
import asyncio
import json
import random
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

RAW_TOPIC = "emails.raw"
OUTPUT_TOPIC = "analysis.text"


async def main():
    consumer = AIOKafkaConsumer(
        RAW_TOPIC,
        bootstrap_servers="localhost:9092",
        group_id="mock-analyzer",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await producer.start()
    print(f"Mock-analyzer: listening {RAW_TOPIC} -> writing {OUTPUT_TOPIC}", flush=True)

    try:
        async for msg in consumer:
            data = msg.value
            result = {
                "task_id": data["task_id"],
                "analyzer_type": "text",
                "score": round(random.uniform(0.0, 1.0), 3),
                "features": {"mock": True},
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
            await producer.send_and_wait(OUTPUT_TOPIC, result)
            print(f"[mock] task={data['task_id']} score={result['score']}", flush=True)
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())