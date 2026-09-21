import uuid
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from aiokafka import AIOKafkaProducer
from redis import asyncio as aioredis

from app.config import KAFKA_BOOTSTRAP, REDIS_URL, TOPIC_RAW


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await app.state.producer.start()
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    await app.state.producer.stop()
    await app.state.redis.aclose()


app = FastAPI(title="API Gateway", version="0.1.0", lifespan=lifespan)


class AnalyzeIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=50_000)


@app.post("/api/v1/analyze")
async def analyze(payload: AnalyzeIn):
    task_id = str(uuid.uuid4())
    message = {
        "task_id": task_id,
        "text": payload.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await app.state.producer.send_and_wait(TOPIC_RAW, message)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kafka unavailable: {e}")

    await app.state.redis.hset(f"task:{task_id}", mapping={"status": "processing"})
    await app.state.redis.expire(f"task:{task_id}", 3600)

    return {"task_id": task_id, "status": "accepted"}


@app.get("/api/v1/status/{task_id}")
async def status(task_id: str):
    data = await app.state.redis.hgetall(f"task:{task_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "status": data.get("status", "processing")}


@app.get("/health")
async def health():
    return {"status": "healthy"}