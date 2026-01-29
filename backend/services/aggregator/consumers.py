"""Kafka consumers for aggregator service.

Consumes from multiple topics and forwards events to WebSocket clients.
Uses threading to bridge sync Kafka consumer to async FastAPI.
"""
import asyncio
import json
import logging
import threading
from typing import Callable, Optional

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from .config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    ALL_TOPICS,
    TOPIC_TIMELINE_EVENTS,
    TOPIC_QUOTES_READY,
    TOPIC_PROVINCES_UPDATED,
    TOPIC_PORTRAITS_READY,
)

logger = logging.getLogger(__name__)


# Map topic names to message types for frontend
TOPIC_TO_MESSAGE_TYPE = {
    TOPIC_TIMELINE_EVENTS: "timeline_update",
    TOPIC_QUOTES_READY: "quotes_update",
    TOPIC_PROVINCES_UPDATED: "provinces_update",
    TOPIC_PORTRAITS_READY: "portraits_update",
}


class AggregatorConsumer:
    """Consumes from all Kafka topics and forwards to WebSocket manager.

    Runs in a background thread, posting events to an async queue
    that the main FastAPI app processes.
    """

    def __init__(self):
        self._consumer: Optional[KafkaConsumer] = None
        self._thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()
        self._event_queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue) -> None:
        """Start the consumer in a background thread."""
        self._loop = loop
        self._event_queue = event_queue
        self._shutdown.clear()

        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("Aggregator consumer thread started")

    def stop(self) -> None:
        """Stop the consumer thread."""
        self._shutdown.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._consumer:
            self._consumer.close()
            self._consumer = None
        logger.info("Aggregator consumer stopped")

    def _run_consumer(self) -> None:
        """Consumer loop running in background thread."""
        try:
            logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
            logger.info(f"Subscribing to topics: {ALL_TOPICS}")

            self._consumer = KafkaConsumer(
                *ALL_TOPICS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_CONSUMER_GROUP,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="latest",  # Only care about new events
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                consumer_timeout_ms=1000,
            )

            logger.info("Kafka consumer connected, waiting for events...")

            while not self._shutdown.is_set():
                try:
                    message_batch = self._consumer.poll(timeout_ms=500)

                    for topic_partition, messages in message_batch.items():
                        topic = topic_partition.topic
                        message_type = TOPIC_TO_MESSAGE_TYPE.get(topic, "unknown")

                        for message in messages:
                            event = message.value
                            game_id = event.get("game_id")

                            if not game_id:
                                logger.warning(f"Event without game_id from {topic}")
                                continue

                            # Create WebSocket message
                            ws_message = {
                                "type": message_type,
                                **event,
                            }

                            # Post to async queue
                            self._post_to_queue(game_id, ws_message)

                            logger.debug(
                                f"Queued {message_type} for game={game_id}, "
                                f"iteration={event.get('iteration')}"
                            )

                except KafkaError as e:
                    logger.error(f"Kafka error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Consumer thread error: {e}")
        finally:
            if self._consumer:
                self._consumer.close()

    def _post_to_queue(self, game_id: str, message: dict) -> None:
        """Post an event to the async queue (thread-safe)."""
        if self._loop and self._event_queue:
            self._loop.call_soon_threadsafe(
                self._event_queue.put_nowait,
                (game_id, message)
            )


# Global consumer instance
consumer = AggregatorConsumer()
