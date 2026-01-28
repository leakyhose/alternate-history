"""Kafka producer for portrait events."""
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from .config import KAFKA_BOOTSTRAP_SERVERS, TOPIC_PORTRAITS_READY

logger = logging.getLogger(__name__)


class PortraitsProducer:
    """Produces portrait events to Kafka."""

    def __init__(self):
        self._producer: Optional[KafkaProducer] = None

    def connect(self) -> None:
        """Connect to Kafka."""
        logger.info(f"Connecting producer to {KAFKA_BOOTSTRAP_SERVERS}")

        self._producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks=1,
            retries=3,
        )

    def produce_portraits(
        self,
        game_id: str,
        iteration: int,
        portraits: List[Dict[str, Any]],
    ) -> bool:
        """Publish portraits to Kafka."""
        if not self._producer:
            raise RuntimeError("Producer not connected")

        event = {
            "event_type": "portraits_ready",
            "game_id": game_id,
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "portraits": portraits,
            "status": "success",
        }

        try:
            future = self._producer.send(
                topic=TOPIC_PORTRAITS_READY, key=game_id, value=event
            )
            future.get(timeout=10)
            logger.info(f"Published {len(portraits)} portraits for game={game_id}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish portraits: {e}")
            return False

    def produce_failure(self, game_id: str, iteration: int, error: str) -> bool:
        """Publish a failure event."""
        if not self._producer:
            raise RuntimeError("Producer not connected")

        event = {
            "event_type": "portraits_failed",
            "game_id": game_id,
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "error": error,
            "portraits": [],
            "status": "failed",
        }

        try:
            future = self._producer.send(
                topic=TOPIC_PORTRAITS_READY, key=game_id, value=event
            )
            future.get(timeout=10)
            logger.warning(f"Published failure for game={game_id}: {error}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish failure event: {e}")
            return False

    def close(self) -> None:
        """Close the producer."""
        if self._producer:
            self._producer.flush()
            self._producer.close()
            self._producer = None
