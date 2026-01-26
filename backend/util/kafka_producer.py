"""Kafka producer utility for publishing timeline events."""
import json
import os
import logging
from typing import Optional, Any
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

# Topic names
TOPIC_TIMELINE_EVENTS = "timeline.events"
TOPIC_QUOTES_READY = "quotes.ready"
TOPIC_PROVINCES_UPDATED = "provinces.updated"
TOPIC_PORTRAITS_READY = "portraits.ready"

# Singleton producer instance
_producer: Optional[KafkaProducer] = None


def get_kafka_bootstrap_servers() -> str:
    """Get Kafka bootstrap servers from environment or use default."""
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")


def get_producer() -> KafkaProducer:
    """Get or create the singleton Kafka producer instance."""
    global _producer

    if _producer is None:
        bootstrap_servers = get_kafka_bootstrap_servers()
        logger.info(f"Initializing Kafka producer with bootstrap servers: {bootstrap_servers}")

        _producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            # Serialize values as JSON
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            # Serialize keys as UTF-8 strings
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            # Wait for all replicas to acknowledge (durability)
            acks="all",
            # Retry on transient failures
            retries=3,
            # Batch settings for efficiency
            batch_size=16384,
            linger_ms=10,
        )
        logger.info("Kafka producer initialized successfully")

    return _producer


def produce_timeline_event(
    game_id: str,
    iteration: int,
    scenario_id: str,
    year_range: str,
    filter_result: dict,
    historian_context: dict,
    dreamer_decision: dict,
) -> bool:
    """
    Produce a TimelineEvent to the timeline.events topic.

    Args:
        game_id: Unique identifier for the game session
        iteration: Iteration number (1, 2, 3, ...)
        scenario_id: The scenario being played (e.g., "rome")
        year_range: String like "630-650" representing the simulated period
        filter_result: Output from the filter agent
        historian_context: Output from the historian agent
        dreamer_decision: Output from the dreamer agent

    Returns:
        True if the message was sent successfully, False otherwise
    """
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
    }

    try:
        # Use game_id as the key for partition routing
        # All events for the same game go to the same partition (ordering guaranteed)
        future = producer.send(
            topic=TOPIC_TIMELINE_EVENTS,
            key=game_id,
            value=event,
        )
        # Block until the message is sent (or timeout)
        record_metadata = future.get(timeout=10)

        logger.info(
            f"Produced timeline event for game={game_id}, iteration={iteration} "
            f"to partition={record_metadata.partition}, offset={record_metadata.offset}"
        )
        return True

    except KafkaError as e:
        logger.error(f"Failed to produce timeline event for game={game_id}: {e}")
        return False


def close_producer() -> None:
    """Close the Kafka producer and release resources."""
    global _producer

    if _producer is not None:
        logger.info("Closing Kafka producer")
        _producer.flush()  # Ensure all pending messages are sent
        _producer.close()
        _producer = None
        logger.info("Kafka producer closed")
