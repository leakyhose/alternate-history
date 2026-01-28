"""Kafka producer for timeline events."""
import json
import os
import logging
from typing import Optional
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

TOPIC_TIMELINE_EVENTS = "timeline.events"
TOPIC_QUOTES_READY = "quotes.ready"
TOPIC_PROVINCES_UPDATED = "provinces.updated"
TOPIC_PORTRAITS_READY = "portraits.ready"

_producer: Optional[KafkaProducer] = None


def get_kafka_bootstrap_servers() -> str:
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        bootstrap_servers = get_kafka_bootstrap_servers()
        logger.info(f"Initializing Kafka producer: {bootstrap_servers}")
        _producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=3,
            batch_size=16384,
            linger_ms=10,
        )
    return _producer


def produce_timeline_event(
    game_id: str,
    iteration: int,
    scenario_id: str,
    year_range: str,
    filter_result: dict,
    historian_context: dict,
    dreamer_decision: dict,
    current_provinces: list = None,
) -> bool:
    """Produce a TimelineEvent to Kafka."""
    producer = get_producer()

    event = {
        "event_type": "timeline_event",
        "game_id": game_id,
        "iteration": iteration,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "scenario_id": scenario_id,
        "year_range": year_range,
        "filter_result": filter_result,
        "historian_context": historian_context,
        "dreamer_decision": dreamer_decision,
        "current_provinces": current_provinces or [],
    }

    try:
        future = producer.send(topic=TOPIC_TIMELINE_EVENTS, key=game_id, value=event)
        record_metadata = future.get(timeout=10)
        logger.info(f"Produced event: game={game_id}, iteration={iteration}, partition={record_metadata.partition}")
        return True
    except KafkaError as e:
        logger.error(f"Failed to produce event for game={game_id}: {e}")
        return False


def close_producer() -> None:
    global _producer
    if _producer is not None:
        _producer.flush()
        _producer.close()
        _producer = None
