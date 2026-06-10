import json
import logging
from confluent_kafka import Producer
import os

logger = logging.getLogger(__name__)

class CDCService:
    def __init__(self):
        self.producer_conf = {
            'bootstrap.servers': os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            'client.id': 'transaction-graph-service'
        }
        self.topic = os.getenv("KAFKA_TRANSACTION_TOPIC", "transactions.events")
        try:
            self.producer = Producer(self.producer_conf)
            logger.info(f"Kafka producer initialized for topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            self.producer = None

    def publish_transaction(self, tx_data: dict):
        if not self.producer:
            logger.warning("Kafka producer not available, skipping publish")
            return

        try:
            self.producer.produce(
                self.topic,
                key=tx_data['transaction_id'],
                value=json.dumps(tx_data),
                callback=self._delivery_report
            )
            # Flush to ensure delivery (in production you might do this periodically)
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Error publishing to Kafka: {e}")

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

cdc_service = CDCService()
