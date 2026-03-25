from kafka import KafkaConsumer, KafkaProducer
import asyncio
import json
import os
import time

class PlatformBus:
    """Synchronous fallback Wrapper around Kafka for inter-agent and supervisor communications"""
    
    def __init__(self):
        self.servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self._producer = None

    def connect_producer(self):
        # Retry mechanism for Kafka connection
        for attempt in range(15):
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self.servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8")
                )
                print("✅ Successfully connected to Kafka Producer!")
                return
            except Exception as e:
                print(f"⚠️ Waiting for Kafka broker to become available (attempt {attempt+1}/15)... Error: {e}")
                time.sleep(3)
        print("❌ Failed to connect to Kafka producer after multiple retries.")

    async def send(self, topic: str, message: dict):
        if not self._producer:
            self.connect_producer()
        if self._producer:
            self._producer.send(topic, value=message)
            self._producer.flush()

    async def stop_producer(self):
        if self._producer:
            self._producer.close()
            self._producer = None

# Singleton instance for simple imports
bus = PlatformBus()
