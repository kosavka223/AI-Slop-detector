"""Image analyzer: QR detection plus conservative AI-image heuristics."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")


def analyze_image(image_data: bytes) -> tuple[float, dict, str]:
    features: dict = {"bytes": len(image_data), "qr_codes": []}
    if not image_data:
        return 0.0, features, "no image payload"
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_data))
        features.update({"format": image.format, "width": image.width, "height": image.height, "mode": image.mode, "metadata_keys": sorted(image.info.keys())})
        # Missing metadata is weak evidence only; it is common after email sanitization.
        score = 0.10 if not image.info else 0.0
    except Exception as exc:
        features["decode_error"] = str(exc)
        return 0.0, features, "image could not be decoded"
    try:
        import cv2
        import numpy as np
        matrix = cv2.imdecode(np.frombuffer(image_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if matrix is not None:
            detector = cv2.QRCodeDetector()
            ok, decoded, _, _ = detector.detectAndDecodeMulti(matrix)
            if ok:
                features["qr_codes"] = [value for value in decoded if value]
            else:
                value, _, _ = detector.detectAndDecode(matrix)
                if value:
                    features["qr_codes"] = [value]
    except ImportError:
        features["qr_detection"] = "opencv unavailable"
    except Exception as exc:
        features["qr_detection_error"] = str(exc)
    if features["qr_codes"]:
        score += 0.25
    reason = "QR code detected" if features["qr_codes"] else "no QR code detected; AI-image score is heuristic"
    return round(min(score, 1.0), 3), features, reason


def _payloads(data: dict) -> list[bytes]:
    """emails.parsed: список картинок от парсера (+ legacy: одиночная картинка)."""
    payloads: list[bytes] = []
    for image in data.get("images") or []:
        value = image.get("data_base64") if isinstance(image, dict) else None
        if isinstance(value, str):
            try:
                payloads.append(base64.b64decode(value, validate=False))
            except Exception:
                continue
    legacy = data.get("image_data") or data.get("image_base64")
    if isinstance(legacy, str):
        try:
            payloads.append(base64.b64decode(legacy.split(",", 1)[-1], validate=False))
        except Exception:
            pass
    elif isinstance(legacy, (bytes, bytearray)):
        payloads.append(bytes(legacy))
    return payloads


async def main() -> None:
    consumer = AIOKafkaConsumer("emails.parsed", bootstrap_servers=KAFKA, group_id="image-analyzer")
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA, value_serializer=lambda v: json.dumps(v).encode())
    await consumer.start(); await producer.start()
    print("Image analyzer: emails.parsed -> analysis.images", flush=True)
    try:
        async for msg in consumer:
            try:
                data = json.loads(msg.value.decode())
                payloads = _payloads(data)
                if payloads:
                    results = [analyze_image(p) for p in payloads]
                    score = max(r[0] for r in results)
                    features = {"image_count": len(results), "images": [r[1] for r in results]}
                    reason = "; ".join(r[2] for r in results)
                else:
                    score, features, reason = 0.0, {"image_count": 0}, "no image payloads in message"
                await producer.send_and_wait("analysis.images", {"task_id": data["task_id"], "analyzer_type": "images", "score": score, "features": features, "reason": reason, "analyzed_at": datetime.now(timezone.utc).isoformat()})
            except Exception as exc:
                print(f"[images] skipped malformed message: {exc}", flush=True)
    finally:
        await consumer.stop(); await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
