import logging
import os
import json
import sys
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from confluent_kafka import Consumer, KafkaError
import threading

from src.notifications import dispatch_notifications, get_notification_channels

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global event_loop
    event_loop = asyncio.get_running_loop()
    asyncio.create_task(_broadcast_worker())
    thread = threading.Thread(target=consume_fraud_events, args=(event_loop,), daemon=True)
    thread.start()
    yield

app = FastAPI(title="Alerting Service", lifespan=lifespan)

recent_alerts: List[Dict[str, Any]] = []
recent_alerts_max = int(os.getenv("RECENT_ALERTS_MAX", "200"))
connected_clients: Set[WebSocket] = set()
alert_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
event_loop: asyncio.AbstractEventLoop | None = None

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def _store_recent_alert(payload: Dict[str, Any]):
    alert_id = payload.get("alert_id")
    if alert_id:
        recent_alerts[:] = [item for item in recent_alerts if item.get("alert_id") != alert_id]
    recent_alerts.append(payload)
    if len(recent_alerts) > recent_alerts_max:
        del recent_alerts[: len(recent_alerts) - recent_alerts_max]

def consume_fraud_events(loop: asyncio.AbstractEventLoop):
    """
    Background thread to consume fraud events from Kafka and trigger alerts.
    """
    conf = {
        'bootstrap.servers': os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        'group.id': 'alerting-service-group',
        'auto.offset.reset': 'earliest'
    }
    
    consumer = Consumer(conf)
    topic = os.getenv("KAFKA_FRAUD_ALERTS_TOPIC", "fraud.alerts")
    consumer.subscribe([topic])
    
    logger.info(f"Started consuming fraud alerts from topic: {topic}")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    logger.error(f"Kafka error: {msg.error()}")
                    continue
            
            # Process fraud alert
            try:
                alert_data = json.loads(msg.value().decode('utf-8'))
                payload = dict(alert_data)
                payload["received_at"] = datetime.now(timezone.utc).isoformat()
                payload["notification_results"] = dispatch_notifications(payload)
                payload["notifications_attempted_at"] = datetime.now(timezone.utc).isoformat()
                _store_recent_alert(payload)

                asyncio.run_coroutine_threadsafe(alert_queue.put(payload), loop)
                logger.info(f"CRITICAL: Fraud detected! Alert ID: {payload.get('alert_id')}")
            except Exception as e:
                logger.error(f"Error processing alert message: {e}")
                
    finally:
        consumer.close()

@app.get("/alerts/recent")
async def get_recent_alerts(limit: int = 50):
    limit = max(1, min(int(limit), recent_alerts_max))
    return list(reversed(recent_alerts[-limit:]))


@app.get("/alerts/channels")
async def get_alert_channels():
    channels = get_notification_channels()
    configured_count = sum(1 for channel in channels if channel.get("configured"))
    return {
        "configured_channel_count": configured_count,
        "channels": channels,
    }

@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)

async def _broadcast_worker():
    while True:
        payload = await alert_queue.get()
        if not connected_clients:
            continue
        message = json.dumps(payload)
        to_remove: List[WebSocket] = []
        for ws in list(connected_clients):
            try:
                await ws.send_text(message)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            connected_clients.discard(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9005)
