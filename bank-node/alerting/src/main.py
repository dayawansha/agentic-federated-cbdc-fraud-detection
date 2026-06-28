"""
================================================================================
ALERTING SERVICE - BUSINESS LOGIC & EXPLANATION
================================================================================
Think of the Alerting service as the bank's "24/7 Security Watchtower."
Its job is to watch all transactions as they happen in real-time, evaluate their risk,
generate alert tickets, and notify human fraud operators.

THE SERVICE OPERATES THROUGH THESE STEPS:
1. STREAM LISTENING (Kafka Consumer): It listens to two streaming pipelines (Kafka topics):
   - `transactions.events`: A real-time log of every payment recorded by the transaction-graph.
   - `fraud.alerts`: Alerts published by the GNN Model during inference.
2. SIMPLE RULE CHECKS: As transactions pass through, it runs fast checks:
   - Is the transfer amount over $10,000 (medium severity) or over $50,000 (high severity)?
   - Is an account repeating transactions rapidly (more than 5 times in a few minutes)?
3. ALERT PERSISTENCE: If a rule is breached, or if the GNN model reports an illicit prediction,
   the service creates a unified alert (containing the transaction ID, severity level,
   and reason) and saves it to a PostgreSQL database.
4. LIVE DASHBOARD NOTIFICATION: It maintains a WebSocket connection with the operator
   web dashboard. When an alert is created, it instantly pushes it to the browser.
5. EMAIL/WEBHOOK DISPATCH: It triggers notifications to send out alerts to external endpoints
   so compliance officers get warned immediately.
================================================================================
"""
import logging
import os
import json
import sys
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from confluent_kafka import Consumer, KafkaError, Producer
import threading
from sqlalchemy import JSON, Column, DateTime, Integer, String, Float, create_engine, desc, select
from sqlalchemy.orm import declarative_base, sessionmaker

from src.notifications import dispatch_notifications, get_notification_channels

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TRANSACTION_EVENTS_TOPIC = os.getenv("KAFKA_TRANSACTION_EVENTS_TOPIC", os.getenv("KAFKA_TRANSACTION_TOPIC", "transactions.events"))
KAFKA_FRAUD_ALERTS_TOPIC = os.getenv("KAFKA_FRAUD_ALERTS_TOPIC", "fraud.alerts")
TX_ALERT_AMOUNT_THRESHOLD = float(os.getenv("TX_ALERT_AMOUNT_THRESHOLD", "10000"))
TX_ALERT_HIGH_AMOUNT_THRESHOLD = float(os.getenv("TX_ALERT_HIGH_AMOUNT_THRESHOLD", "50000"))
TX_ALERT_REPEAT_THRESHOLD = int(os.getenv("TX_ALERT_REPEAT_THRESHOLD", "5"))
TX_ALERT_METADATA_RISK_THRESHOLD = float(os.getenv("TX_ALERT_METADATA_RISK_THRESHOLD", "0.8"))

Base = declarative_base()
engine = None
SessionLocal = None
db_ready = False
alert_producer = None


class AlertRecord(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String, nullable=True, unique=True, index=True)
    tx_id = Column(String, nullable=True, index=True)
    severity = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    status = Column(String, nullable=True)
    source = Column(String, nullable=True)
    agent_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    notifications_attempted_at = Column(DateTime(timezone=True), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)


def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    database = os.getenv("POSTGRES_DB", "federated_fraud_db")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def _create_engine():
    database_url = _build_database_url()
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}
    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _setup_database() -> None:
    global engine, SessionLocal, db_ready
    if db_ready:
        return
    try:
        engine = _create_engine()
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)
        db_ready = True
        logger.info("Alerting persistence initialized successfully")
    except Exception as exc:
        engine = None
        SessionLocal = None
        db_ready = False
        logger.warning("Alerting database unavailable, continuing with in-memory alert history only: %s", exc)


def _setup_alert_producer() -> None:
    global alert_producer
    if alert_producer is not None:
        return
    try:
        alert_producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "client.id": "alerting-service-detector",
            }
        )
        logger.info("Alerting detector Kafka producer initialized")
    except Exception as exc:
        alert_producer = None
        logger.warning("Alerting detector Kafka producer unavailable: %s", exc)


