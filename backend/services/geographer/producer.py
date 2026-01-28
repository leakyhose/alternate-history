"""Kafka producer for province update events."""
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from .config import KAFKA_BOOTSTRAP_SERVERS, TOPIC_PROVINCES_UPDATED

logger = logging.getLogger(__name__)


class ProvincesProducer:
    """Produces province update events to Kafka."""

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

    def produce_provinces(
        self,
        game_id: str,
        iteration: int,
        province_updates: List[Dict[str, Any]],
        year: int,
    ) -> bool:
        """Publish province updates to Kafka."""
        if not self._producer:
            raise RuntimeError("Producer not connected")

        event = {
            "event_type": "provinces_updated",
            "game_id": game_id,
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "province_updates": province_updates,
            "year": year,
        }

        try:
            future = self._producer.send(
                topic=TOPIC_PROVINCES_UPDATED, key=game_id, value=event
            )
            future.get(timeout=10)
            logger.info(f"Published {len(province_updates)} updates for game={game_id}")
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish provinces: {e}")
            return False

    def produce_failure(self, game_id: str, iteration: int, error: str) -> bool:
        """Publish a failure event."""
        if not self._producer:
            raise RuntimeError("Producer not connected")

        event = {
            "event_type": "provinces_failed",
            "game_id": game_id,
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "error": error,
            "province_updates": [],
        }

        try:
            future = self._producer.send(
                topic=TOPIC_PROVINCES_UPDATED, key=game_id, value=event
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
