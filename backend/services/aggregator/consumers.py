"""Kafka consumers for aggregator service."""
import asyncio
import json
import logging
import threading
from typing import Optional

import redis
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
    REDIS_URL,
)

logger = logging.getLogger(__name__)

TOPIC_TO_MESSAGE_TYPE = {
    TOPIC_TIMELINE_EVENTS: "timeline_update",
    TOPIC_QUOTES_READY: "quotes_update",
    TOPIC_PROVINCES_UPDATED: "provinces_update",
    TOPIC_PORTRAITS_READY: "portraits_update",
}


def transform_timeline_event(event: dict) -> dict:
    """Transform Kafka timeline event to frontend WebSocket format."""
    dreamer = event.get("dreamer_decision", {})
    filter_result = event.get("filter_result", {})

    original_divergences = filter_result.get("divergences", [])
    current_divergences = dreamer.get("divergences", [])

    updated_divergences = [d for d in current_divergences if d in original_divergences]
    new_divergences = [d for d in current_divergences if d not in original_divergences]

    current_provinces = event.get("current_provinces", [])
    provinces = []
    for p in current_provinces:
        provinces.append({
            "id": p.get("id"),
            "name": p.get("name", ""),
            "owner": p.get("owner", ""),
            "control": p.get("control", p.get("owner", "")),
        })

    return {
        "type": "timeline_update",
        "event_type": event.get("event_type", "timeline_event"),
        "game_id": event.get("game_id"),
        "iteration": event.get("iteration"),
        "timestamp": event.get("timestamp"),
        "scenario_id": event.get("scenario_id"),
        "year_range": event.get("year_range"),
        "writer_output": {
            "narrative": dreamer.get("narrative", ""),
            "updated_divergences": updated_divergences,
            "new_divergences": new_divergences,
            "merged": dreamer.get("merged", False),
        },
        "cartographer_output": {
            "territorial_changes": dreamer.get("territorial_changes", []),
        },
        "ruler_updates_output": {
            "rulers": dreamer.get("rulers", {}),
        },
        "current_provinces": provinces,
    }


def transform_provinces_event(event: dict) -> dict:
    """Transform Kafka provinces event to frontend WebSocket format."""
    province_updates = event.get("province_updates", [])

    provinces = []
    for p in province_updates:
        provinces.append({
            "id": p.get("id"),
            "name": p.get("name", ""),
            "owner": p.get("owner", ""),
            "control": p.get("control", p.get("owner", "")),
        })

    return {
        "type": "provinces_update",
        "event_type": event.get("event_type", "provinces_updated"),
        "game_id": event.get("game_id"),
        "iteration": event.get("iteration"),
        "timestamp": event.get("timestamp"),
        "provinces": provinces,
        "year": event.get("year"),
        "error": event.get("error"),
    }


_redis_client: Optional[redis.Redis] = None


def _get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
            logger.info(f"Aggregator connected to Redis at {REDIS_URL}")
        except redis.RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None
    return _redis_client


def _resolve_portrait_key(key: str) -> Optional[str]:
    """Resolve Redis key to portrait base64 data."""
    if not key:
        return None
    client = _get_redis_client()
    if not client:
        return None
    try:
        return client.get(key)
    except redis.RedisError as e:
        logger.error(f"Failed to resolve portrait key {key}: {e}")
        return None


def transform_portraits_event(event: dict) -> dict:
    """Transform Kafka portraits event, resolving Redis keys to base64."""
    portraits_in = event.get("portraits", [])
    portraits_out = []

    for p in portraits_in:
        portrait_key = p.get("portrait_key", "")
        portrait_base64 = _resolve_portrait_key(portrait_key)

        if portrait_base64:
            portraits_out.append({
                "tag": p.get("tag", ""),
                "ruler_name": p.get("ruler_name", ""),
                "portrait_base64": portrait_base64,
            })
            logger.debug(f"Resolved portrait for {p.get('ruler_name')}")
        else:
            logger.warning(f"Failed to resolve portrait key for {p.get('ruler_name')}")

    return {
        "type": "portraits_update",
        "event_type": event.get("event_type", "portraits_ready"),
        "game_id": event.get("game_id"),
        "iteration": event.get("iteration"),
        "timestamp": event.get("timestamp"),
        "portraits": portraits_out,
        "status": "success" if portraits_out else "failed",
        "error": event.get("error"),
    }


class AggregatorConsumer:
    """Consumes from Kafka topics and forwards to WebSocket manager."""

    def __init__(self):
        self._consumer: Optional[KafkaConsumer] = None
        self._thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()
        self._event_queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop, event_queue: asyncio.Queue) -> None:
        self._loop = loop
        self._event_queue = event_queue
        self._shutdown.clear()

        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("Aggregator consumer thread started")

    def stop(self) -> None:
        self._shutdown.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._consumer:
            self._consumer.close()
            self._consumer = None
        logger.info("Aggregator consumer stopped")

    def _run_consumer(self) -> None:
        try:
            logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
            logger.info(f"Subscribing to topics: {ALL_TOPICS}")

            self._consumer = KafkaConsumer(
                *ALL_TOPICS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_CONSUMER_GROUP,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="latest",
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

                            if topic == TOPIC_TIMELINE_EVENTS:
                                ws_message = transform_timeline_event(event)
                            elif topic == TOPIC_PROVINCES_UPDATED:
                                ws_message = transform_provinces_event(event)
                            elif topic == TOPIC_PORTRAITS_READY:
                                ws_message = transform_portraits_event(event)
                            else:
                                ws_message = {"type": message_type, **event}

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
        if self._loop and self._event_queue:
            self._loop.call_soon_threadsafe(
                self._event_queue.put_nowait,
                (game_id, message)
            )


consumer = AggregatorConsumer()