def _persist_alert(payload: Dict[str, Any]) -> None:
    if not db_ready or SessionLocal is None:
        return

    alert_id = payload.get("alert_id")
    received_at = _parse_datetime(payload.get("received_at")) or datetime.now(timezone.utc)
    notifications_attempted_at = _parse_datetime(payload.get("notifications_attempted_at"))
    tx_id = payload.get("txId", payload.get("tx_id"))

    with SessionLocal() as session:
        existing = None
        if alert_id:
            existing = session.execute(
                select(AlertRecord).where(AlertRecord.alert_id == str(alert_id)).limit(1)
            ).scalar_one_or_none()

        if existing is None:
            existing = AlertRecord(
                alert_id=str(alert_id) if alert_id is not None else None,
                received_at=received_at,
                payload=dict(payload),
            )
            session.add(existing)

        existing.tx_id = str(tx_id) if tx_id is not None else None
        existing.severity = str(payload.get("severity")) if payload.get("severity") is not None else None
        existing.confidence_score = (
            float(payload.get("confidence_score")) if payload.get("confidence_score") is not None else None
        )
        existing.status = str(payload.get("status")) if payload.get("status") is not None else None
        existing.source = str(payload.get("source")) if payload.get("source") is not None else None
        existing.agent_id = str(payload.get("agent_id")) if payload.get("agent_id") is not None else None
        existing.timestamp = _parse_datetime(payload.get("timestamp"))
        existing.received_at = received_at
        existing.notifications_attempted_at = notifications_attempted_at
        existing.payload = dict(payload)
        session.commit()


def _fetch_recent_alerts(limit: int) -> List[Dict[str, Any]]:
    if not db_ready or SessionLocal is None:
        return list(reversed(recent_alerts[-limit:]))

    with SessionLocal() as session:
        rows = session.execute(
            select(AlertRecord).order_by(desc(AlertRecord.received_at), desc(AlertRecord.id)).limit(limit)
        ).scalars().all()
        return [dict(row.payload or {}) for row in rows]


def _normalize_severity(value: Any) -> str:
    normalized = str(value or "medium").strip().lower()
    if normalized not in {"critical", "high", "medium", "low"}:
        return "medium"
    return normalized


