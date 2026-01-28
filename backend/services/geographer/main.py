#!/usr/bin/env python3
"""Geographer microservice entry point."""
import logging
import signal
import sys
from typing import Optional

from .consumer import TimelineEventConsumer
from .producer import ProvincesProducer
from .geo_processor import process_territorial_changes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("geographer")

_shutdown_requested = False


def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    _shutdown_requested = True


def process_event(event: dict, producer: ProvincesProducer) -> None:
    """Process a single timeline event."""
    game_id = event.get("game_id", "unknown")
    iteration = event.get("iteration", 0)
    year_range = event.get("year_range", "0-0")

    # Extract year from year_range (e.g., "630-650" -> 650)
    try:
        year = int(year_range.split("-")[1])
    except (IndexError, ValueError):
        year = 0

    try:
        province_updates = process_territorial_changes(event)
        producer.produce_provinces(
            game_id=game_id,
            iteration=iteration,
            province_updates=province_updates,
            year=year,
        )
        logger.info(f"Processed game={game_id}, iteration={iteration}, updates={len(province_updates)}")
    except Exception as e:
        logger.error(f"Failed game={game_id}, iteration={iteration}: {e}")
        producer.produce_failure(game_id=game_id, iteration=iteration, error=str(e))


def run_service() -> None:
    """Main service loop."""
    global _shutdown_requested

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    consumer: Optional[TimelineEventConsumer] = None
    producer: Optional[ProvincesProducer] = None

    try:
        logger.info("Starting Geographer service")

        consumer = TimelineEventConsumer()
        consumer.connect()

        producer = ProvincesProducer()
        producer.connect()

        logger.info("Ready, waiting for events...")

        for event in consumer.consume():
            if _shutdown_requested:
                break
            process_event(event, producer)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)
    finally:
        logger.info("Shutting down...")
        if producer:
            producer.close()
        if consumer:
            consumer.close()


if __name__ == "__main__":
    run_service()
