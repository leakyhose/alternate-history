"""Kafka consumer for timeline events."""
import json
import logging
from typing import Iterator, Dict, Any, Optional

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from .config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    TOPIC_TIMELINE_EVENTS,
)

logger = logging.getLogger(__name__)


class TimelineEventConsumer:
    """Consumes TimelineEvents from Kafka."""

    def __init__(self, group_id: str = KAFKA_CONSUMER_GROUP):
        self.group_id = group_id
        self._consumer: Optional[KafkaConsumer] = None

    def connect(self) -> None:
        """Connect to Kafka and subscribe to timeline.events."""
        logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")

        self._consumer = KafkaConsumer(
            TOPIC_TIMELINE_EVENTS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
            consumer_timeout_ms=1000,
        )

        logger.info(f"Subscribed to {TOPIC_TIMELINE_EVENTS}")

    def consume(self) -> Iterator[Dict[str, Any]]:
        """Yield timeline events from Kafka."""
        if not self._consumer:
            raise RuntimeError("Consumer not connected")

        logger.info("Consuming timeline events...")

        while True:
            try:
                message_batch = self._consumer.poll(timeout_ms=1000)

                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        event = message.value
                        logger.info(
                            f"Received: game={event.get('game_id')}, "
                            f"iteration={event.get('iteration')}"
                        )
                        yield event

            except KafkaError as e:
                logger.error(f"Kafka error: {e}")
                continue

    def close(self) -> None:
        """Close the consumer."""
        if self._consumer:
            self._consumer.close()
            self._consumer = None