def _score_to_severity(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_transaction_stream_alert(event: Dict[str, Any]) -> Dict[str, Any] | None:
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    amount = _coerce_float(event.get("amount"))
    metadata_risk = _coerce_float(metadata.get("risk_score"), default=-1.0)
    repeat_count = max(
        _coerce_int(metadata.get("repeat_count")),
        _coerce_int(metadata.get("tx_count_1h")),
        _coerce_int(metadata.get("velocity_count")),
    )
    source_account = str(event.get("source_account") or "")
    target_account = str(event.get("target_account") or "")

    score = 0.0
    reasons: List[str] = []
    if amount >= TX_ALERT_AMOUNT_THRESHOLD:
        reasons.append(f"transaction amount {amount:.2f} exceeded threshold")
        score += 0.45
    if amount >= TX_ALERT_HIGH_AMOUNT_THRESHOLD:
        reasons.append(f"transaction amount {amount:.2f} exceeded high-risk threshold")
        score += 0.3
    if repeat_count >= TX_ALERT_REPEAT_THRESHOLD:
        reasons.append(f"transaction velocity count {repeat_count} exceeded threshold")
        score += 0.25
    if source_account and target_account and source_account == target_account:
        reasons.append("self-transfer detected")
        score += 0.2
    if metadata_risk >= TX_ALERT_METADATA_RISK_THRESHOLD:
        reasons.append(f"upstream metadata risk score {metadata_risk:.2f} exceeded threshold")
        score = max(score, metadata_risk)

    score = min(score, 1.0)
    if not reasons or score < 0.5:
        return None

    tx_id = event.get("transaction_id") or event.get("txId") or event.get("tx_id")
    timestamp = event.get("timestamp") or datetime.now(timezone.utc).isoformat()
    return {
        "alert_id": f"stream-{tx_id or uuid.uuid4().hex[:12]}",
        "txId": tx_id,
        "timestamp": timestamp,
        "severity": _score_to_severity(score),
        "confidence_score": score,
        "reason": "; ".join(reasons),
        "status": "open",
        "source": "transaction-stream-detector",
        "agent_id": "alerting-service",
        "source_account": source_account or None,
        "target_account": target_account or None,
        "detector_type": "rule-based-stream-detector",
        "raw_event": dict(event),
    }


def _publish_generated_alert(payload: Dict[str, Any]) -> bool:
    if alert_producer is None:
        return False
    try:
        alert_producer.produce(
            KAFKA_FRAUD_ALERTS_TOPIC,
            key=str(payload.get("alert_id") or uuid.uuid4().hex),
            value=json.dumps(payload),
        )
        alert_producer.poll(0)
        return True
    except Exception as exc:
        logger.error("Failed to publish generated stream alert %s: %s", payload.get("alert_id"), exc)
        return False


def _summarize_alerts(limit: int) -> Dict[str, Any]:
    alerts = _fetch_recent_alerts(limit)
    severity_counts = {severity: 0 for severity in ("critical", "high", "medium", "low")}
    source_counts: Dict[str, int] = {}
    recent_detector_alerts = 0
    for alert in alerts:
        severity = _normalize_severity(alert.get("severity"))
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        source = str(alert.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
        if source == "transaction-stream-detector":
            recent_detector_alerts += 1

    return {
        "alert_count": len(alerts),
        "severity_counts": severity_counts,
        "source_counts": source_counts,
        "detector_enabled": True,
        "transaction_topic": KAFKA_TRANSACTION_EVENTS_TOPIC,
        "alerts_topic": KAFKA_FRAUD_ALERTS_TOPIC,
        "recent_detector_alerts": recent_detector_alerts,
        "persistence_mode": "database" if db_ready else "memory-fallback",
        "outbound_channels": get_notification_channels(),
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global event_loop
    _setup_database()
    _setup_alert_producer()
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
    try:
        _persist_alert(payload)
    except Exception as exc:
        logger.error("Failed to persist alert %s: %s", alert_id, exc)

def consume_fraud_events(loop: asyncio.AbstractEventLoop):
    """
    Background thread to consume fraud events from Kafka and trigger alerts.
    """
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'alerting-service-group',
        'auto.offset.reset': 'earliest'
    }
    
    consumer = Consumer(conf)
    consumer.subscribe([KAFKA_TRANSACTION_EVENTS_TOPIC, KAFKA_FRAUD_ALERTS_TOPIC])
    
    logger.info(
        "Started alerting consumers for transaction topic %s and alert topic %s",
        KAFKA_TRANSACTION_EVENTS_TOPIC,
        KAFKA_FRAUD_ALERTS_TOPIC,
    )
    
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

            topic_name = msg.topic()
            try:
                event_payload = json.loads(msg.value().decode('utf-8'))
                if topic_name == KAFKA_TRANSACTION_EVENTS_TOPIC:
                    generated_alert = _build_transaction_stream_alert(dict(event_payload))
                    if not generated_alert:
                        continue
                    if _publish_generated_alert(generated_alert):
                        logger.info(
                            "Generated and published transaction-stream alert %s for tx %s",
                            generated_alert.get("alert_id"),
                            generated_alert.get("txId"),
                        )
                    else:
                        logger.warning(
                            "Publishing unavailable, routing generated transaction-stream alert %s locally",
                            generated_alert.get("alert_id"),
                        )
                        payload = dict(generated_alert)
                        payload["received_at"] = datetime.now(timezone.utc).isoformat()
                        payload["notification_results"] = dispatch_notifications(payload)
                        payload["notifications_attempted_at"] = datetime.now(timezone.utc).isoformat()
                        _store_recent_alert(payload)
                        asyncio.run_coroutine_threadsafe(alert_queue.put(payload), loop)
                    continue

                payload = dict(event_payload)
                payload["severity"] = _normalize_severity(payload.get("severity"))
                payload["received_at"] = datetime.now(timezone.utc).isoformat()
                payload["notification_results"] = dispatch_notifications(payload)
                payload["notifications_attempted_at"] = datetime.now(timezone.utc).isoformat()
                _store_recent_alert(payload)

                asyncio.run_coroutine_threadsafe(alert_queue.put(payload), loop)
                logger.info("Fraud alert routed and broadcast: %s", payload.get("alert_id"))
            except Exception as e:
                logger.error("Error processing Kafka message from %s: %s", topic_name, e)
                
    finally:
        consumer.close()

@app.get("/alerts/recent")
async def get_recent_alerts(limit: int = 50):
    limit = max(1, min(int(limit), recent_alerts_max))
    return _fetch_recent_alerts(limit)


@app.get("/alerts/summary")
async def get_alert_summary(limit: int = 200):
    limit = max(1, min(int(limit), max(recent_alerts_max, 500)))
    return _summarize_alerts(limit)


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
