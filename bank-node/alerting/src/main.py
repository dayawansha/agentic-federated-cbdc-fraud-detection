import logging
import os
import json
import sys
from fastapi import FastAPI
from confluent_kafka import Consumer, KafkaError
import threading

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from shared.schemas.models import FraudAlert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alerting Service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def consume_fraud_events():
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
                    break
            
            # Process fraud alert
            try:
                alert_data = json.loads(msg.value().decode('utf-8'))
                logger.info(f"CRITICAL: Fraud detected! Alert ID: {alert_data.get('alert_id')}")
                # Logic to send email, SMS, or create a ticket would go here
            except Exception as e:
                logger.error(f"Error processing alert message: {e}")
                
    finally:
        consumer.close()

@app.on_event("startup")
async def startup_event():
    # Start Kafka consumer in a separate thread
    thread = threading.Thread(target=consume_fraud_events, daemon=True)
    thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9005)
