#!/usr/bin/env python3
"""Quotegiver microservice entry point."""
import logging
import signal
import sys
from typing import Optional

from .consumer import TimelineEventConsumer
from .producer import QuotesProducer
from .quote_generator import generate_quotes_from_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("quotegiver")

_shutdown_requested = False


def signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Received signal {signum}, shutting down...")
    _shutdown_requested = True


def process_event(event: dict, producer: QuotesProducer) -> None:
    """Process a single timeline event."""
    game_id = event.get("game_id", "unknown")
    iteration = event.get("iteration", 0)

    try:
        quotes = generate_quotes_from_event(event)
        producer.produce_quotes(game_id=game_id, iteration=iteration, quotes=quotes)
        logger.info(f"Processed game={game_id}, iteration={iteration}, quotes={len(quotes)}")
    except Exception as e:
        logger.error(f"Failed game={game_id}, iteration={iteration}: {e}")
        producer.produce_failure(game_id=game_id, iteration=iteration, error=str(e))


def run_service() -> None:
    """Main service loop."""
    global _shutdown_requested

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    consumer: Optional[TimelineEventConsumer] = None
    producer: Optional[QuotesProducer] = None

    try:
        logger.info("Starting Quotegiver service")

        consumer = TimelineEventConsumer()
        consumer.connect()

        producer = QuotesProducer()
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
